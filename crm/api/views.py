"""API DRF du module CRM."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from crm.api.serializers import (
    AccountSerializer,
    ActivitySerializer,
    ContactSerializer,
    LeadSerializer,
    OpportunitySerializer,
    PipelineSerializer,
    StageSerializer,
)
from crm.models import (
    Account,
    Activity,
    Contact,
    Lead,
    LeadStatus,
    Opportunity,
    OpportunityStatus,
    Pipeline,
    Stage,
)
from hr.api.views import BaseTenantViewSet


class AccountViewSet(BaseTenantViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "legal_name", "email", "phone"]


class ContactViewSet(BaseTenantViewSet):
    queryset = Contact.objects.all().select_related("account")
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["first_name", "last_name", "email", "phone"]


class PipelineViewSet(BaseTenantViewSet):
    queryset = Pipeline.objects.all().prefetch_related("stages")
    serializer_class = PipelineSerializer
    permission_classes = [IsAuthenticated]


class StageViewSet(BaseTenantViewSet):
    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    permission_classes = [IsAuthenticated]


class OpportunityViewSet(BaseTenantViewSet):
    queryset = Opportunity.objects.all().select_related(
        "account", "primary_contact", "stage", "pipeline", "owner",
    )
    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "account__name"]
    ordering_fields = ["created_at", "expected_close_date", "amount"]

    @action(detail=True, methods=["post"], url_path="mark-won")
    def mark_won(self, request, pk=None):
        opp: Opportunity = self.get_object()
        opp.status = OpportunityStatus.WON
        opp.win_probability = 100
        opp.closed_at = timezone.now()
        opp.save()
        return Response(OpportunitySerializer(opp).data)

    @action(detail=True, methods=["post"], url_path="mark-lost")
    def mark_lost(self, request, pk=None):
        opp: Opportunity = self.get_object()
        opp.status = OpportunityStatus.LOST
        opp.win_probability = 0
        opp.closed_at = timezone.now()
        opp.lost_reason = (request.data.get("reason") or "")[:255]
        opp.save()
        return Response(OpportunitySerializer(opp).data)


class LeadViewSet(BaseTenantViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["first_name", "last_name", "email", "company"]

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        """Convertit un lead en Account + Contact + Opportunity (optionnel)."""
        lead: Lead = self.get_object()
        if lead.status == LeadStatus.CONVERTED:
            return Response(
                {"detail": "Lead déjà converti.", "code": "already_converted"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            account = Account.objects.create(
                tenant=lead.tenant,
                name=lead.company or f"{lead.first_name} {lead.last_name}".strip() or "Compte sans nom",
                email=lead.email, phone=lead.phone,
                industry=lead.industry,
                owner=lead.owner,
                type="PROSPECT",
            )
            if lead.first_name or lead.last_name:
                Contact.objects.create(
                    tenant=lead.tenant,
                    account=account,
                    first_name=lead.first_name,
                    last_name=lead.last_name,
                    email=lead.email,
                    phone=lead.phone,
                    is_primary=True,
                )
            lead.status = LeadStatus.CONVERTED
            lead.converted_account = account
            lead.converted_at = timezone.now()
            lead.save(update_fields=["status", "converted_account", "converted_at", "updated_at"])
        return Response(LeadSerializer(lead).data)


class ActivityViewSet(BaseTenantViewSet):
    queryset = Activity.objects.all().select_related("account", "contact", "opportunity", "lead", "assigned_to")
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
