"""
Console d'administration LyneAI : consommation tokens.

Exposée à ``/manage/ai-usage/`` (route déclarée dans ``ai_assistant.urls``).

La vue agrège ``AIMessage.prompt_tokens`` et ``AIMessage.completion_tokens``
sur le tenant courant pour produire :

- KPIs globaux (total tokens, prompts, complétions, conversations, users actifs).
- Répartition par module (general, hr, finance…).
- Top 10 utilisateurs par tokens consommés.
- Top 10 conversations par tokens consommés.
- Série temporelle quotidienne sur la période.

Filtres : ``?period=7d|30d|90d|all`` (défaut 30j).

Accès : OWNER/ADMIN du tenant courant (ou superuser Django).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from ai_assistant.models import AIConversation, AIMessage, AIMessageRole


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
PERIOD_PRESETS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


def _resolve_period(value: str) -> tuple[str, "timezone.datetime | None"]:
    """Renvoie (label, datetime_min) pour la période demandée."""
    value = (value or "30d").lower()
    days = PERIOD_PRESETS.get(value, 30)
    if days is None:
        return "all", None
    return value, timezone.now() - timedelta(days=days)


# --------------------------------------------------------------------------- #
# Vue
# --------------------------------------------------------------------------- #
class AIUsageDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Tableau de bord de consommation tokens IA pour le tenant courant.
    """

    template_name = "ai_assistant/admin_usage.html"
    raise_exception = False  # → redirige vers login si non auth

    # ---------------------------------------------------------------- ACL --- #
    def test_func(self) -> bool:
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return False
        try:
            from tenants.models import TenantUser
        except Exception:  # noqa: BLE001
            return False
        return TenantUser.objects.filter(
            tenant=tenant, user=user, is_active=True,
            role__in=["OWNER", "ADMIN"],
        ).exists()

    # ---------------------------------------------------------------- ctx --- #
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        ctx["tenant"] = tenant

        period_label, period_min = _resolve_period(self.request.GET.get("period"))
        ctx["period"] = period_label
        ctx["periods"] = list(PERIOD_PRESETS.keys())

        if tenant is None:
            ctx.update(self._empty_ctx())
            return ctx

        msgs = AIMessage.objects.filter(tenant=tenant)
        if period_min is not None:
            msgs = msgs.filter(created_at__gte=period_min)

        # KPIs globaux
        agg = msgs.aggregate(
            total_prompt=Sum("prompt_tokens"),
            total_completion=Sum("completion_tokens"),
            messages=Count("id"),
        )
        prompt = int(agg["total_prompt"] or 0)
        completion = int(agg["total_completion"] or 0)
        total = prompt + completion
        ctx["kpis"] = {
            "total_tokens": total,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "messages": int(agg["messages"] or 0),
            "conversations": (
                AIConversation.objects
                .filter(tenant=tenant, messages__in=msgs)
                .distinct().count()
            ),
            "active_users": (
                msgs.filter(role=AIMessageRole.USER)
                .values("conversation__user_id").distinct().count()
            ),
        }

        # Par module
        ctx["per_module"] = list(
            msgs.values("conversation__module")
            .annotate(
                total=Sum("prompt_tokens") + Sum("completion_tokens"),
                msgs=Count("id"),
            )
            .order_by("-total")
        )

        # Top 10 utilisateurs
        ctx["top_users"] = list(
            msgs.values(
                "conversation__user_id",
                email=F("conversation__user__email"),
                username=F("conversation__user__username"),
                first_name=F("conversation__user__first_name"),
                last_name=F("conversation__user__last_name"),
            )
            .annotate(
                total=Sum("prompt_tokens") + Sum("completion_tokens"),
                prompt=Sum("prompt_tokens"),
                completion=Sum("completion_tokens"),
                msgs=Count("id"),
            )
            .order_by("-total")[:10]
        )

        # Top 10 conversations
        ctx["top_conversations"] = list(
            msgs.values(
                "conversation_id",
                title=F("conversation__title"),
                module=F("conversation__module"),
                user_email=F("conversation__user__email"),
            )
            .annotate(
                total=Sum("prompt_tokens") + Sum("completion_tokens"),
                msgs=Count("id"),
            )
            .order_by("-total")[:10]
        )

        # Série quotidienne
        daily = list(
            msgs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total=Sum("prompt_tokens") + Sum("completion_tokens"),
                prompt=Sum("prompt_tokens"),
                completion=Sum("completion_tokens"),
            )
            .order_by("day")
        )
        ctx["daily"] = daily
        ctx["daily_labels"] = [d["day"].isoformat() if d.get("day") else "" for d in daily]
        ctx["daily_totals"] = [int(d.get("total") or 0) for d in daily]
        ctx["daily_max"] = max(ctx["daily_totals"]) if ctx["daily_totals"] else 0

        # Cap pour barres horizontales (utilisé en CSS width %).
        ctx["module_max"] = max(
            (m.get("total") or 0) for m in ctx["per_module"]
        ) or 1
        ctx["user_max"] = max(
            (u.get("total") or 0) for u in ctx["top_users"]
        ) or 1

        return ctx

    @staticmethod
    def _empty_ctx() -> Dict[str, Any]:
        return {
            "kpis": {
                "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "messages": 0, "conversations": 0, "active_users": 0,
            },
            "per_module": [],
            "top_users": [],
            "top_conversations": [],
            "daily": [],
            "daily_labels": [],
            "daily_totals": [],
            "daily_max": 0,
            "module_max": 1,
            "user_max": 1,
        }
