"""
Client Ollama pour LYNEERP.

- ``chat()``         : appel synchrone non-streaming → renvoie le message complet.
- ``chat_stream()``  : générateur Python qui yield chaque chunk de tokens.
- ``health()``       : ping rapide, utile pour monitoring.

Le client utilise ``requests`` (synchrone) volontairement : on s'aligne sur
le reste du projet (Django sync, Gunicorn workers thread). Pour du streaming
SSE côté DRF on bufferise simplement ce générateur.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Erreur côté Ollama (timeout, statut HTTP non-200, JSON invalide…)."""


class OllamaService:
    """
    Client Ollama minimal mais robuste.

    >>> svc = OllamaService()
    >>> reply = svc.chat([{"role": "user", "content": "Bonjour"}])
    >>> svc.health()
    True
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", 120)

    # ----------------------------------------------------------------------- #
    # API publique
    # ----------------------------------------------------------------------- #
    def health(self) -> bool:
        """Renvoie True si Ollama répond."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama injoignable : {exc}") from exc

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        format: Optional[str] = None,
        keep_alive: str = "5m",
    ) -> Dict[str, Any]:
        """
        Appel synchrone, renvoie un dict :

            {
                "content": "...",
                "model": "qwen2.5:7b",
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "duration_ms": 1024,
                "raw": {...},  # payload complet Ollama
            }
        """
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": float(temperature),
                "top_p": float(top_p),
                "num_predict": int(max_tokens),
            },
            "keep_alive": keep_alive,
        }
        if format:
            payload["format"] = format

        started = time.monotonic()
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Ollama chat failed: %s", exc)
            raise OllamaError(f"Ollama erreur réseau : {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise OllamaError(f"Réponse Ollama invalide : {exc}") from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "content": (data.get("message") or {}).get("content", ""),
            "model": data.get("model", payload["model"]),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "duration_ms": duration_ms,
            "raw": data,
        }

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        format: Optional[str] = None,
        keep_alive: str = "5m",
    ) -> Iterator[Dict[str, Any]]:
        """
        Streaming générateur. Yield des dicts:

            {"chunk": "..."}                # partiel
            {"done": True, "content": "...", "prompt_tokens": ..., ...}  # final

        Permet d'alimenter un SSE/EventSource côté front sans bloquer.
        """
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": float(temperature),
                "top_p": float(top_p),
                "num_predict": int(max_tokens),
            },
            "keep_alive": keep_alive,
        }
        if format:
            payload["format"] = format

        started = time.monotonic()
        accumulated: List[str] = []

        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=True,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except ValueError:
                        continue

                    delta = (evt.get("message") or {}).get("content", "")
                    if delta:
                        accumulated.append(delta)
                        yield {"chunk": delta}

                    if evt.get("done"):
                        yield {
                            "done": True,
                            "content": "".join(accumulated),
                            "model": evt.get("model", payload["model"]),
                            "prompt_tokens": evt.get("prompt_eval_count", 0),
                            "completion_tokens": evt.get("eval_count", 0),
                            "duration_ms": int((time.monotonic() - started) * 1000),
                            "raw": evt,
                        }
                        return
        except requests.RequestException as exc:
            logger.warning("Ollama stream failed: %s", exc)
            raise OllamaError(f"Ollama erreur réseau : {exc}") from exc

    # ----------------------------------------------------------------------- #
    # Helpers structurés (JSON forcé)
    # ----------------------------------------------------------------------- #
    def chat_json(
        self,
        messages: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Force le mode JSON (Ollama supporte ``format='json'``). Le contenu
        renvoyé est parsé en dict ; en cas de JSON invalide, on renvoie
        ``{"_raw": <contenu>, "_parse_error": True}``.
        """
        kwargs.setdefault("format", "json")
        result = self.chat(messages, **kwargs)
        try:
            result["data"] = json.loads(result["content"]) if result["content"] else {}
        except ValueError:
            result["data"] = {"_raw": result["content"], "_parse_error": True}
        return result


# --------------------------------------------------------------------------- #
# Instance singleton (pratique côté views/services)
# --------------------------------------------------------------------------- #
_default_service: Optional[OllamaService] = None


def get_ollama() -> OllamaService:
    global _default_service
    if _default_service is None:
        _default_service = OllamaService()
    return _default_service
