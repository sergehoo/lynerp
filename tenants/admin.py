from django.contrib import admin
from django.contrib.admin import AdminSite
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from tenants.models import License, SeatAssignment, Tenant, TenantService, TenantSubscription, TenantSettings, \
    TenantActivityLog, TenantBilling, TenantInvitation, TenantDomain, TenantUser


# -- Admin dashboard (facultatif) -------------------------------------------------

class CustomAdminSite(AdminSite):
    """Admin d'accueil avec petits KPIs licences & seats."""
    site_header = "LyneERP – Administration"
    site_title = "LyneERP Admin"
    index_title = "Tableau de bord"

    def index(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}

        license_stats = License.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(active=True) & Q(valid_until__gte=timezone.now().date())),
            expired=Count('id', filter=Q(valid_until__lt=timezone.now().date())),
        )
        seat_stats = SeatAssignment.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(active=True)),
        )

        extra_context['license_stats'] = license_stats
        extra_context['seat_stats'] = seat_stats
        return super().index(request, extra_context)


# Tu peux l’utiliser si tu veux un site admin séparé :
# custom_admin_site = CustomAdminSite(name="custom_admin")


# -- Helpers communs ---------------------------------------------------------------

def license_is_valid(lic: License) -> bool:
    return bool(lic.active and lic.valid_until and lic.valid_until >= timezone.now().date())


def license_assigned_seats(lic: License) -> int:
    return SeatAssignment.objects.filter(
        tenant=lic.tenant, module=lic.module, active=True
    ).count()


def license_available_seats(lic: License) -> int:
    return max(lic.seats - license_assigned_seats(lic), 0)


# -- License admin -----------------------------------------------------------------
@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "domain",
        "plan_badge",
        "is_active",
        "trial_badge",
        "active_users_count_display",
        "created_at",
    )
    list_filter = ("is_active", "plan_type", "created_at")
    search_fields = ("name", "slug", "domain", "contact_email", "billing_email", "legal_name", "tax_id")
    list_editable = ("is_active",)
    date_hierarchy = "created_at"
    actions = ("activate_tenants", "deactivate_tenants")

    readonly_fields = (
        "created_at",
        "updated_at",
        "trial_badge",
        "active_users_count_display",
        "display_legal_name",
        "display_address",
    )

    fieldsets = (
        ("Configuration SaaS", {
            "fields": ("name", "slug", "domain", "is_active", "plan_type", "trial_ends_at"),
        }),
        ("Identité légale & Fiscalité", {
            "fields": ("legal_name", "trade_name", "legal_form", "registration_number", "tax_id", "tax_center"),
        }),
        ("Facturation", {
            "fields": (
                "currency", "default_tax_rate", "payment_terms_days",
                "billing_email", "billing_address_line1", "billing_address_line2",
                "billing_city", "billing_region", "billing_country", "billing_postal_code",
            ),
            "classes": ("collapse",),
        }),
        ("Coordonnées", {
            "fields": ("contact_email", "contact_phone", "website"),
            "classes": ("collapse",),
        }),
        ("Branding documents", {
            "fields": ("logo_url", "stamp_url", "signature_url", "invoice_footer_note"),
            "classes": ("collapse",),
        }),
        ("Paiement", {
            "fields": ("bank_details", "mobile_money_details"),
            "classes": ("collapse",),
        }),
        ("Dates", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        # adapte le related_name si ton TenantUser s'appelle autrement
        return super().get_queryset(request).prefetch_related("tenant_users")

    # ----- Badges UI -----
    def plan_badge(self, obj: Tenant):
        colors = {
            "STARTER": "#95a5a6",
            "PROFESSIONAL": "#2980b9",
            "ENTERPRISE": "#8e44ad",
        }
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:999px;">{}</span>',
            colors.get(obj.plan_type, "#111"),
            obj.get_plan_type_display(),
        )
    plan_badge.short_description = "Plan"

    def trial_badge(self, obj: Tenant):
        if obj.is_in_trial:
            days_left = max((obj.trial_ends_at - timezone.now()).days, 0)
            return format_html('<span style="color:#d97706;">⏰ Essai ({} j)</span>', days_left)
        return format_html('<span style="color:#6b7280;">—</span>')
    trial_badge.short_description = "Essai"

    def active_users_count_display(self, obj: Tenant):
        return format_html("<b>{}</b>", obj.active_users_count)
    active_users_count_display.short_description = "Users actifs"

    # ----- Actions -----
    def activate_tenants(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} tenant(s) activé(s).")
    activate_tenants.short_description = "Activer"

    def deactivate_tenants(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} tenant(s) désactivé(s).")
    deactivate_tenants.short_description = "Désactiver"

@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = (
        "user_email",
        "tenant",
        "role",
        "is_active",
        "is_owner_or_admin",
        "joined_at",
        "last_access"
    )
    list_filter = ("role", "is_active", "joined_at", "tenant")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "tenant__name"
    )
    list_editable = ("role", "is_active")
    readonly_fields = ("joined_at", "last_access_display")
    raw_id_fields = ("user", "invited_by")

    fieldsets = (
        ("Membre", {
            'fields': ('tenant', 'user', 'role', 'is_active')
        }),
        ("Services", {
            'fields': ('enabled_services',),
            'classes': ('collapse',)
        }),
        ("Invitation", {
            'fields': ('invited_by',),
            'classes': ('collapse',)
        }),
        ("Dates", {
            'fields': ('joined_at', 'last_access_display'),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def is_owner_or_admin(self, obj):
        if obj.is_owner:
            return format_html('<span style="color: red;">👑 Propriétaire</span>')
        elif obj.is_admin:
            return format_html('<span style="color: orange;">⚡ Admin</span>')
        return format_html('<span style="color: gray;">Membre</span>')

    is_owner_or_admin.short_description = "Privilèges"

    def last_access_display(self, obj):
        if obj.last_access:
            return obj.last_access.strftime("%d/%m/%Y %H:%M")
        return "Jamais"

    last_access_display.short_description = "Dernier accès"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'tenant')


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary", "tenant_plan")
    list_filter = ("is_primary", "tenant")
    search_fields = ("domain", "tenant__name")
    list_editable = ("is_primary",)

    def tenant_plan(self, obj):
        return obj.tenant.plan_type

    tenant_plan.short_description = "Plan tenant"


@admin.register(TenantService)
class TenantServiceAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "service_display",
        "license_type",
        "is_active",
        "status",
        "is_expired_display",
        "activated_at"
    )
    list_filter = ("service", "license_type", "is_active", "status", "tenant")
    search_fields = ("tenant__name", "service")
    list_editable = ("is_active", "status", "license_type")
    readonly_fields = ("activated_at", "days_until_expiry_display")

    fieldsets = (
        ("Service", {
            'fields': ('tenant', 'service', 'is_active', 'status')
        }),
        ("Licence", {
            'fields': ('license_type', 'external_license_id')
        }),
        ("Configuration", {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ("Validité", {
            'fields': ('activated_at', 'expires_at', 'days_until_expiry_display')
        }),
    )

    def service_display(self, obj):
        return obj.get_service_display()

    service_display.short_description = "Service"

    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">⚠️ Expiré</span>')
        elif obj.expires_at:
            days = obj.days_until_expiry
            if days and days < 7:
                return format_html('<span style="color: orange;">{} jours</span>', days)
            return format_html('<span style="color: green;">{} jours</span>', days)
        return format_html('<span style="color: gray;">Illimité</span>')

    is_expired_display.short_description = "Expiration"

    def days_until_expiry_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return "Aucune date d'expiration"
        return f"{days} jours"

    days_until_expiry_display.short_description = "Jours avant expiration"


@admin.register(TenantInvitation)
class TenantInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "tenant",
        "role",
        "status",
        "is_expired_display",
        "created_at",
        "expires_at"
    )
    list_filter = ("status", "role", "tenant", "created_at")
    search_fields = ("email", "tenant__name", "first_name", "last_name")
    readonly_fields = ("created_at", "accepted_at", "is_expired_display")
    actions = ["resend_invitations", "revoke_invitations"]

    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">✗ Expirée</span>')
        else:
            days_left = (obj.expires_at - timezone.now()).days
            return format_html('<span style="color: green;">✓ Valide ({}j)</span>', days_left)

    is_expired_display.short_description = "Validité"

    def resend_invitations(self, request, queryset):
        # Ici vous pouvez implémenter la logique de renvoi d'email
        count = queryset.count()
        self.message_user(request, f"{count} invitation(s) à renvoyer.")

    resend_invitations.short_description = "Renvoyer les invitations sélectionnées"

    def revoke_invitations(self, request, queryset):
        updated = queryset.update(status='REVOKED')
        self.message_user(request, f"{updated} invitation(s) révoquée(s).")

    revoke_invitations.short_description = "Révoquer les invitations sélectionnées"


@admin.register(TenantBilling)
class TenantBillingAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "tenant",
        "billing_period",
        "total_amount",
        "currency",
        "status_display",
        "due_date",
        "paid_at"
    )
    list_filter = ("status", "currency", "due_date", "tenant")
    search_fields = ("invoice_number", "tenant__name", "stripe_invoice_id")
    # readonly_fields = ("created_at", "issued_at", "paid_at")
    # list_editable = ("status",)

    fieldsets = (
        ("Facturation", {
            'fields': ('tenant', 'invoice_number', 'status')
        }),
        ("Période", {
            'fields': ('billing_period_start', 'billing_period_end')
        }),
        ("Montant", {
            'fields': ('total_amount', 'currency', 'tax_rate')
        }),
        ("Détails", {
            'fields': ('service_breakdown',),
            'classes': ('collapse',)
        }),
        ("Références externes", {
            'fields': ('stripe_invoice_id', 'pdf_url'),
            'classes': ('collapse',)
        }),
        ("Dates", {
            'fields': ('due_date', 'issued_at', 'paid_at')
        }),
    )

    def billing_period(self, obj):
        return f"{obj.billing_period_start} - {obj.billing_period_end}"

    billing_period.short_description = "Période"

    def status_display(self, obj):
        status_colors = {
            'DRAFT': 'gray',
            'ISSUED': 'blue',
            'PAID': 'green',
            'OVERDUE': 'red',
            'CANCELLED': 'darkred'
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};"><b>{}</b></span>',
            color, obj.get_status_display()
        )

    status_display.short_description = "Statut"


@admin.register(TenantActivityLog)
class TenantActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "action_display",
        "user_email",
        "ip_address",
        "created_at"
    )
    list_filter = ("action", "created_at", "tenant")
    search_fields = ("tenant__name", "user__email", "description", "ip_address")
    readonly_fields = ("created_at", "user_agent_display")
    date_hierarchy = "created_at"

    def action_display(self, obj):
        icons = {
            'USER_LOGGED_IN': '🔐',
            'USER_INVITED': '📨',
            'USER_ROLE_CHANGED': '👥',
            'SERVICE_ACTIVATED': '⚡',
            'SERVICE_CONFIGURED': '⚙️',
            'SETTINGS_UPDATED': '🔧',
            'BILLING_UPDATED': '💰'
        }
        icon = icons.get(obj.action, '📝')
        return f"{icon} {obj.get_action_display()}"

    action_display.short_description = "Action"

    def user_email(self, obj):
        return obj.user.email if obj.user else "Système"

    user_email.short_description = "Utilisateur"

    def user_agent_display(self, obj):
        return obj.user_agent or "Non disponible"

    user_agent_display.short_description = "User Agent"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'tenant')


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "language", "timezone", "require_2fa", "updated_at")
    list_filter = ("language", "require_2fa", "timezone")
    search_fields = ("tenant__name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Tenant", {
            'fields': ('tenant',)
        }),
        ("Préférences générales", {
            'fields': ('language', 'timezone', 'date_format')
        }),
        ("Sécurité", {
            'fields': ('require_2fa', 'session_timeout', 'max_login_attempts')
        }),
        ("Notifications", {
            'fields': ('email_notifications', 'billing_notifications', 'security_notifications'),
            'classes': ('collapse',)
        }),
        ("Configuration services", {
            'fields': ('service_configs',),
            'classes': ('collapse',)
        }),
        ("Dates", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "service_display",
        "license_type",
        "period",
        "started_at",
        "ended_at",
        "is_active"
    )
    list_filter = ("service", "license_type", "period", "tenant")
    search_fields = ("tenant__name", "service", "external_subscription_id")
    readonly_fields = ("created_at",)

    def service_display(self, obj):
        return dict(TenantService.SERVICE_CHOICES).get(obj.service, obj.service)

    service_display.short_description = "Service"

    def is_active(self, obj):
        if obj.ended_at and obj.ended_at < timezone.now():
            return format_html('<span style="color: red;">Inactif</span>')
        return format_html('<span style="color: green;">Actif</span>')

    is_active.short_description = "Statut"


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "module",
        "plan",
        "seats",
        "assigned_seats_col",
        "available_seats_col",
        "valid_until",
        "is_valid_col",
        "active",
    )
    list_filter = ("module", "active", "plan", "valid_until", "tenant")
    search_fields = ("tenant__name", "tenant__slug", "module", "plan")
    date_hierarchy = "valid_until"
    # Pas de created_at/updated_at dans ton modèle actuel → on ne les affiche pas.

    fieldsets = (
        ("Informations de base", {
            'fields': ('tenant', 'module', 'plan', 'active')
        }),
        ("Sièges", {
            # Affichages read-only calculés (via methods)
            'fields': (),
            'description': (
                "<div style='margin-top:6px'>"
                "Les sièges utilisés/disponibles sont calculés dynamiquement à partir des attributions actives."
                "</div>"
            )
        }),
        ("Validité", {
            'fields': ('seats', 'valid_until'),
        }),
    )

    # Colonnes calculées
    def assigned_seats_col(self, obj: License):
        return license_assigned_seats(obj)

    assigned_seats_col.short_description = "Sièges assignés"

    def available_seats_col(self, obj: License):
        return license_available_seats(obj)

    available_seats_col.short_description = "Sièges disponibles"

    def is_valid_col(self, obj: License):
        ok = license_is_valid(obj)
        if ok:
            days_left = (obj.valid_until - timezone.now().date()).days if obj.valid_until else None
            if days_left is None:
                return format_html('<span style="color:green;">✓ Valide</span>')
            color = "green" if days_left > 30 else ("orange" if days_left > 7 else "red")
            return format_html('<span style="color:{};">✓ Valide ({} j)</span>', color, days_left)
        return format_html('<span style="color:red;">✗ Expirée</span>')

    is_valid_col.short_description = "Statut"

    def get_queryset(self, request):
        # Optimisation
        qs = super().get_queryset(request)
        return qs.select_related('tenant')


# -- SeatAssignment admin ----------------------------------------------------------

@admin.register(SeatAssignment)
class SeatAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "module",
        "user_sub_short",
        "active",
        "activated_at",
        "duration_days",
    )
    list_filter = ("module", "active", "activated_at", "tenant")
    search_fields = ("tenant__name", "tenant__slug", "module", "user_sub")
    date_hierarchy = "activated_at"
    list_editable = ("active",)

    fieldsets = (
        ("Informations générales", {
            'fields': ('tenant', 'module', 'active')
        }),
        ("Utilisateur", {
            'fields': ('user_sub',)
        }),
        ("Dates", {
            'fields': ('activated_at',),
            'classes': ('collapse',)
        }),
    )

    # Colonnes calculées
    def user_sub_short(self, obj):
        return (obj.user_sub[:20] + "…") if obj.user_sub and len(obj.user_sub) > 20 else (obj.user_sub or "—")

    user_sub_short.short_description = "User ID"

    def duration_days(self, obj):
        if obj.activated_at:
            delta = timezone.now() - obj.activated_at
            return f"{delta.days} j"
        return "—"

    duration_days.short_description = "Âge"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tenant')
