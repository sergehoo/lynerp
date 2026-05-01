"""
Orchestrateur d'une conversation IA.

Le runner :

1. Charge l'historique de la conversation.
2. Injecte le prompt système approprié au module + le contexte tenant/user.
3. **Décide automatiquement** s'il faut faire une recherche web (router LLM).
4. Si oui : exécute ``deep_research`` et injecte les sources en contexte.
5. Appelle Ollama (chat ou stream) pour la réponse finale.
6. Persiste la réponse comme ``AIMessage(role=ASSISTANT)``.
7. Journalise via ``AIAuditLog``.

Pour les outils : ce runner ne déclenche PAS de function-calling automatique
(qwen2.5 ne tool-calls pas nativement comme OpenAI). Les outils sont
invoqués depuis l'UI via des actions explicites (boutons "Analyser",
"Résumer", etc.) qui appellent les services métier directement (cf.
`ai_assistant/tools/`).

La décision de recherche web est entièrement déléguée au modèle via un
mini-prompt "router" qui retourne du JSON. L'utilisateur n'a rien à
activer : si le modèle juge qu'il manque d'informations factuelles
récentes, il déclenche la recherche.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional

from ai_assistant.models import (
    AIAuditEvent,
    AIConversation,
    AIMessage,
    AIMessageRole,
    AIModelConfig,
)
from ai_assistant.services.audit import log_event
from ai_assistant.services.context import build_user_context
from ai_assistant.services.ollama import OllamaError, get_ollama
from ai_assistant.services.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Router prompt : décide si une recherche web est nécessaire
# --------------------------------------------------------------------------- #
WEB_ROUTER_PROMPT = """Tu es un classifieur. À partir de la question de \
l'utilisateur, tu dois décider si une **recherche web en direct** est \
nécessaire pour répondre correctement.

Réponds UNIQUEMENT avec un JSON strict, sans texte autour, au format :
{{"needs_web": <true|false>, "search_query": "<requête optimisée pour Google>", "reason": "<courte justification>"}}

# Règles
- needs_web=true SI la question porte sur :
  * des informations factuelles datées (taux fiscaux d'une année précise,
    actualité réglementaire, jurisprudence récente, prix de marché,
    taux de change, météo, événements récents…)
  * des données qui ont pu évoluer après la date de connaissance du modèle
    ({knowledge_cutoff})
  * une législation locale / nationale spécifique pour laquelle tu n'es
    pas certain
  * une recherche explicite (« cherche sur internet », « actualité »,
    « dernières nouvelles », « 2025 », « 2026 »…)

- needs_web=false SI :
  * la question concerne les données internes de l'ERP de l'utilisateur
    (employés, factures, écritures comptables du tenant…)
  * la question est une connaissance générale stable (concepts de
    gestion, vocabulaire, méthodes éprouvées, code OHADA général…)
  * la question est une demande de rédaction, traduction, résumé, calcul
    qui n'exige pas d'information externe
  * il s'agit d'une simple salutation ou conversation

# Question de l'utilisateur
\"\"\"{question}\"\"\"

# Module ERP courant
{module}

JSON :"""


# Coupe la décision si la question est trop courte ou évidemment salutation.
_TRIVIAL_PATTERNS = (
    "bonjour", "salut", "hello", "hi", "merci", "thank", "ok",
    "ouais", "oui", "non", "no",
)


class ConversationRunner:
    """
    Encapsule la logique d'envoi de message dans une conversation IA.
    """

    DEFAULT_MAX_HISTORY = 30  # nombre max de messages historiques injectés

    # Active/désactive complètement la recherche web automatique
    # (ex. en environnement air-gapped) — peut être surchargé par settings.
    AUTO_WEB_RESEARCH = True

    # Longueur min de la question avant d'envisager le web (évite
    # de payer un LLM pour "ok" ou "merci").
    MIN_QUESTION_LENGTH = 12

    def __init__(self, conversation: AIConversation) -> None:
        self.conversation = conversation
        self.tenant = conversation.tenant
        self.user = conversation.user
        self.config = self._resolve_config()
        self.ollama = get_ollama()
        self.prompt_registry = get_prompt_registry()
        # État partagé entre la décision web et la génération finale :
        # rempli par ``_maybe_run_web_research`` avant l'appel principal.
        self._web_context: Optional[Dict[str, Any]] = None

    # ----------------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------------- #
    def send_user_message(
        self,
        content: str,
        *,
        request=None,
        stream: bool = False,
    ) -> Iterator[Dict[str, Any]] | AIMessage:
        """
        Persiste le message utilisateur, appelle Ollama, persiste la réponse.

        Si ``stream=True``, renvoie un générateur de chunks (pour SSE).
        Sinon, renvoie l'``AIMessage`` final de l'assistant.

        Avant l'appel principal, le runner peut **automatiquement** déclencher
        une recherche web s'il juge que la question l'exige. La décision est
        prise par un router LLM (cf. ``_decide_web_research``).
        """
        user_msg = AIMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            role=AIMessageRole.USER,
            content=content,
        )

        log_event(
            tenant=self.tenant, actor=self.user,
            conversation=self.conversation,
            event=AIAuditEvent.PROMPT_SENT,
            target_model="ai_assistant.AIMessage",
            target_id=str(user_msg.id),
            payload={"length": len(content), "module": self.conversation.module},
            request=request,
        )

        if stream:
            return self._stream_with_web(content, request=request)

        # Mode synchrone : on exécute la recherche web (silencieuse), puis le LLM.
        self._maybe_run_web_research(content, on_event=None)
        messages = self._build_message_payload()
        return self._sync_assistant(messages, request=request)

    # ----------------------------------------------------------------------- #
    # Décision automatique : faut-il faire une recherche web ?
    # ----------------------------------------------------------------------- #
    def _is_trivial_question(self, content: str) -> bool:
        """Évite l'appel router pour les messages triviaux."""
        text = (content or "").strip().lower()
        if len(text) < self.MIN_QUESTION_LENGTH:
            return True
        # Salutations courtes pures
        if text in _TRIVIAL_PATTERNS:
            return True
        return False

    def _decide_web_research(self, content: str) -> Dict[str, Any]:
        """
        Demande au modèle si une recherche web est nécessaire.

        Retourne un dict normalisé :
            {"needs_web": bool, "search_query": str, "reason": str}

        En cas d'erreur ou de JSON invalide, retourne ``needs_web=False``
        (fallback safe : on préfère ne pas chercher plutôt que de spammer
        DuckDuckGo).
        """
        if not self.AUTO_WEB_RESEARCH:
            return {"needs_web": False, "search_query": "", "reason": "disabled"}
        if self._is_trivial_question(content):
            return {"needs_web": False, "search_query": "", "reason": "trivial"}

        from django.conf import settings as _settings
        cutoff = getattr(_settings, "AI_KNOWLEDGE_CUTOFF", "fin 2024")

        prompt = WEB_ROUTER_PROMPT.format(
            question=content[:1500],
            module=self.conversation.module or "general",
            knowledge_cutoff=cutoff,
        )
        try:
            result = self.ollama.chat_json(
                [
                    {"role": "system",
                     "content": "Tu es un classifieur strict. Tu ne réponds qu'en JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                top_p=1.0,
                max_tokens=200,
            )
            data = result.get("data") or {}
        except OllamaError as exc:
            logger.warning("Web router unavailable: %s", exc)
            return {"needs_web": False, "search_query": "", "reason": f"router_error: {exc}"}

        needs_web = bool(data.get("needs_web"))
        query = (data.get("search_query") or content).strip()[:300]
        reason = (data.get("reason") or "")[:300]
        return {"needs_web": needs_web, "search_query": query, "reason": reason}

    def _maybe_run_web_research(
        self,
        content: str,
        *,
        on_event=None,
    ) -> None:
        """
        Si le router décide qu'une recherche web est nécessaire, exécute
        ``deep_research`` (sans synthèse Ollama : on injecte juste les
        snippets) et stocke le résultat dans ``self._web_context``.

        ``on_event`` est un callback optionnel pour pousser des événements
        de progression au front-end (mode streaming SSE).
        """
        decision = self._decide_web_research(content)
        if not decision.get("needs_web"):
            return

        query = decision["search_query"] or content
        if on_event:
            on_event({"type": "web_searching", "query": query, "reason": decision.get("reason", "")})

        # Import tardif pour éviter un cycle d'import au démarrage Django.
        try:
            from ai_assistant.services.web.research import deep_research
        except ImportError as exc:
            logger.warning("Web research unavailable: %s", exc)
            if on_event:
                on_event({"type": "web_done", "sources": [], "error": str(exc)})
            return

        try:
            research = deep_research(
                question=query,
                tenant=self.tenant,
                pages=3,
                sync_with_ollama=False,  # on laisse le LLM principal faire la synthèse
            )
        except Exception as exc:  # noqa: BLE001  (filet de sécurité large)
            logger.exception("deep_research failed: %s", exc)
            if on_event:
                on_event({"type": "web_done", "sources": [], "error": str(exc)})
            return

        sources = research.get("sources") or []
        self._web_context = {
            "query": query,
            "raw_snippets": research.get("raw_snippets", ""),
            "sources": sources,
            "provider": research.get("provider"),
            "reason": decision.get("reason", ""),
        }

        if on_event:
            on_event({
                "type": "web_done",
                "query": query,
                "sources": sources,
                "provider": research.get("provider"),
            })

    def _web_context_message(self) -> Optional[Dict[str, str]]:
        """
        Construit un message ``role=system`` à injecter dans le payload Ollama
        si une recherche web a été effectuée. Le LLM final s'en sert pour
        produire une synthèse citée.
        """
        if not self._web_context:
            return None
        sources = self._web_context.get("sources") or []
        snippets = self._web_context.get("raw_snippets") or ""
        if not snippets and not sources:
            return None
        sources_lines = []
        for src in sources:
            sources_lines.append(
                f"[{src.get('index')}] {src.get('title') or ''} — {src.get('url')}"
            )
        sources_block = "\n".join(sources_lines) or "(aucune)"
        return {
            "role": "system",
            "content": (
                "# Recherche web automatique exécutée\n\n"
                f"Tu as déclenché une recherche web pour : "
                f"« {self._web_context.get('query', '')} ».\n\n"
                "Voici les extraits récupérés en direct (à utiliser pour "
                "répondre **avec citations** [1], [2]… et un bloc Sources "
                "à la fin de ta réponse) :\n\n"
                f"{snippets[:18000]}\n\n"
                "## Sources disponibles\n"
                f"{sources_block}\n\n"
                "Cite ces sources [n] dans ta réponse pour chaque "
                "affirmation chiffrée ou factuelle. Si l'information "
                "manque, dis-le honnêtement."
            ),
        }

    # ----------------------------------------------------------------------- #
    # Internes
    # ----------------------------------------------------------------------- #
    def _resolve_config(self) -> Optional[AIModelConfig]:
        if self.conversation.config_id:
            return self.conversation.config
        return (
            AIModelConfig.objects
            .filter(tenant=self.tenant, is_default=True)
            .first()
        )

    def _system_prompt(self) -> str:
        ctx = build_user_context(self.user, self.tenant)
        prompt_name = f"{self.conversation.module}.system"
        rendered = self.prompt_registry.render(
            prompt_name, context=ctx, tenant=self.tenant,
        )
        if rendered:
            return rendered
        # Fallback générique
        return self.prompt_registry.render(
            "general.system", context=ctx, tenant=self.tenant,
        )

    def _build_message_payload(self) -> List[Dict[str, Any]]:
        """
        Compose la liste de messages au format LLM :
        [system, (optionnel: contexte web auto), ...historique limité..., dernier user]
        """
        history = list(
            self.conversation.messages
            .order_by("-created_at")[: self.DEFAULT_MAX_HISTORY]
        )
        history.reverse()

        payload: List[Dict[str, Any]] = []
        system = self._system_prompt()
        if system:
            payload.append({"role": "system", "content": system})

        # Contexte web automatique (si une recherche a été déclenchée).
        web_msg = self._web_context_message()
        if web_msg:
            payload.append(web_msg)

        for msg in history:
            if msg.role in {AIMessageRole.USER, AIMessageRole.ASSISTANT}:
                payload.append({"role": msg.role, "content": msg.content})
            elif msg.role == AIMessageRole.TOOL:
                payload.append({
                    "role": "tool",
                    "content": (
                        f"[outil={msg.tool_name}] "
                        f"résultat={msg.tool_result}"
                    ),
                })
        return payload

    def _model_options(self) -> Dict[str, Any]:
        if self.config:
            return {
                "model": self.config.model,
                "temperature": float(self.config.temperature),
                "top_p": float(self.config.top_p),
                "max_tokens": int(self.config.max_tokens),
            }
        return {}

    def _sync_assistant(self, messages, *, request=None) -> AIMessage:
        try:
            result = self.ollama.chat(messages, **self._model_options())
        except OllamaError as exc:
            assistant = AIMessage.objects.create(
                tenant=self.tenant,
                conversation=self.conversation,
                role=AIMessageRole.ASSISTANT,
                content=f"⚠️ Service IA indisponible : {exc}",
                metadata={"error": str(exc)},
            )
            return assistant

        metadata: Dict[str, Any] = {
            "model": result.get("model"),
            "duration_ms": result.get("duration_ms", 0),
        }
        if self._web_context:
            metadata["web_sources"] = self._web_context.get("sources", [])
            metadata["web_query"] = self._web_context.get("query", "")
            metadata["web_provider"] = self._web_context.get("provider")

        assistant = AIMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            role=AIMessageRole.ASSISTANT,
            content=result.get("content", ""),
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            metadata=metadata,
        )

        # Met à jour le titre de la conversation à partir du premier échange.
        if not self.conversation.title:
            preview = (assistant.content or "").strip().split("\n", 1)[0][:80]
            if preview:
                self.conversation.title = preview
                self.conversation.save(update_fields=["title", "updated_at"])

        log_event(
            tenant=self.tenant, actor=self.user,
            conversation=self.conversation,
            event=AIAuditEvent.RESPONSE_RECEIVED,
            target_model="ai_assistant.AIMessage",
            target_id=str(assistant.id),
            payload={
                "tokens": assistant.prompt_tokens + assistant.completion_tokens,
                "duration_ms": assistant.metadata.get("duration_ms", 0),
            },
            request=request,
        )
        return assistant

    def _stream_assistant(self, messages, *, request=None) -> Iterator[Dict[str, Any]]:
        """
        Générateur SSE : yield chunks puis crée l'AIMessage final.
        """
        accumulated: List[str] = []
        opts = self._model_options()
        prompt_tokens = 0
        completion_tokens = 0
        duration_ms = 0
        model = opts.get("model") or get_ollama().model

        try:
            for evt in self.ollama.chat_stream(messages, **opts):
                if "chunk" in evt:
                    accumulated.append(evt["chunk"])
                    yield {"type": "chunk", "delta": evt["chunk"]}
                if evt.get("done"):
                    prompt_tokens = evt.get("prompt_tokens", 0)
                    completion_tokens = evt.get("completion_tokens", 0)
                    duration_ms = evt.get("duration_ms", 0)
                    model = evt.get("model", model)
        except OllamaError as exc:
            yield {"type": "error", "message": str(exc)}
            return

        full_content = "".join(accumulated)
        metadata: Dict[str, Any] = {"model": model, "duration_ms": duration_ms}
        if self._web_context:
            metadata["web_sources"] = self._web_context.get("sources", [])
            metadata["web_query"] = self._web_context.get("query", "")
            metadata["web_provider"] = self._web_context.get("provider")

        assistant = AIMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            role=AIMessageRole.ASSISTANT,
            content=full_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            metadata=metadata,
        )

        if not self.conversation.title:
            preview = full_content.strip().split("\n", 1)[0][:80]
            if preview:
                self.conversation.title = preview
                self.conversation.save(update_fields=["title", "updated_at"])

        log_event(
            tenant=self.tenant, actor=self.user,
            conversation=self.conversation,
            event=AIAuditEvent.RESPONSE_RECEIVED,
            target_model="ai_assistant.AIMessage",
            target_id=str(assistant.id),
            payload={
                "tokens": prompt_tokens + completion_tokens,
                "duration_ms": duration_ms,
            },
            request=request,
        )
        done_evt: Dict[str, Any] = {
            "type": "done",
            "message_id": str(assistant.id),
            "content": full_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": model,
            "duration_ms": duration_ms,
        }
        if self._web_context:
            done_evt["sources"] = self._web_context.get("sources", [])
        yield done_evt

    # ----------------------------------------------------------------------- #
    # Wrapper streaming : recherche web automatique + génération
    # ----------------------------------------------------------------------- #
    def _stream_with_web(
        self,
        content: str,
        *,
        request=None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Pipeline streaming complet :
        1. Décide (LLM router) si une recherche web est nécessaire.
        2. Si oui : émet ``{type: web_searching}``, exécute deep_research,
           émet ``{type: web_done, sources: [...]}``.
        3. Construit le payload avec contexte web injecté.
        4. Délègue au stream Ollama principal.
        """
        # Buffer interne pour collecter les events de progression web,
        # qui seront émis vers le client via SSE avant les chunks LLM.
        progress_events: List[Dict[str, Any]] = []

        def _on_event(evt: Dict[str, Any]) -> None:
            progress_events.append(evt)

        self._maybe_run_web_research(content, on_event=_on_event)

        # Émet d'abord les events web (web_searching, web_done)
        for evt in progress_events:
            yield evt

        # Puis on lance le LLM avec contexte enrichi
        messages = self._build_message_payload()
        yield from self._stream_assistant(messages, request=request)
