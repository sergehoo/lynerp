# tenants/models.py
from django.core.validators import MinValueValidator
from django.db import models
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Tenant(models.Model):

    slug = models.SlugField(max_length=64, unique=True)  # ex: acme
    name = models.CharField(max_length=128)
    domain = models.CharField(max_length=255, blank=True)  # ex: acme.lyneerp.com
    settings = models.JSONField(default=dict, blank=True)  # préférences (voir §3)

    # Informations de contact
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    # Statut et dates
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # Plan et facturation
    PLAN_TYPES = [
        ('STARTER', 'Starter'),
        ('PROFESSIONAL', 'Professional'),
        ('ENTERPRISE', 'Enterprise'),
    ]
    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPES,
        default='STARTER'
    )
    billing_email = models.EmailField(blank=True)

    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['domain']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    @property
    def is_in_trial(self):
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at

    @property
    def active_users_count(self):
        return self.tenant_users.filter(is_active=True).count()


class TenantUser(models.Model):

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='tenant_users'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tenant_memberships'
    )

    # Rôles dans le tenant
    ROLE_CHOICES = [
        ('OWNER', 'Propriétaire'),
        ('ADMIN', 'Administrateur'),
        ('MANAGER', 'Manager'),
        ('MEMBER', 'Membre'),
        ('VIEWER', 'Observateur'),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='MEMBER'
    )

    # Services activés pour cet utilisateur
    enabled_services = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste des services activés pour cet utilisateur"
    )

    # Statut
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_users'
    )

    # Dates
    last_access = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tenant_users'
        verbose_name = 'Membre du Tenant'
        verbose_name_plural = 'Membres des Tenants'
        unique_together = ['tenant', 'user']
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.tenant.name} ({self.role})"

    @property
    def is_owner(self):
        return self.role == 'OWNER'

    @property
    def is_admin(self):
        return self.role in ['OWNER', 'ADMIN']


class TenantDomain(models.Model):
    """
    Support de multiples domaines par tenant (login SSO, white-label, etc.)
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "tenant_domains"
        indexes = [
            models.Index(fields=["tenant", "domain"]),
        ]
        # NOTE: pas de 'deferrable' ici
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_domain_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.domain} ({'primary' if self.is_primary else 'alias'})"

    def clean(self):
        """
        Sécurise côté application (utile si backend sans contraintes partielles).
        Empêche d'avoir >1 domaine primaire pour le même tenant.
        """
        from django.core.exceptions import ValidationError
        if self.is_primary:
            qs = TenantDomain.objects.filter(tenant=self.tenant, is_primary=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_primary": "Un seul domaine primaire est autorisé par tenant."})

    def save(self, *args, **kwargs):
        self.full_clean()  # applique clean() avant save
        return super().save(*args, **kwargs)


class TenantService(models.Model):

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='tenant_services'
    )

    SERVICE_CHOICES = [
        ('RH', 'Ressources Humaines'),
        ('PROJET', 'Gestion de Projet'),
        ('COMMERCIAL', 'Commercial'),
        ('LOGISTIQUE', 'Logistique'),
        ('COMPTABILITE', 'Comptabilité'),
        ('INVENTAIRE', 'Gestion des stocks'),
    ]
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)

    # Configuration du service
    is_active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)

    # Licence et plan
    LICENSE_TYPES = [
        ('BASIC', 'Basic'),
        ('PRO', 'Professional'),
        ('ENTERPRISE', 'Enterprise'),
    ]
    license_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPES,
        default='BASIC'
    )

    # Dates
    activated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    STATUS_CHOICES = [
        ("ACTIVE", "Actif"),
        ("EXPIRED", "Expiré"),
        ("SUSPENDED", "Suspendu"),
        ("CANCELLED", "Annulé"),
    ]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="ACTIVE")
    external_license_id = models.CharField(max_length=120, blank=True,
                                           help_text="ID licence/abonnement côté fournisseur (Stripe/OM/Key)")

    class Meta:
        db_table = 'tenant_services'
        verbose_name = 'Service du Tenant'
        verbose_name_plural = 'Services des Tenants'
        unique_together = ['tenant', 'service']
        indexes = [
            models.Index(fields=['tenant', 'service']),
            models.Index(fields=['is_active']),
            models.Index(fields=['license_type']),
        ]

    def __str__(self):
        return f"{self.tenant.name} - {self.get_service_display()} ({self.license_type})"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def days_until_expiry(self):
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days


class TenantInvitation(models.Model):

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='invitations'
    )

    # Informations de l'invité
    email = models.EmailField()
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)

    # Rôle et services proposés
    role = models.CharField(
        max_length=20,
        choices=TenantUser.ROLE_CHOICES,
        default='MEMBER'
    )
    enabled_services = models.JSONField(default=list, blank=True)

    # Statut de l'invitation
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('ACCEPTED', 'Acceptée'),
        ('EXPIRED', 'Expirée'),
        ('REVOKED', 'Révoquée'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # Token et sécurité
    token = models.CharField(max_length=100, unique=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tenant_invitations'
        indexes = [
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['token']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(expires_at__gt=models.F('created_at')),
                                   name="invite_expires_after_creation"),
            models.UniqueConstraint(
                fields=['tenant', 'email'],
                condition=models.Q(status='PENDING'),
                name='uniq_pending_invite_per_tenant_email'
            ),
        ]

    def mark_accepted(self, user):
        self.status = "ACCEPTED"
        self.accepted_at = timezone.now()
        self.save(update_fields=["status", "accepted_at"])

    def __str__(self):
        return f"Invitation {self.email} - {self.tenant.name}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class TenantBilling(models.Model):

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing_records'
    )

    # Informations de facturation
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Détails des services facturés
    service_breakdown = models.JSONField(
        default=dict,
        help_text="Détail du coût par service"
    )

    # Statut de paiement
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('ISSUED', 'Émise'),
        ('PAID', 'Payée'),
        ('OVERDUE', 'En retard'),
        ('CANCELLED', 'Annulée'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    # Références externes
    invoice_number = models.CharField(max_length=50, unique=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)

    currency = models.CharField(max_length=3, default="XOF")  # ou "EUR"/"USD" selon marché
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    pdf_url = models.CharField(max_length=255, blank=True)  # clé de stockage MinIO/S3
    # contraintes
    # Dates
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField()

    class Meta:
        db_table = 'tenant_billing'
        verbose_name = 'Facturation Tenant'
        verbose_name_plural = 'Facturations Tenants'
        indexes = [
            models.Index(fields=['tenant', 'billing_period_start']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(total_amount__gte=0), name="billing_total_non_negative"),
            models.CheckConstraint(check=models.Q(billing_period_end__gte=models.F('billing_period_start')),
                                   name="billing_period_order"),
        ]

    def __str__(self):
        return f"Facture {self.invoice_number} - {self.tenant.name}"


class TenantActivityLog(models.Model):

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_activities'
    )

    # Action effectuée
    ACTION_CHOICES = [
        ('USER_LOGGED_IN', 'Connexion utilisateur'),
        ('USER_INVITED', 'Utilisateur invité'),
        ('USER_ROLE_CHANGED', 'Rôle utilisateur modifié'),
        ('SERVICE_ACTIVATED', 'Service activé'),
        ('SERVICE_CONFIGURED', 'Service configuré'),
        ('SETTINGS_UPDATED', 'Paramètres modifiés'),
        ('BILLING_UPDATED', 'Facturation modifiée'),
    ]
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)

    # Détails
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    # IP et user agent
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Date
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_activity_logs'
        verbose_name = 'Log d\'activité Tenant'
        verbose_name_plural = 'Logs d\'activité Tenants'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.tenant.name} - {self.created_at}"


class TenantSettings(models.Model):
    """
    Configuration spécifique pour chaque tenant
    """

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='tenant_settings'
    )

    # Paramètres généraux
    language = models.CharField(max_length=10, default='fr')
    timezone = models.CharField(max_length=50, default='Africa/Abidjan')
    date_format = models.CharField(max_length=20, default='DD/MM/YYYY')

    # Paramètres de sécurité
    require_2fa = models.BooleanField(default=False)
    session_timeout = models.PositiveIntegerField(default=60)  # en minutes
    max_login_attempts = models.PositiveIntegerField(default=5)

    # Paramètres de notification
    email_notifications = models.BooleanField(default=True)
    billing_notifications = models.BooleanField(default=True)
    security_notifications = models.BooleanField(default=True)

    # Configuration des services
    service_configs = models.JSONField(default=dict, blank=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Configuration Tenant'
        verbose_name_plural = 'Configurations Tenants'

    def __str__(self):
        return f"Configuration - {self.tenant.name}"


class TenantSubscription(models.Model):

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="subscriptions")
    service = models.CharField(max_length=20, choices=TenantService.SERVICE_CHOICES)
    license_type = models.CharField(max_length=20, choices=TenantService.LICENSE_TYPES)
    period = models.CharField(max_length=10, choices=[("monthly", "Mensuel"), ("yearly", "Annuel")], default="monthly")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    external_subscription_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenant_subscriptions"
        indexes = [models.Index(fields=["tenant", "service", "started_at"]), ]


class License(models.Model):
  # Ajout d'un ID
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="licenses"
    )
    module = models.SlugField()  # "rh"
    plan = models.CharField(max_length=32)  # Starter/Pro/Enterprise
    seats = models.PositiveIntegerField(default=5)
    valid_until = models.DateField()
    active = models.BooleanField(default=True)

    # Ajout des champs manquants pour la cohérence
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'licenses'
        verbose_name = 'Licence'
        verbose_name_plural = 'Licences'
        unique_together = ['tenant', 'module']  # Un seul type de licence par module et tenant
        indexes = [
            models.Index(fields=['tenant', 'module']),
            models.Index(fields=['active']),
            models.Index(fields=['valid_until']),
        ]

    def __str__(self):
        return f"{self.tenant.name} - {self.module} ({self.plan})"

    @property
    def is_valid(self):
        """Vérifie si la licence est active et non expirée"""
        return self.active and self.valid_until >= timezone.now().date()

    @property
    def available_seats(self):
        """Nombre de sièges disponibles"""
        assigned_count = self.seat_assignments.filter(active=True).count()
        return max(0, self.seats - assigned_count)

    @property
    def is_fully_utilized(self):
        """Vérifie si tous les sièges sont occupés"""
        return self.available_seats <= 0


class SeatAssignment(models.Model):
  # Ajout d'un ID
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="seat_assignments"  # Correction du related_name
    )
    license = models.ForeignKey(  # Lien vers la licence
        License,
        on_delete=models.CASCADE,
        related_name="seat_assignments",
        null=True,
        blank=True
    )
    module = models.SlugField()
    user_sub = models.CharField(max_length=128)  # sub du JWT
    user_email = models.EmailField()  # Ajout de l'email pour référence
    active = models.BooleanField(default=True)
    activated_at = models.DateTimeField(default=timezone.now)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'seat_assignments'
        verbose_name = 'Attribution de siège'
        verbose_name_plural = 'Attributions de sièges'
        unique_together = (("tenant", "module", "user_sub"),)
        indexes = [
            models.Index(fields=['tenant', 'module']),
            models.Index(fields=['user_sub']),
            models.Index(fields=['active']),
        ]

    def __str__(self):
        return f"{self.user_email} - {self.module} ({'Actif' if self.active else 'Inactif'})"

    def deactivate(self):
        """Désactive l'attribution de siège"""
        self.active = False
        self.deactivated_at = timezone.now()
        self.save()
