from django.contrib import admin
from django.contrib.admin import AdminSite
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from tenants.models import License, SeatAssignment, Tenant


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