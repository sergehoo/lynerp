# Lyneerp/hr/models.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from hr.storage import TenantPath
from tenants.models import Tenant


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    # tenant_id = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    tenant_id = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )
    # Champs ajoutés
    code = models.CharField(max_length=20, blank=True, help_text="Code département (ex: IT, HR, FIN)")
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Budget annuel du département"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("tenant_id", "name"),)
        db_table = 'hr_department'
        verbose_name = 'Département'
        verbose_name_plural = 'Départements'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"

    @property
    def active_contracts_count(self):
        """Nombre de contrats actifs dans le département"""
        today = timezone.now().date()
        return self.contracts.filter(
            status='ACTIVE',
            start_date__lte=today,
            end_date__gte=today
        ).count()
    @property
    def employees_count(self):
        return self.employee_set.filter(is_active=True).count()

    @property
    def full_path(self):
        """Retourne le chemin complet du département"""
        path = []
        current = self
        while current:
            path.append(current.name)
            current = current.parent
        return ' / '.join(reversed(path))


class Position(models.Model):
    """Poste/emploi dans l'organisation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=120)
    code = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='positions')
    description = models.TextField(blank=True)

    # Grille salariale
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Classification
    LEVEL_CHOICES = [
        ('INTERN', 'Stagiaire'),
        ('JUNIOR', 'Junior'),
        ('MID', 'Intermédiaire'),
        ('SENIOR', 'Senior'),
        ('LEAD', 'Lead'),
        ('MANAGER', 'Manager'),
        ('DIRECTOR', 'Directeur'),
        ('EXECUTIVE', 'Direction'),
    ]
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='JUNIOR')

    tenant_id = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("tenant_id", "title"), ("tenant_id", "code"))

        db_table = 'hr_positions'
        verbose_name = 'Poste'
        verbose_name_plural = 'Postes'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_level_display()})"


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matricule = models.CharField(max_length=64, unique=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    department = models.ForeignKey(Department, null=True, on_delete=models.SET_NULL)
    hire_date = models.DateField()
    contract_type = models.CharField(max_length=64)
    extra = models.JSONField(default=dict, blank=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,db_column='tenant_id',  # tenant requis
        db_index=True,
    )

    # Champs ajoutés
    position = models.ForeignKey(
        Position,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees'
    )

    # Informations personnelles
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=1,
        choices=[('M', 'Masculin'), ('F', 'Féminin'), ('O', 'Autre')],
        blank=True
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.JSONField(default=dict, blank=True)

    # Informations professionnelles
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Salaire brut mensuel"
    )
    work_schedule = models.CharField(
        max_length=20,
        choices=[
            ('FULL_TIME', 'Temps plein'),
            ('PART_TIME', 'Temps partiel'),
            ('FLEXIBLE', 'Horaires flexibles'),
        ],
        default='FULL_TIME'
    )

    # Statut
    is_active = models.BooleanField(default=True)
    termination_date = models.DateField(null=True, blank=True)
    termination_reason = models.TextField(blank=True)

    # Système
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_account = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profile'
    )

    class Meta:
        unique_together = (("tenant", "email"), ("tenant", "matricule"))
        db_table = 'hr_employees'
        verbose_name = 'Employé'
        verbose_name_plural = 'Employés'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['department']),
            models.Index(fields=['hire_date']),
            models.Index(fields=['contract_type']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.matricule})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def seniority(self):
        """Ancienneté en années"""
        if self.hire_date:
            delta = timezone.now().date() - self.hire_date
            return delta.days // 365
        return 0

    @property
    def is_on_leave(self):
        """Vérifie si l'employé est actuellement en congé"""
        today = timezone.now().date()
        return self.leaverequest_set.filter(
            status='approved',
            start_date__lte=today,
            end_date__gte=today
        ).exists()

        # Ajout de propriétés pour les contrats
        @property
        def current_contract(self):
            """Retourne le contrat actuel de l'employé"""
            today = timezone.now().date()
            return self.contracts.filter(
                start_date__lte=today,
                end_date__gte=today,
                status='ACTIVE'
            ).first() or self.contracts.filter(
                start_date__lte=today,
                end_date__isnull=True,
                status='ACTIVE'
            ).first()

        @property
        def contract_history(self):
            """Retourne l'historique complet des contrats"""
            return self.contracts.all().order_by('-start_date')

        @property
        def has_active_contract(self):
            """Vérifie si l'employé a un contrat actif"""
            return self.current_contract is not None

        @property
        def contract_status(self):
            """Statut du contrat actuel"""
            contract = self.current_contract
            if not contract:
                return "Aucun contrat"

            if contract.is_probation_period:
                return "Période d'essai"
            elif contract.status == 'ACTIVE':
                return "Actif"
            else:
                return contract.get_status_display()


class ContractType(models.Model):
    """Types de contrats standardisés"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Nom du type de contrat")
    code = models.CharField(max_length=50, unique=True, help_text="Code unique du contrat")
    description = models.TextField(blank=True, help_text="Description du type de contrat")

    # Caractéristiques du contrat
    is_permanent = models.BooleanField(default=False, help_text="Contrat à durée indéterminée")
    has_probation = models.BooleanField(default=True, help_text="Période d'essai incluse")
    default_probation_days = models.PositiveIntegerField(default=90, help_text="Durée par défaut de la période d'essai")
    requires_approval = models.BooleanField(default=True, help_text="Nécessite une approbation")

    # Configuration légale
    legal_reference = models.CharField(max_length=200, blank=True, help_text="Référence légale")
    minimum_salary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Salaire minimum légal pour ce type de contrat"
    )
    maximum_hours = models.PositiveIntegerField(
        default=40, help_text="Heures maximum hebdomadaires"
    )

    tenant_id = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_contract_types'
        verbose_name = 'Type de contrat'
        verbose_name_plural = 'Types de contrats'
        unique_together = (("tenant_id", "code"),)
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['is_permanent']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        if self.is_permanent and self.default_probation_days > 365:
            raise ValidationError({
                'default_probation_days': 'La période d\'essai ne peut excéder 365 jours pour un CDI'
            })


class EmploymentContract(models.Model):
    """Contrat de travail"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='contracts')
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, related_name='contracts')

    # Informations de base
    contract_number = models.CharField(max_length=100, unique=True, help_text="Numéro unique du contrat")
    title = models.CharField(max_length=200, help_text="Intitulé du poste")
    department = models.ForeignKey('Department', on_delete=models.PROTECT, related_name='contracts')
    position = models.ForeignKey('Position', on_delete=models.PROTECT, related_name='contracts', null=True, blank=True)

    # Période du contrat
    start_date = models.DateField(help_text="Date de début du contrat")
    end_date = models.DateField(null=True, blank=True, help_text="Date de fin (pour CDD)")
    expected_end_date = models.DateField(null=True, blank=True, help_text="Date de fin prévisionnelle")

    # Période d'essai
    probation_start_date = models.DateField(null=True, blank=True, help_text="Début de la période d'essai")
    probation_end_date = models.DateField(null=True, blank=True, help_text="Fin de la période d'essai")
    probation_duration_days = models.PositiveIntegerField(default=90, help_text="Durée de la période d'essai en jours")

    # Rémunération
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, help_text="Salaire de base")
    salary_currency = models.CharField(max_length=3, default='EUR', help_text="Devise du salaire")
    salary_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Mensuel'),
            ('WEEKLY', 'Hebdomadaire'),
            ('BIWEEKLY', 'Bimensuel'),
            ('DAILY', 'Journalier'),
            ('HOURLY', 'Horaire'),
        ],
        default='MONTHLY'
    )

    # Temps de travail
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, default=40.0, help_text="Heures hebdomadaires")
    work_schedule = models.ForeignKey(
        'WorkScheduleTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts'
    )

    # Lieu de travail
    work_location = models.CharField(max_length=200, blank=True, help_text="Lieu de travail principal")
    remote_allowed = models.BooleanField(default=False, help_text="Télétravail autorisé")
    remote_days_per_week = models.PositiveIntegerField(default=0, help_text="Jours de télétravail par semaine")

    # Statut du contrat
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('PENDING_APPROVAL', 'En attente d\'approbation'),
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('TERMINATED', 'Résilié'),
        ('EXPIRED', 'Expiré'),
        ('RENEWED', 'Renouvelé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # Raison de la résiliation
    termination_reason = models.TextField(blank=True, help_text="Raison de la résiliation")
    termination_date = models.DateField(null=True, blank=True, help_text="Date de résiliation")
    termination_type = models.CharField(
        max_length=20,
        choices=[
            ('RESIGNATION', 'Démission'),
            ('DISMISSAL', 'Licenciement'),
            ('MUTUAL_AGREEMENT', 'Rupture conventionnelle'),
            ('END_CONTRACT', 'Fin de contrat'),
            ('OTHER', 'Autre'),
        ],
        blank=True
    )

    # Documents
    contract_document = models.FileField(
        upload_to=TenantPath('contracts'),
        null=True,
        blank=True,
        help_text="Document du contrat signé"
    )
    amendment_document = models.FileField(
        upload_to=TenantPath('contract_amendments'),
        null=True,
        blank=True,
        help_text="Avenant au contrat"
    )

    # Métadonnées
    signed_by_employee = models.BooleanField(default=False, help_text="Signé par l'employé")
    signed_by_employer = models.BooleanField(default=False, help_text="Signé par l'employeur")
    signed_date = models.DateField(null=True, blank=True, help_text="Date de signature")

    # Approbations
    approved_by = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_contracts'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_contracts'
    )

    class Meta:
        db_table = 'hr_employment_contracts'
        verbose_name = 'Contrat de travail'
        verbose_name_plural = 'Contrats de travail'
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['employee', 'start_date']),
            models.Index(fields=['contract_number']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'end_date']),
        ]
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.contract_number} - {self.employee}"

    def clean(self):
        errors = {}

        # Validation des dates
        if self.end_date and self.start_date > self.end_date:
            errors['end_date'] = "La date de fin doit être après la date de début"

        if self.probation_end_date and self.probation_start_date:
            if self.probation_start_date >= self.probation_end_date:
                errors['probation_end_date'] = "La fin de la période d'essai doit être après le début"

            if self.probation_start_date < self.start_date:
                errors['probation_start_date'] = "La période d'essai ne peut commencer avant le début du contrat"

        if self.termination_date and self.start_date > self.termination_date:
            errors['termination_date'] = "La date de résiliation doit être après la date de début"

        # Validation CDD vs CDI
        if self.contract_type.is_permanent and self.end_date:
            errors['end_date'] = "Un CDI ne doit pas avoir de date de fin"

        if not self.contract_type.is_permanent and not self.end_date:
            errors['end_date'] = "Un CDD doit avoir une date de fin"

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Génération automatique du numéro de contrat si vide
        if not self.contract_number:
            self.contract_number = self.generate_contract_number()

        # Calcul automatique de la fin de période d'essai si début spécifié
        if self.probation_start_date and not self.probation_end_date:
            from datetime import timedelta
            self.probation_end_date = self.probation_start_date + timedelta(days=self.probation_duration_days)

        super().save(*args, **kwargs)

    def generate_contract_number(self):
        """Génère un numéro de contrat unique"""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('contract_number_seq')")
            seq = cursor.fetchone()[0]
        return f"CT{timezone.now().year}{seq:06d}"

    @property
    def is_active(self):
        """Vérifie si le contrat est actif"""
        today = timezone.now().date()
        return (self.status == 'ACTIVE' and
                self.start_date <= today and
                (not self.end_date or self.end_date >= today))

    @property
    def is_probation_period(self):
        """Vérifie si l'employé est en période d'essai"""
        if not self.probation_start_date or not self.probation_end_date:
            return False
        today = timezone.now().date()
        return self.probation_start_date <= today <= self.probation_end_date

    @property
    def days_until_end(self):
        """Jours restants jusqu'à la fin du contrat"""
        if not self.end_date:
            return None
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days

    @property
    def contract_duration_days(self):
        """Durée totale du contrat en jours"""
        if not self.end_date:
            return None
        return (self.end_date - self.start_date).days

    @property
    def can_be_renewed(self):
        """Vérifie si le contrat peut être renouvelé"""
        if self.contract_type.is_permanent:
            return False
        return self.days_until_end is not None and self.days_until_end <= 30

    @property
    def requires_renewal(self):
        """Vérifie si le contrat nécessite un renouvellement"""
        return self.days_until_end is not None and self.days_until_end <= 60


class ContractAmendment(models.Model):
    """Avenant à un contrat existant"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(EmploymentContract, on_delete=models.CASCADE, related_name='amendments')
    amendment_number = models.CharField(max_length=50, help_text="Numéro de l'avenant")

    # Type d'avenant
    AMENDMENT_TYPES = [
        ('SALARY', 'Modification de salaire'),
        ('POSITION', 'Changement de poste'),
        ('SCHEDULE', 'Modification d\'horaire'),
        ('LOCATION', 'Changement de lieu'),
        ('DURATION', 'Prolongation de contrat'),
        ('OTHER', 'Autre modification'),
    ]
    amendment_type = models.CharField(max_length=20, choices=AMENDMENT_TYPES)

    # Description des modifications
    description = models.TextField(help_text="Description détaillée des modifications")
    effective_date = models.DateField(help_text="Date d'effet de l'avenant")

    # Anciennes valeurs (pour historique)
    previous_data = models.JSONField(default=dict, help_text="Données avant modification")
    new_data = models.JSONField(default=dict, help_text="Nouvelles données")

    # Statut
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Brouillon'),
            ('PENDING_SIGNATURE', 'En attente de signature'),
            ('SIGNED', 'Signé'),
            ('REJECTED', 'Rejeté'),
        ],
        default='DRAFT'
    )

    # Documents
    amendment_document = models.FileField(
        upload_to=TenantPath('contract_amendments'),
        null=True,
        blank=True
    )

    # Signatures
    signed_by_employee = models.BooleanField(default=False)
    signed_by_employer = models.BooleanField(default=False)
    signed_date = models.DateField(null=True, blank=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_amendments'
    )

    class Meta:
        db_table = 'hr_contract_amendments'
        verbose_name = 'Avenant de contrat'
        verbose_name_plural = 'Avenants de contrats'
        unique_together = (("contract", "amendment_number"),)
        indexes = [
            models.Index(fields=['tenant_id', 'effective_date']),
            models.Index(fields=['contract', 'amendment_type']),
        ]
        ordering = ['-effective_date']

    def __str__(self):
        return f"Avenant {self.amendment_number} - {self.contract}"

    @property
    def is_effective(self):
        """Vérifie si l'avenant est en vigueur"""
        return (self.status == 'SIGNED' and
                self.effective_date <= timezone.now().date())


class ContractTemplate(models.Model):
    """Modèles de contrats pré-définis"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Nom du modèle")
    contract_type = models.ForeignKey(ContractType, on_delete=models.CASCADE, related_name='templates')

    # Contenu du modèle
    template_file = models.FileField(
        upload_to=TenantPath('contract_templates'),
        help_text="Fichier template du contrat"
    )
    template_content = models.TextField(blank=True, help_text="Contenu textuel du template")

    # Variables disponibles
    available_variables = models.JSONField(
        default=list,
        help_text="Liste des variables disponibles dans le template"
    )

    # Statut
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Template par défaut pour ce type de contrat")

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_contract_templates'
        verbose_name = 'Modèle de contrat'
        verbose_name_plural = 'Modèles de contrats'
        unique_together = (("tenant_id", "name"),)
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['contract_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.contract_type})"

    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'un seul template par défaut par type
        if self.is_default:
            ContractTemplate.objects.filter(
                tenant_id=self.tenant_id,
                contract_type=self.contract_type,
                is_default=True
            ).update(is_default=False)
        super().save(*args, **kwargs)


class ContractAlert(models.Model):
    """Alertes et rappels pour les contrats"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(EmploymentContract, on_delete=models.CASCADE, related_name='alerts')

    # Type d'alerte
    ALERT_TYPES = [
        ('CONTRACT_END', 'Fin de contrat'),
        ('PROBATION_END', 'Fin de période d\'essai'),
        ('RENEWAL_REMINDER', 'Rappel de renouvellement'),
        ('DOCUMENT_EXPIRY', 'Expiration de document'),
        ('COMPLIANCE_CHECK', 'Vérification de conformité'),
    ]
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)

    # Détails de l'alerte
    title = models.CharField(max_length=200, help_text="Titre de l'alerte")
    message = models.TextField(help_text="Message détaillé de l'alerte")
    due_date = models.DateField(help_text="Date d'échéance")

    # Priorité
    PRIORITY_CHOICES = [
        ('LOW', 'Basse'),
        ('MEDIUM', 'Moyenne'),
        ('HIGH', 'Haute'),
        ('URGENT', 'Urgente'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')

    # Statut
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'En attente'),
            ('IN_PROGRESS', 'En cours'),
            ('RESOLVED', 'Résolue'),
            ('DISMISSED', 'Ignorée'),
        ],
        default='PENDING'
    )

    # Assignation
    assigned_to = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_alerts'
    )

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hr_contract_alerts'
        verbose_name = 'Alerte contrat'
        verbose_name_plural = 'Alertes contrats'
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['priority']),
        ]
        ordering = ['due_date', 'priority']

    def __str__(self):
        return f"{self.alert_type} - {self.contract}"

    @property
    def is_overdue(self):
        """Vérifie si l'alerte est en retard"""
        return self.due_date < timezone.now().date() and self.status == 'PENDING'

    @property
    def days_until_due(self):
        """Jours restants jusqu'à l'échéance"""
        today = timezone.now().date()
        if today > self.due_date:
            return 0
        return (self.due_date - today).days


class ContractHistory(models.Model):
    """Historique des modifications des contrats"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(EmploymentContract, on_delete=models.CASCADE, related_name='history')

    # Action effectuée
    ACTION_CHOICES = [
        ('CREATED', 'Création'),
        ('UPDATED', 'Modification'),
        ('STATUS_CHANGED', 'Changement de statut'),
        ('AMENDMENT_ADDED', 'Avenant ajouté'),
        ('DOCUMENT_UPLOADED', 'Document uploadé'),
        ('SIGNED', 'Signature'),
        ('TERMINATED', 'Résiliation'),
        ('RENEWED', 'Renouvellement'),
    ]
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)

    # Détails
    description = models.TextField(help_text="Description de l'action")
    changes = models.JSONField(default=dict, help_text="Détails des changements")

    # Métadonnées
    performed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='contract_actions'
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_contract_history'
        verbose_name = 'Historique contrat'
        verbose_name_plural = 'Historiques contrats'
        indexes = [
            models.Index(fields=['tenant_id', 'performed_at']),
            models.Index(fields=['contract', 'action']),
        ]
        ordering = ['-performed_at']

    def __str__(self):
        return f"{self.action} - {self.contract}"


class SalaryHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='salary_history')
    effective_date = models.DateField()
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200, blank=True)
    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_salary_history'
        indexes = [models.Index(fields=['tenant_id', 'employee', 'effective_date'])]
        unique_together = (('employee', 'effective_date'),)


class HRDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    category = models.CharField(max_length=50)  # 'contract','id','medical','other'...
    file = models.FileField(upload_to=TenantPath('hr_documents'))
    title = models.CharField(max_length=120, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_documents'
        indexes = [models.Index(fields=['tenant_id', 'category', 'uploaded_at'])]


class LeaveType(models.Model):
    """Types de congés (annuel, maladie, maternité, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    # Configuration
    max_days = models.PositiveIntegerField(help_text="Nombre maximum de jours par an")
    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    carry_over = models.BooleanField(
        default=False,
        help_text="Report des jours non utilisés à l'année suivante"
    )
    carry_over_max = models.PositiveIntegerField(
        default=0,
        help_text="Nombre maximum de jours reportables"
    )

    tenant_id = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("tenant_id", "name"), ("tenant_id", "code"))
        db_table = 'hr_leave_types'
        verbose_name = 'Type de congé'
        verbose_name_plural = 'Types de congés'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class HolidayCalendar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    country = models.CharField(max_length=2, blank=True)  # 'CI','FR', ...
    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_holiday_calendars'
        unique_together = (('tenant_id', 'name'),)


class Holiday(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    label = models.CharField(max_length=120)

    class Meta:
        db_table = 'hr_holidays'
        unique_together = (('calendar', 'date'),)
        indexes = [models.Index(fields=['date'])]


class WorkScheduleTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)  # ex: 'Standard 8-17'
    tenant_id = models.CharField(max_length=64, db_index=True)
    rules = models.JSONField(default=dict, blank=True)  # {mon:{start:'08:00', end:'17:00', break:60}, ...}

    class Meta:
        db_table = 'hr_work_schedules'
        unique_together = (('tenant_id', 'name'),)


class LeaveRequest(models.Model):
    STATUS = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('cancelled', 'Annulé')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS, default='pending')
    tenant_id = models.CharField(max_length=64, db_index=True)

    # Champs ajoutés
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    number_of_days = models.PositiveIntegerField(help_text="Nombre de jours demandés")
    reason = models.TextField(blank=True, help_text="Motif du congé")

    # Workflow
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_leave_requests'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Fichiers joints
    attachment = models.FileField(
        upload_to='leave_attachments/',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'hr_leave_requests'
        verbose_name = 'Demande de congé'
        verbose_name_plural = 'Demandes de congé'
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['employee', 'start_date']),
            models.Index(fields=['leave_type']),
            models.Index(fields=['requested_at']),
        ]
        ordering = ['-requested_at']
        constraints = [
            models.CheckConstraint(check=models.Q(end_date__gte=models.F('start_date')),
                                   name='leave_dates_order'),
        ]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date} to {self.end_date})"

    def save(self, *args, **kwargs):
        # Calcul automatique du nombre de jours
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.number_of_days = delta.days + 1  # Inclut le jour de début
        super().save(*args, **kwargs)

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def is_pending(self):
        return self.status == 'pending'


class LeaveBalance(models.Model):
    """Solde de congés pour chaque employé"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()

    # Soldes
    total_days = models.PositiveIntegerField(help_text="Jours alloués pour l'année")
    used_days = models.PositiveIntegerField(default=0, help_text="Jours utilisés")
    carried_over_days = models.PositiveIntegerField(default=0, help_text="Jours reportés")

    tenant_id = models.CharField(max_length=64, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("employee", "leave_type", "year"),)
        db_table = 'hr_leave_balances'
        verbose_name = 'Solde de congé'
        verbose_name_plural = 'Soldes de congés'
        indexes = [
            models.Index(fields=['tenant_id', 'year']),
            models.Index(fields=['employee']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.year})"

    @property
    def remaining_days(self):
        return self.total_days + self.carried_over_days - self.used_days

    @property
    def utilization_rate(self):
        if self.total_days + self.carried_over_days > 0:
            return (self.used_days / (self.total_days + self.carried_over_days)) * 100
        return 0


class LeaveApprovalStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_request = models.ForeignKey('LeaveRequest', on_delete=models.CASCADE, related_name='approval_steps')
    step = models.PositiveIntegerField()  # 1,2,...
    approver = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='to_approve_leaves')
    status = models.CharField(max_length=16,
                              choices=[('pending', 'pending'), ('approved', 'approved'), ('rejected', 'rejected')],
                              default='pending')
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_leave_approval_steps'
        unique_together = (('leave_request', 'step'),)
        indexes = [models.Index(fields=['tenant_id', 'status'])]


class Attendance(models.Model):
    """Pointage des employés"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()

    # Heures de pointage
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)

    # Calculs
    worked_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Heures travaillées"
    )
    overtime_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        help_text="Heures supplémentaires"
    )

    # Statut
    STATUS_CHOICES = [
        ('PRESENT', 'Présent'),
        ('ABSENT', 'Absent'),
        ('LATE', 'En retard'),
        ('HALF_DAY', 'Demi-journée'),
        ('LEAVE', 'Congé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')

    # Notes
    notes = models.TextField(blank=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("employee", "date"),)
        db_table = 'hr_attendances'
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        indexes = [
            models.Index(fields=['tenant_id', 'date']),
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['status']),
        ]
        ordering = ['-date', 'employee']
        constraints = [
            models.CheckConstraint(
                check=~(models.Q(check_in__isnull=False) & models.Q(check_out__isnull=False) &
                        models.Q(check_out__lt=models.F('check_in'))),
                name='attendance_checkout_after_checkin'
            ),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.status})"

    def save(self, *args, **kwargs):
        # Calcul automatique des heures travaillées
        if self.check_in and self.check_out:
            from datetime import datetime, timedelta

            # Convertir en datetime pour calcul
            check_in_dt = datetime.combine(self.date, self.check_in)
            check_out_dt = datetime.combine(self.date, self.check_out)

            # Calculer la différence
            delta = check_out_dt - check_in_dt
            hours = delta.total_seconds() / 3600

            # Soustraire la pause déjeuner (1 heure)
            hours = max(0, hours - 1)

            self.worked_hours = round(hours, 2)

            # Calcul des heures supplémentaires (au-delà de 8 heures)
            if hours > 8:
                self.overtime_hours = round(hours - 8, 2)

        super().save(*args, **kwargs)


class Payroll(models.Model):
    """Fiche de paie"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')

    # Période
    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField()

    # Gains
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonuses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Retenues
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    social_security = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Total
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)

    # Statut
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('PROCESSED', 'Traité'),
        ('PAID', 'Payé'),
        ('CANCELLED', 'Annulé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # Références
    payroll_number = models.CharField(max_length=50, unique=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_payrolls'
        verbose_name = 'Fiche de paie'
        verbose_name_plural = 'Fiches de paie'
        indexes = [
            models.Index(fields=['tenant_id', 'period_start']),
            models.Index(fields=['employee', 'period_start']),
            models.Index(fields=['payroll_number']),
            models.Index(fields=['status']),
        ]
        ordering = ['-period_start']
        constraints = [
            models.CheckConstraint(check=models.Q(period_end__gte=models.F('period_start')),
                                   name='payroll_period_order'),
            models.CheckConstraint(check=models.Q(gross_salary__gte=0) & models.Q(net_salary__gte=0),
                                   name='payroll_amounts_non_negative'),
        ]

    def __str__(self):
        return f"Paie {self.payroll_number} - {self.employee}"

    def save(self, *args, **kwargs):
        # Calcul automatique des totaux
        self.gross_salary = self.base_salary + self.overtime_pay + self.bonuses + self.allowances
        self.net_salary = self.gross_salary - self.tax - self.social_security - self.other_deductions
        super().save(*args, **kwargs)


class PerformanceReview(models.Model):
    """Évaluation de performance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performance_reviews')

    # Période d'évaluation
    review_period_start = models.DateField()
    review_period_end = models.DateField()
    review_date = models.DateField()

    # Évaluateur
    reviewer = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='conducted_reviews'
    )

    # Résultats
    overall_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)]
    )
    goals_achievement = models.PositiveIntegerField(
        validators=[MaxValueValidator(100)],
        help_text="Pourcentage d'objectifs atteints"
    )

    # Commentaires
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    goals_next_period = models.TextField(blank=True)

    # Statut
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('IN_REVIEW', 'En revue'),
        ('FINALIZED', 'Finalisé'),
        ('ACKNOWLEDGED', 'Reconnu par employé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_performance_reviews'
        verbose_name = 'Évaluation de performance'
        verbose_name_plural = 'Évaluations de performance'
        indexes = [
            models.Index(fields=['tenant_id', 'review_date']),
            models.Index(fields=['employee', 'review_date']),
            models.Index(fields=['reviewer']),
        ]
        ordering = ['-review_date']

    def __str__(self):
        return f"Évaluation {self.employee} - {self.review_date}"

    @property
    def performance_level(self):
        """Niveau de performance basé sur la note"""
        if self.overall_rating >= 4.5:
            return "Excellent"
        elif self.overall_rating >= 4.0:
            return "Très bon"
        elif self.overall_rating >= 3.0:
            return "Bon"
        elif self.overall_rating >= 2.0:
            return "À améliorer"
        else:
            return "Insuffisant"


class Recruitment(models.Model):
    """Campagne de recrutement"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Intitulé du poste")
    reference = models.CharField(max_length=50, unique=True, help_text="Référence du recrutement")

    # Poste et département
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='recruitments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='recruitments')

    # Description et exigences
    job_description = models.TextField(help_text="Description détaillée du poste")
    requirements = models.JSONField(
        default=dict,
        help_text="Exigences et compétences requises (structurées pour l'IA)"
    )

    # Informations sur le poste
    contract_type = models.CharField(
        max_length=20,
        choices=[
            ('CDI', 'CDI'),
            ('CDD', 'CDD'),
            ('STAGE', 'Stage'),
            ('ALTERNANCE', 'Alternance'),
            ('FREELANCE', 'Freelance'),
        ],
        default='CDI'
    )
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    remote_allowed = models.BooleanField(default=False)

    # Processus de recrutement
    hiring_manager = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='managed_recruitments'
    )
    recruiters = models.ManyToManyField(
        Employee,
        related_name='assigned_recruitments',
        blank=True
    )

    # Statut et dates
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('OPEN', 'Ouvert'),
        ('IN_REVIEW', 'En cours de revue'),
        ('INTERVIEW', 'Phase d entretien'),
        ('OFFER', 'Phase d offre'),
        ('CLOSED', 'Clôturé'),
        ('CANCELLED', 'Annulé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    publication_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    target_hiring_date = models.DateField(null=True, blank=True)

    # Métriques
    number_of_positions = models.PositiveIntegerField(default=1)

    # Configuration IA
    ai_scoring_enabled = models.BooleanField(default=True)
    ai_scoring_criteria = models.JSONField(
        default=dict,
        help_text="Critères de scoring IA personnalisés"
    )
    minimum_ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Score minimum pour la présélection IA"
    )

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_recruitments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'reference']),
            models.Index(fields=['position']),
            models.Index(fields=['publication_date']),
        ]
        unique_together = (('tenant_id', 'reference'),)
        constraints = [
            models.CheckConstraint(
                check=~(
                        models.Q(salary_min__isnull=False) &
                        models.Q(salary_max__isnull=False) &
                        models.Q(salary_min__gt=models.F('salary_max'))
                ),
                name='recruit_salary_min_le_max'
            ),
            models.CheckConstraint(
                check=~(
                        models.Q(publication_date__isnull=False) &
                        models.Q(closing_date__isnull=False) &
                        models.Q(closing_date__lt=models.F('publication_date'))
                ),
                name='recruit_close_ge_publish'
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.reference})"

    @property
    def is_active(self):
        return self.status in ['OPEN', 'IN_REVIEW', 'INTERVIEW', 'OFFER']

    @property
    def applications_count(self):
        return self.applications.count()

    @property
    def applications_pending_review(self):
        return self.applications.filter(status='APPLIED').count()

    def clean(self):
        errors = {}
        if self.position and self.position.tenant_id != self.tenant_id:
            errors['position'] = "Le poste n'appartient pas au même tenant."
        if self.department and self.department.tenant_id != self.tenant_id:
            errors['department'] = "Le département n'appartient pas au même tenant."
        if self.hiring_manager and self.hiring_manager.tenant_id != self.tenant_id:
            errors['hiring_manager'] = "Le manager n'appartient pas au même tenant."
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)


def upload_to_per_tenant(prefix):
    import os
    def _path(instance, filename):
        tenant = getattr(instance, 'tenant_id', 'public')
        name = os.path.basename(filename)
        return f"{tenant}/{prefix}/{uuid.uuid4()}_{name}"

    return _path


class JobApplication(models.Model):
    """Candidature à un poste"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recruitment = models.ForeignKey(
        Recruitment,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    # Informations du candidat
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)

    # Documents
    cv = models.FileField(upload_to=TenantPath('job_applications/cv'))
    cover_letter = models.FileField(upload_to=TenantPath('job_applications/cover_letters'), null=True, blank=True)
    portfolio = models.FileField(upload_to=TenantPath('job_applications/portfolios'), null=True, blank=True)

    # Données extraites (remplissage automatique via IA)
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données extraites des documents par IA"
    )

    # Scoring IA
    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Score de matching IA (0-100)"
    )
    ai_feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feedback détaillé de l'IA"
    )

    # Statut de la candidature
    STATUS_CHOICES = [
        ('APPLIED', 'Postulé'),
        ('AI_SCREENED', 'Présélectionné IA'),
        ('AI_REJECTED', 'Rejeté IA'),
        ('HR_REVIEW', 'En revue RH'),
        ('SHORTLISTED', 'Présélectionné'),
        ('INTERVIEW_1', 'Entretien 1'),
        ('INTERVIEW_2', 'Entretien 2'),
        ('INTERVIEW_3', 'Entretien 3'),
        ('REFERENCE_CHECK', 'Vérification références'),
        ('OFFERED', 'Offre faite'),
        ('HIRED', 'Embauché'),
        ('REJECTED', 'Rejeté'),
        ('WITHDRAWN', 'Retiré'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')

    # Suivi
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Notes internes
    internal_notes = models.TextField(blank=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_job_applications'
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['recruitment', 'applied_at']),
            models.Index(fields=['ai_score']),
            models.Index(fields=['email']),
        ]
        unique_together = (('recruitment', 'email'),)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.recruitment.title}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_ai_approved(self):
        return self.ai_score and self.ai_score >= self.recruitment.minimum_ai_score

    @property
    def days_since_application(self):
        delta = timezone.now() - self.applied_at
        return delta.days

    def clean(self):
        errors = {}
        if self.recruitment and self.tenant_id != self.recruitment.tenant_id:
            errors['tenant_id'] = "La candidature doit porter le même tenant que le recrutement."
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)


class AIProcessingResult(models.Model):
    """Résultats du traitement IA des candidatures"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application = models.OneToOneField(
        JobApplication,
        on_delete=models.CASCADE,
        related_name='ai_processing'
    )

    # Données extraites du CV
    extracted_skills = models.JSONField(
        default=list,
        help_text="Compétences extraites du CV"
    )
    extracted_experience = models.JSONField(
        default=list,
        help_text="Expériences professionnelles extraites"
    )
    extracted_education = models.JSONField(
        default=list,
        help_text="Formations extraites"
    )
    extracted_languages = models.JSONField(
        default=list,
        help_text="Langues extraites"
    )

    # Analyse de matching
    skills_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    experience_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    education_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    overall_match_score = models.DecimalField(max_digits=5, decimal_places=2)

    # Analyse détaillée
    missing_skills = models.JSONField(default=list)
    strong_skills = models.JSONField(default=list)
    experience_gaps = models.JSONField(default=list)
    red_flags = models.JSONField(default=list)

    # Métadonnées du traitement
    processing_time = models.DecimalField(max_digits=8, decimal_places=3, help_text="Temps de traitement en secondes")
    ai_model_version = models.CharField(max_length=50, default="v1.0")
    processed_at = models.DateTimeField(auto_now_add=True)

    # Statut
    PROCESSING_STATUS = [
        ('PENDING', 'En attente'),
        ('PROCESSING', 'En cours'),
        ('COMPLETED', 'Terminé'),
        ('FAILED', 'Échec'),
    ]
    status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='PENDING')
    error_message = models.TextField(blank=True)

    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_ai_processing_results'
        verbose_name = 'Résultat traitement IA'
        verbose_name_plural = 'Résultats traitement IA'
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['processed_at']),
            models.Index(fields=['overall_match_score']),
        ]

    def __str__(self):
        return f"IA Analysis - {self.job_application}"


class Interview(models.Model):
    """Entretien de recrutement"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name='interviews'
    )

    # Type d'entretien
    INTERVIEW_TYPES = [
        ('PHONE', 'Téléphonique'),
        ('VIDEO', 'Visioconférence'),
        ('IN_PERSON', 'En présentiel'),
        ('TECHNICAL', 'Technique'),
        ('HR', 'RH'),
        ('MANAGER', 'Manager'),
        ('FINAL', 'Final'),
    ]
    interview_type = models.CharField(max_length=20, choices=INTERVIEW_TYPES, default='HR')

    # Participants
    interviewers = models.ManyToManyField(Employee, related_name='interviews_to_conduct')
    candidate = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='interview_schedule')

    # Planning
    scheduled_date = models.DateTimeField()
    duration = models.PositiveIntegerField(help_text="Durée en minutes", default=60)
    location = models.CharField(max_length=200, blank=True)
    meeting_link = models.URLField(blank=True, help_text="Lien pour les entretiens à distance")

    # Préparation
    interview_guide = models.TextField(blank=True, help_text="Guide d'entretien")
    key_points_to_assess = models.JSONField(
        default=list,
        help_text="Points clés à évaluer"
    )

    # Résultats
    conducted_at = models.DateTimeField(null=True, blank=True)
    interviewer_feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feedback structuré des interviewers"
    )
    overall_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)]
    )
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('STRONG_HIRE', 'Fortement recommandé'),
            ('HIRE', 'Recommandé'),
            ('NO_HIRE', 'Non recommandé'),
            ('NEUTRAL', 'Neutre'),
        ],
        blank=True
    )
    notes = models.TextField(blank=True)

    # Statut
    STATUS_CHOICES = [
        ('SCHEDULED', 'Planifié'),
        ('CONFIRMED', 'Confirmé'),
        ('IN_PROGRESS', 'En cours'),
        ('COMPLETED', 'Terminé'),
        ('CANCELLED', 'Annulé'),
        ('NO_SHOW', 'Candidat absent'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_interviews'
        ordering = ['scheduled_date']
        indexes = [
            models.Index(fields=['tenant_id', 'scheduled_date']),
            models.Index(fields=['job_application']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration__gt=0),
                name='interview_duration_positive'
            ),
        ]

    def __str__(self):
        return f"Entretien {self.interview_type} - {self.job_application}"

    @property
    def is_past_due(self):
        return self.scheduled_date < timezone.now() and self.status in ['SCHEDULED', 'CONFIRMED']

    def clean(self):
        errors = {}
        if self.job_application and self.tenant_id != self.job_application.tenant_id:
            errors['tenant_id'] = "L'entretien doit porter le même tenant que la candidature."
        if self.conducted_at and self.conducted_at < self.scheduled_date:
            errors['conducted_at'] = "La date de réalisation ne peut pas précéder la planification."
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)


class InterviewFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey('Interview', on_delete=models.CASCADE, related_name='feedbacks')
    interviewer = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='given_feedbacks')
    criteria = models.JSONField(default=dict, blank=True)  # {'communication':4.0, 'tech':4.5, ...}
    summary = models.TextField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1,
                                 validators=[MinValueValidator(1.0), MaxValueValidator(5.0)])
    created_at = models.DateTimeField(auto_now_add=True)
    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_interview_feedbacks'
        unique_together = (('interview', 'interviewer'),)
        indexes = [models.Index(fields=['tenant_id', 'interviewer']), ]


class RecruitmentAnalytics(models.Model):
    """Analytiques pour le recrutement"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recruitment = models.OneToOneField(
        Recruitment,
        on_delete=models.CASCADE,
        related_name='analytics'
    )

    # Métriques de base
    total_applications = models.PositiveIntegerField(default=0)
    ai_screened_applications = models.PositiveIntegerField(default=0)
    ai_rejected_applications = models.PositiveIntegerField(default=0)
    hr_reviewed_applications = models.PositiveIntegerField(default=0)
    interviews_scheduled = models.PositiveIntegerField(default=0)
    offers_made = models.PositiveIntegerField(default=0)
    hires = models.PositiveIntegerField(default=0)

    # Métriques temporelles
    average_processing_time = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Temps moyen de traitement en heures"
    )
    time_to_hire = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Temps moyen d'embauche en jours"
    )

    # Efficacité IA
    ai_accuracy_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Taux de précision de l'IA (%)"
    )
    ai_false_positives = models.PositiveIntegerField(default=0)
    ai_false_negatives = models.PositiveIntegerField(default=0)

    # Sources de candidatures
    application_sources = models.JSONField(
        default=dict,
        help_text="Répartition par source de candidature"
    )

    # Dernière mise à jour
    last_calculated = models.DateTimeField(auto_now=True)

    tenant_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'hr_recruitment_analytics'
        verbose_name = 'Analytique recrutement'
        verbose_name_plural = 'Analytiques recrutement'

    def __str__(self):
        return f"Analytics - {self.recruitment.title}"

    @property
    def conversion_rate(self):
        if self.total_applications > 0:
            return (self.hires / self.total_applications) * 100
        return 0

    @property
    def ai_efficiency(self):
        if self.total_applications > 0:
            return (self.ai_screened_applications / self.total_applications) * 100
        return 0


class JobOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='offer')
    title = models.CharField(max_length=200, help_text="Intitulé du poste proposé")
    proposed_salary = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    contract_type = models.CharField(max_length=20)  # aligner avec Recruitment.contract_type
    offer_pdf = models.FileField(upload_to=TenantPath('offers'), null=True, blank=True)
    status = models.CharField(max_length=20,
                              choices=[('DRAFT', 'Brouillon'), ('SENT', 'Envoyée'), ('ACCEPTED', 'Acceptée'),
                                       ('DECLINED', 'Refusée'), ('EXPIRED', 'Expirée')], default='DRAFT')
    sent_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hr_job_offers'
        indexes = [models.Index(fields=['tenant_id', 'status']), ]


class RecruitmentWorkflow(models.Model):
    """Workflow personnalisable de recrutement"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Étapes du workflow
    stages = models.JSONField(
        default=list,
        help_text="Étapes personnalisées du processus de recrutement"
    )

    # Configuration IA
    ai_scoring_weights = models.JSONField(
        default=dict,
        help_text="Pondérations pour le scoring IA"
    )

    # Modèles d'email automatiques
    email_templates = models.JSONField(
        default=dict,
        help_text="Templates d'email pour chaque étape"
    )

    # Actif par défaut
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    tenant_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hr_recruitment_workflows'
        verbose_name = 'Workflow recrutement'
        verbose_name_plural = 'Workflows recrutement'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'un seul workflow par défaut
        if self.is_default:
            RecruitmentWorkflow.objects.filter(
                tenant_id=self.tenant_id,
                is_default=True
            ).update(is_default=False)
        super().save(*args, **kwargs)
