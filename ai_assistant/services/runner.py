"""
Orchestrateur d'une conversation IA.

Le runner :

1. Charge l'historique de la conversation.
2. Injecte le prompt système approprié au module + le contexte tenant/user.
3. Appelle Ollama (chat ou stream).
4. Persiste la réponse comme ``AIMessage(role=ASSISTANT)``.
5. Journalise via ``AIAuditLog``.

Pour les outils : ce runner ne déclenche PAS de function-calling automatique
(qwen2.5 ne tool-calls pas nativement comme OpenAI). Les outils sont
invoqués depuis l'UI via des actions explicites (boutons "Analyser",
"Résumer", etc.) qui appellent les services métier directement (cf.
`ai_assistant/tools/`).
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


class ConversationRunner:
    """
    Encapsule la logique d'envoi de message dans une conversation IA.
    """

    DEFAULT_MAX_HISTORY = 30  # nombre max de messages historiques injectés

    def __init__(self, conversation: AIConversation) -> None:
        self.conversation = conversation
        self.tenant = conversation.tenant
        self.user = conversation.user
        self.config = self._resolve_config()
        self.ollama = get_ollama()
        self.prompt_registry = get_prompt_registry()

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

        messages = self._build_message_payload()

        if stream:
            return self._stream_assistant(messages, request=request)
        return self._sync_assistant(messages, request=request)

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
        [system, ...historique limité..., dernier user]
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

        assistant = AIMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            role=AIMessageRole.ASSISTANT,
            content=result.get("content", ""),
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            metadata={
                "model": result.get("model"),
                "duration_ms": result.get("duration_ms", 0),
            },
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
        assistant = AIMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            role=AIMessageRole.ASSISTANT,
            content=full_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            metadata={"model": model, "duration_ms": duration_ms},
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
        yield {
            "type": "done",
            "message_id": str(assistant.id),
            "content": full_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": model,
            "duration_ms": duration_ms,
        }
