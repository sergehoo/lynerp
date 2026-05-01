from __future__ import annotations

from rest_framework import serializers

from crm.models import (
    Account,
    Activity,
    Contact,
    Lead,
    Opportunity,
    Pipeline,
    Stage,
)


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class ContactSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ["id", "tenant", "full_name", "created_at", "updated_at"]


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class PipelineSerializer(serializers.ModelSerializer):
    stages = StageSerializer(many=True, read_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id", "code", "name", "description",
            "is_default", "is_active", "stages",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "stages", "created_at", "updated_at"]


class OpportunitySerializer(serializers.ModelSerializer):
    weighted_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    account_name = serializers.CharField(source="account.name", read_only=True)
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = Opportunity
        fields = "__all__"
        read_only_fields = [
            "id", "tenant", "weighted_amount", "account_name", "stage_name",
            "ai_score", "ai_score_explanation", "created_at", "updated_at",
        ]


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = "__all__"
        read_only_fields = [
            "id", "tenant", "ai_score", "ai_score_explanation",
            "converted_at", "created_at", "updated_at",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]
