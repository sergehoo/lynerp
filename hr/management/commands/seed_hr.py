import random
import uuid
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import uuid
from faker import Faker

from tenants.models import Tenant
from hr.models import (
    Department, Position, Employee,
    ContractType, EmploymentContract, ContractAmendment, ContractAlert, ContractHistory,
    SalaryHistory, HRDocument,
    LeaveType, LeaveBalance, LeaveRequest, LeaveApprovalStep,
    MedicalRecord, MedicalVisit, MedicalRestriction,
    Attendance, Payroll, PerformanceReview,
    Recruitment, JobApplication, AIProcessingResult, Interview, InterviewFeedback,
    RecruitmentAnalytics, JobOffer, RecruitmentWorkflow
)

fake = Faker("fr_FR")


def rand_date_between(start: date, end: date) -> date:
    if start >= end:
        return start
    days = (end - start).days
    return start + timedelta(days=random.randint(0, days))


class Command(BaseCommand):
    help = "Seed HR fake data (Employees, Contracts, Leaves, Payroll, Recruitment, etc.)"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, default=None, help="Tenant UUID/id (optional)")
        parser.add_argument("--n", type=int, default=100, help="Number of employees to create (default 100)")
        parser.add_argument("--purge", action="store_true",
                            help="Delete existing HR data for this tenant_id before seeding")

    @transaction.atomic
    def handle(self, *args, **opts):
        n = int(opts["n"])
        tenant_arg = opts["tenant"]
        purge = bool(opts["purge"])

        tenant = self._get_or_create_tenant(tenant_arg)
        tenant_id_str = str(getattr(tenant, "id", tenant.pk))

        self.stdout.write(self.style.SUCCESS(f"✅ Tenant: {tenant} | tenant_id={tenant_id_str}"))
        self.stdout.write(self.style.WARNING(f"Seeding {n} employees..."))

        if purge:
            self._purge(tenant, tenant_id_str)

        # 1) Workflows recrutement
        workflows = self._create_recruitment_workflows(tenant_id_str)

        # 2) Types congés
        leave_types = self._create_leave_types(tenant_id_str)

        # 3) Contract types
        contract_types = self._create_contract_types(tenant_id_str)

        # 4) Départements + Positions
        departments = self._create_departments(tenant)
        positions = self._create_positions(tenant, departments)

        # 5) Employees
        employees = self._create_employees(tenant, departments, positions, n)

        # 6) Donner des managers (dept.manager) après création employees
        self._assign_department_managers(departments, employees)

        # 7) Contrats + avenants + alertes + historique
        contracts = self._create_contracts(tenant_id_str, employees, departments, positions, contract_types)

        # 8) Salary history + docs
        self._create_salary_history(tenant_id_str, employees)
        self._create_documents(tenant_id_str, employees)

        # 9) Congés: balances + requests + approval steps
        self._create_leave_balances(tenant_id_str, employees, leave_types)
        self._create_leave_requests(tenant_id_str, employees, leave_types)

        # 10) Medical
        self._create_medical(tenant_id_str, employees)

        # 11) Attendance
        self._create_attendance(tenant_id_str, employees)

        # 12) Payroll
        self._create_payrolls(tenant_id_str, employees)

        # 13) Performance reviews
        self._create_performance_reviews(tenant_id_str, employees)

        # 14) Recruitment + apps + IA + interviews + feedback + analytics + offers
        self._create_recruitment_pipeline(tenant, tenant_id_str, departments, positions, employees, workflows)

        self.stdout.write(self.style.SUCCESS("🎉 Seed terminé avec succès."))

    # -------------------------
    # Tenant + purge
    # -------------------------
    def _get_or_create_tenant(self, tenant_arg):
        if tenant_arg:
            t = Tenant.objects.filter(id=tenant_arg).first()
            if t:
                return t
            # si ton PK n'est pas UUIDField, fallback:
            t = Tenant.objects.filter(pk=tenant_arg).first()
            if t:
                return t

        # fallback : premier tenant ou création rapide
        t = Tenant.objects.first()
        if t:
            return t

        # adapte les champs obligatoires de ton modèle Tenant si besoin
        return Tenant.objects.create(
            name="Demo Tenant",
            slug="demo-tenant",
        )

    def _purge(self, tenant, tenant_id_str: str):
        self.stdout.write(self.style.WARNING("⚠️ Purge des données existantes (tenant scope)..."))

        tenant_uuid = None
        try:
            tenant_uuid = uuid.UUID(str(tenant_id_str))
        except Exception:
            pass

        # --- Tables avec tenant_id en CharField ---
        InterviewFeedback.objects.filter(tenant_id=tenant_id_str).delete()
        Interview.objects.filter(tenant_id=tenant_id_str).delete()
        AIProcessingResult.objects.filter(tenant_id=tenant_id_str).delete()
        JobOffer.objects.filter(tenant_id=tenant_id_str).delete()
        RecruitmentAnalytics.objects.filter(tenant_id=tenant_id_str).delete()
        JobApplication.objects.filter(tenant_id=tenant_id_str).delete()
        RecruitmentWorkflow.objects.filter(tenant_id=tenant_id_str).delete()

        Payroll.objects.filter(tenant_id=tenant_id_str).delete()
        Attendance.objects.filter(tenant_id=tenant_id_str).delete()
        PerformanceReview.objects.filter(tenant_id=tenant_id_str).delete()

        MedicalRestriction.objects.filter(tenant_id=tenant_id_str).delete()
        MedicalVisit.objects.filter(tenant_id=tenant_id_str).delete()
        MedicalRecord.objects.filter(tenant_id=tenant_id_str).delete()

        LeaveApprovalStep.objects.filter(tenant_id=tenant_id_str).delete()
        LeaveRequest.objects.filter(tenant_id=tenant_id_str).delete()
        LeaveBalance.objects.filter(tenant_id=tenant_id_str).delete()
        LeaveType.objects.filter(tenant_id=tenant_id_str).delete()

        HRDocument.objects.filter(tenant_id=tenant_id_str).delete()
        SalaryHistory.objects.filter(tenant_id=tenant_id_str).delete()

        ContractHistory.objects.filter(tenant_id=tenant_id_str).delete()
        ContractAlert.objects.filter(tenant_id=tenant_id_str).delete()
        ContractAmendment.objects.filter(tenant_id=tenant_id_str).delete()
        EmploymentContract.objects.filter(tenant_id=tenant_id_str).delete()
        ContractType.objects.filter(tenant_id=tenant_id_str).delete()

        # --- Recruitment: en base, tenant_id semble être UUID -> filtrer en UUID ---
        if tenant_uuid:
            Recruitment.objects.filter(tenant_id=tenant_uuid).delete()
        else:
            # fallback si DB est finalement varchar
            Recruitment.objects.filter(tenant_id=tenant_id_str).delete()

        # --- Parents (tenant FK) ---
        Employee.objects.filter(tenant=tenant).delete()
        Position.objects.filter(tenant=tenant).delete()
        Department.objects.filter(tenant=tenant).delete()

        self.stdout.write(self.style.SUCCESS("✅ Purge terminée."))

    # -------------------------
    # Seed blocks
    # -------------------------
    def _create_recruitment_workflows(self, tenant_id_str):
        workflows = []
        for i in range(2):
            workflows.append(RecruitmentWorkflow(
                name=f"Workflow Standard {i + 1}",
                description="Processus standard de recrutement",
                stages=[
                    {"code": "APPLIED", "label": "Postulé"},
                    {"code": "AI_SCREENED", "label": "Présélection IA"},
                    {"code": "HR_REVIEW", "label": "Revue RH"},
                    {"code": "INTERVIEW_1", "label": "Entretien 1"},
                    {"code": "OFFERED", "label": "Offre"},
                    {"code": "HIRED", "label": "Embauché"},
                ],
                ai_scoring_weights={"skills": 0.5, "experience": 0.3, "education": 0.2},
                email_templates={
                    "APPLIED": "Merci pour votre candidature.",
                    "REJECTED": "Nous ne donnons pas suite.",
                    "OFFERED": "Nous sommes heureux de vous faire une offre.",
                },
                is_default=(i == 0),
                is_active=True,
                tenant_id=tenant_id_str,
            ))
        RecruitmentWorkflow.objects.bulk_create(workflows)
        return list(RecruitmentWorkflow.objects.filter(tenant_id=tenant_id_str))

    def _create_leave_types(self, tenant_id_str):
        base = [
            ("Congé annuel", "ANNUAL", 30, True),
            ("Maladie", "SICK", 10, True),
            ("Maternité", "MAT", 90, True),
            ("Sans solde", "UNPAID", 30, False),
        ]
        items = []
        for name, code, max_days, paid in base:
            items.append(LeaveType(
                name=name,
                code=code + "-" + tenant_id_str[:6],  # éviter collisions
                description=f"{name} - auto seed",
                max_days=max_days,
                is_paid=paid,
                requires_approval=True,
                carry_over=(code == "ANNUAL"),
                carry_over_max=5 if code == "ANNUAL" else 0,
                tenant_id=tenant_id_str,
                is_active=True,
            ))
        LeaveType.objects.bulk_create(items)
        return list(LeaveType.objects.filter(tenant_id=tenant_id_str))

    def _create_contract_types(self, tenant_id_str):
        # ⚠️ ton ContractType.code est unique=True (global) => codes doivent être globalement uniques
        base = [
            ("CDI", "CT_CDI"),
            ("CDD", "CT_CDD"),
            ("STAGE", "CT_STAGE"),
        ]
        items = []
        for name, code in base:
            items.append(ContractType(
                name=name,
                code=f"{code}_{tenant_id_str[:6]}_{uuid.uuid4().hex[:6]}",
                description=f"Type {name} seed",
                is_permanent=(name == "CDI"),
                has_probation=True,
                default_probation_days=90 if name != "STAGE" else 30,
                requires_approval=True,
                legal_reference="AUTO",
                minimum_salary=None,
                maximum_hours=40,
                tenant_id=tenant_id_str,
                is_active=True,
            ))
        ContractType.objects.bulk_create(items)
        return list(ContractType.objects.filter(tenant_id=tenant_id_str))

    def _create_departments(self, tenant):
        names = ["Direction", "RH", "Finance", "IT", "Opérations", "Commercial", "Marketing", "Support"]
        depts = []
        for nm in names:
            depts.append(Department(
                name=nm,
                parent=None,
                tenant=tenant,
                code=nm[:3].upper(),
                description=f"Département {nm}",
                is_active=True,
            ))
        Department.objects.bulk_create(depts)

        # hiérarchie simple: quelques sous-depts sous "Direction"
        direction = Department.objects.filter(tenant=tenant, name="Direction").first()
        if direction:
            subs = ["Juridique", "Audit", "Qualité"]
            for nm in subs:
                Department.objects.get_or_create(
                    tenant=tenant,
                    name=nm,
                    defaults={"parent": direction, "code": nm[:3].upper(), "description": f"Sous-département {nm}"}
                )
        return list(Department.objects.filter(tenant=tenant))

    def _create_positions(self, tenant, departments):
        titles = [
            "Assistant", "Analyste", "Ingénieur", "Chef de projet", "Manager", "Directeur",
            "Comptable", "Développeur", "Admin Système", "Chargé RH", "Commercial"
        ]
        levels = ["INTERN", "JUNIOR", "MID", "SENIOR", "LEAD", "MANAGER", "DIRECTOR"]
        positions = []
        for d in departments:
            for _ in range(random.randint(2, 5)):
                title = random.choice(titles)
                positions.append(Position(
                    title=f"{title} {d.code}",
                    code=f"{d.code}-{uuid.uuid4().hex[:4]}",
                    department=d,
                    description=f"Poste {title} dans {d.name}",
                    salary_min=random.randint(200_000, 600_000),
                    salary_max=random.randint(700_000, 2_000_000),
                    level=random.choice(levels),
                    tenant=tenant,
                    is_active=True,
                ))
        Position.objects.bulk_create(positions)
        return list(Position.objects.filter(tenant=tenant))

    def _create_employees(self, tenant, departments, positions, n):
        employees = []
        used_matricules = set()
        used_emails = set()

        start_hire_min = date.today().replace(year=date.today().year - 10)
        for i in range(n):
            first = fake.first_name()
            last = fake.last_name()
            email = f"{first}.{last}.{uuid.uuid4().hex[:6]}@example.com".lower()
            while email in used_emails:
                email = f"{first}.{last}.{uuid.uuid4().hex[:6]}@example.com".lower()

            matricule = f"EMP{date.today().year}{random.randint(1000, 9999)}{i}"
            while matricule in used_matricules:
                matricule = f"EMP{date.today().year}{random.randint(1000, 9999)}{uuid.uuid4().hex[:2]}"

            dept = random.choice(departments)
            pos = random.choice([p for p in positions if p.department_id == dept.id] or positions)

            hire = rand_date_between(start_hire_min, date.today() - timedelta(days=30))
            dob = rand_date_between(date.today().replace(year=date.today().year - 55),
                                    date.today().replace(year=date.today().year - 20))

            employees.append(Employee(
                tenant=tenant,
                matricule=matricule,
                first_name=first,
                last_name=last,
                email=email,
                department=dept,
                hire_date=hire,
                contract_type=None,
                extra={"seed": True},
                position=pos,
                date_of_birth=dob,
                gender=random.choice(["M", "F", "O"]),
                phone=fake.phone_number(),
                address=fake.address(),
                emergency_contact={
                    "name": fake.name(),
                    "phone": fake.phone_number(),
                    "relation": random.choice(["Parent", "Conjoint", "Frère/Soeur", "Ami"]),
                },
                salary=random.randint(250_000, 2_500_000),
                work_schedule=random.choice(["FULL_TIME", "PART_TIME", "FLEXIBLE"]),
                is_active=random.random() > 0.05,
                termination_date=None,
                termination_reason="",
            ))
            used_matricules.add(matricule)
            used_emails.add(email)

        Employee.objects.bulk_create(employees)
        return list(Employee.objects.filter(tenant=tenant))

    def _assign_department_managers(self, departments, employees):
        for d in departments:
            # 1 manager aléatoire
            mgr = random.choice(employees)
            Department.objects.filter(id=d.id).update(manager=mgr)

    def _create_contracts(self, tenant_id_str, employees, departments, positions, contract_types):
        contracts = []
        today = timezone.now().date()

        for e in employees:
            # 1 à 2 contrats
            nb = 1 if random.random() < 0.8 else 2
            start_base = e.hire_date
            for k in range(nb):
                ct = random.choice(contract_types)
                start = start_base + timedelta(days=365 * k)
                if start > today:
                    start = today - timedelta(days=random.randint(30, 365))

                is_cdi = ct.is_permanent
                end = None
                if not is_cdi:
                    end = start + timedelta(days=random.randint(120, 365))

                probation_start = start
                probation_days = ct.default_probation_days or 90
                probation_end = probation_start + timedelta(days=probation_days)

                dept = e.department or random.choice(departments)
                pos = e.position or random.choice(positions)

                contract = EmploymentContract(
                    employee=e,
                    contract_type=ct,
                    contract_number=f"CT{today.year}{uuid.uuid4().hex[:10].upper()}",
                    title=pos.title if pos else f"Poste {dept.name}",
                    department=dept,
                    position=pos,
                    start_date=start,
                    end_date=end,
                    expected_end_date=end,
                    probation_start_date=probation_start,
                    probation_end_date=probation_end,
                    probation_duration_days=probation_days,
                    base_salary=random.randint(250_000, 2_500_000),
                    salary_currency="XOF",
                    salary_frequency="MONTHLY",
                    weekly_hours=40.0,
                    work_schedule=None,
                    work_location=random.choice(["Abidjan", "Bouaké", "San-Pédro", "Yamoussoukro"]),
                    remote_allowed=random.random() < 0.2,
                    remote_days_per_week=random.randint(0, 3),
                    status="ACTIVE" if (start <= today and (end is None or end >= today)) else random.choice(
                        ["EXPIRED", "TERMINATED", "SUSPENDED"]),
                    termination_reason="",
                    termination_date=None,
                    termination_type="",
                    contract_document=None,
                    amendment_document=None,
                    signed_by_employee=random.random() < 0.9,
                    signed_by_employer=random.random() < 0.95,
                    signed_date=start + timedelta(days=random.randint(0, 15)),
                    approved_by=None,
                    approved_at=None,
                    tenant_id=tenant_id_str,
                    created_by=None,
                )
                contracts.append(contract)

        EmploymentContract.objects.bulk_create(contracts)
        contracts = list(EmploymentContract.objects.filter(tenant_id=tenant_id_str).select_related("employee"))

        # Amendments + Alerts + History
        amendments = []
        alerts = []
        histories = []

        for c in random.sample(contracts, k=min(len(contracts), max(10, len(contracts) // 5))):
            if random.random() < 0.6:
                amendments.append(ContractAmendment(
                    contract=c,
                    amendment_number=f"AMD-{uuid.uuid4().hex[:6].upper()}",
                    amendment_type=random.choice(["SALARY", "POSITION", "SCHEDULE", "LOCATION", "DURATION", "OTHER"]),
                    description=fake.text(max_nb_chars=120),
                    effective_date=c.start_date + timedelta(days=random.randint(30, 200)),
                    previous_data={"base_salary": str(c.base_salary)},
                    new_data={"base_salary": str(int(c.base_salary) + random.randint(50_000, 300_000))},
                    status=random.choice(["DRAFT", "PENDING_SIGNATURE", "SIGNED"]),
                    amendment_document=None,
                    signed_by_employee=random.random() < 0.7,
                    signed_by_employer=random.random() < 0.7,
                    signed_date=None,
                    tenant_id=tenant_id_str,
                    created_by=None,
                ))

            # alerts
            if c.end_date:
                alerts.append(ContractAlert(
                    contract=c,
                    alert_type="CONTRACT_END",
                    title="Fin de contrat",
                    message="Contrat proche de l'échéance.",
                    due_date=c.end_date,
                    priority=random.choice(["LOW", "MEDIUM", "HIGH"]),
                    status=random.choice(["PENDING", "IN_PROGRESS", "RESOLVED"]),
                    assigned_to=random.choice(employees),
                    tenant_id=tenant_id_str,
                    resolved_at=None,
                ))
            if c.probation_end_date:
                alerts.append(ContractAlert(
                    contract=c,
                    alert_type="PROBATION_END",
                    title="Fin période d'essai",
                    message="Période d'essai proche de la fin.",
                    due_date=c.probation_end_date,
                    priority=random.choice(["MEDIUM", "HIGH"]),
                    status=random.choice(["PENDING", "RESOLVED"]),
                    assigned_to=random.choice(employees),
                    tenant_id=tenant_id_str,
                    resolved_at=None,
                ))

            # history
            histories.append(ContractHistory(
                contract=c,
                action="CREATED",
                description="Contrat créé (seed).",
                changes={"start_date": str(c.start_date), "end_date": str(c.end_date) if c.end_date else None},
                performed_by=None,
                tenant_id=tenant_id_str,
            ))

        if amendments:
            ContractAmendment.objects.bulk_create(amendments)
        if alerts:
            ContractAlert.objects.bulk_create(alerts)
        if histories:
            ContractHistory.objects.bulk_create(histories)

        return contracts

    def _create_salary_history(self, tenant_id_str, employees):
        items = []
        for e in random.sample(employees, k=min(len(employees), 80)):
            base = int(e.salary or random.randint(250_000, 1_500_000))
            # 2 entrées
            d1 = e.hire_date + timedelta(days=180)
            d2 = e.hire_date + timedelta(days=540)
            items.append(SalaryHistory(employee=e, effective_date=d1, gross_salary=base, reason="Embauche",
                                       tenant_id=tenant_id_str))
            items.append(
                SalaryHistory(employee=e, effective_date=d2, gross_salary=base + random.randint(50_000, 400_000),
                              reason="Augmentation", tenant_id=tenant_id_str))
        SalaryHistory.objects.bulk_create(items, ignore_conflicts=True)

    def _create_documents(self, tenant_id_str, employees):
        # On évite de créer de vrais fichiers (FileField). On laisse file vide => pas possible sans storage.
        # Si tu veux des fichiers, il faut un fichier réel via SimpleUploadedFile.
        cats = ["contract", "id", "medical", "other"]
        items = []
        for e in random.sample(employees, k=min(len(employees), 50)):
            # HRDocument.file est obligatoire => on skip si tu ne fournis pas de vrai fichier.
            # On te laisse un exemple commenté si tu veux activer.
            # from django.core.files.uploadedfile import SimpleUploadedFile
            # f = SimpleUploadedFile("doc.txt", b"seed", content_type="text/plain")
            # items.append(HRDocument(employee=e, category="other", file=f, title="Doc seed", tenant_id=tenant_id_str))
            pass
        # if items: HRDocument.objects.bulk_create(items)

    def _create_leave_balances(self, tenant_id_str, employees, leave_types):
        year = timezone.now().year
        items = []
        for e in employees:
            for lt in leave_types:
                total = lt.max_days
                carried = random.randint(0, lt.carry_over_max or 0) if lt.carry_over else 0
                used = random.randint(0, max(0, total + carried))
                items.append(LeaveBalance(
                    employee=e,
                    leave_type=lt,
                    year=year,
                    total_days=total,
                    used_days=min(used, total + carried),
                    carried_over_days=carried,
                    tenant_id=tenant_id_str,
                ))
        LeaveBalance.objects.bulk_create(items, ignore_conflicts=True)

    def _create_leave_requests(self, tenant_id_str, employees, leave_types):
        items = []
        steps = []
        for e in random.sample(employees, k=min(len(employees), 80)):
            for _ in range(random.randint(0, 2)):
                lt = random.choice(leave_types)
                start = rand_date_between(date.today() - timedelta(days=240), date.today() + timedelta(days=60))
                end = start + timedelta(days=random.randint(1, 10))
                status = random.choice(["pending", "approved", "rejected", "cancelled"])
                lr = LeaveRequest(
                    employee=e,
                    start_date=start,
                    end_date=end,
                    status=status,
                    tenant_id=tenant_id_str,
                    leave_type=lt,
                    number_of_days=1,  # recalculé en save()
                    reason=fake.sentence(),
                    approved_by=random.choice(employees) if status == "approved" else None,
                    approved_at=timezone.now() if status == "approved" else None,
                    rejection_reason=fake.sentence() if status == "rejected" else "",
                    attachment=None,
                )
                items.append(lr)

        # save un par un (car LeaveRequest.save calcule number_of_days)
        for lr in items:
            lr.save()
            # steps
            nb_steps = 1 if random.random() < 0.8 else 2
            for s in range(1, nb_steps + 1):
                steps.append(LeaveApprovalStep(
                    leave_request=lr,
                    step=s,
                    approver=random.choice(employees),
                    status=random.choice(["pending", "approved", "rejected"]),
                    decided_at=timezone.now() if lr.status in ["approved", "rejected"] else None,
                    comment=fake.sentence(),
                    tenant_id=tenant_id_str,
                ))
        if steps:
            LeaveApprovalStep.objects.bulk_create(steps)

    def _create_medical(self, tenant_id_str, employees):
        # record 60% des employés
        records = []
        visits = []
        restrictions = []

        for e in random.sample(employees, k=min(len(employees), int(len(employees) * 0.6))):
            records.append(MedicalRecord(
                employee=e,
                blood_type=random.choice(["O+", "O-", "A+", "A-", "B+", "AB+"]),
                allergies=random.sample(["Pollen", "Arachide", "Lactose", "Aucune"], k=1),
                chronic_conditions=random.sample(["Asthme", "Diabète", "HTA", "Aucune"], k=1),
                emergency_notes="RAS" if random.random() < 0.7 else fake.sentence(),
                tenant_id=tenant_id_str,
            ))
        MedicalRecord.objects.bulk_create(records, ignore_conflicts=True)

        for e in random.sample(employees, k=min(len(employees), 40)):
            for _ in range(random.randint(0, 2)):
                visits.append(MedicalVisit(
                    employee=e,
                    visit_date=rand_date_between(date.today() - timedelta(days=700), date.today()),
                    provider=random.choice(["Clinique", "Médecin du travail", "CHU"]),
                    diagnosis=random.choice(["RAS", "Grippe", "Douleurs lombaires", "Migraine"]),
                    notes=fake.sentence(),
                    attachments=[],
                    tenant_id=tenant_id_str,
                ))
            if random.random() < 0.2:
                restrictions.append(MedicalRestriction(
                    employee=e,
                    start_date=rand_date_between(date.today() - timedelta(days=365), date.today()),
                    end_date=None if random.random() < 0.5 else date.today() + timedelta(days=random.randint(30, 180)),
                    restriction="Aménagement horaire / Poste adapté",
                    is_active=True,
                    tenant_id=tenant_id_str,
                ))

        if visits:
            MedicalVisit.objects.bulk_create(visits)
        if restrictions:
            MedicalRestriction.objects.bulk_create(restrictions)

    def _create_attendance(self, tenant_id_str, employees):
        items = []
        today = date.today()
        for e in employees:
            # 20 jours aléatoires sur les 60 derniers
            days = random.sample(range(0, 60), k=20)
            for d in days:
                day = today - timedelta(days=d)
                status = random.choices(
                    ["PRESENT", "ABSENT", "LATE", "HALF_DAY", "LEAVE"],
                    weights=[75, 5, 10, 5, 5],
                    k=1
                )[0]
                check_in = None
                check_out = None
                if status in ["PRESENT", "LATE", "HALF_DAY"]:
                    hour_in = 8 if status != "LATE" else 9
                    check_in = (timezone.datetime.combine(day, timezone.datetime.min.time()).replace(hour=hour_in,
                                                                                                     minute=random.randint(
                                                                                                         0, 30))).time()
                    check_out = (timezone.datetime.combine(day, timezone.datetime.min.time()).replace(hour=17,
                                                                                                      minute=random.randint(
                                                                                                          0,
                                                                                                          30))).time()
                items.append(Attendance(
                    employee=e,
                    date=day,
                    check_in=check_in,
                    check_out=check_out,
                    worked_hours=None,
                    overtime_hours=0,
                    status=status,
                    notes="",
                    tenant_id=tenant_id_str,
                ))
        # bulk_create puis recalcul si besoin (Attendance.save calcule si check_in/out)
        Attendance.objects.bulk_create(items, ignore_conflicts=True)

    def _create_payrolls(self, tenant_id_str, employees):
        items = []
        today = date.today()
        # 3 mois de paie
        for e in employees:
            for m in range(3):
                period_end = (today.replace(day=1) - timedelta(days=1)).replace(day=28) + timedelta(days=4)
                period_end = period_end - timedelta(days=period_end.day)  # dernier jour mois courant
                period_start = (period_end.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
                period_end = (period_start.replace(day=28) + timedelta(days=4))
                period_end = period_end - timedelta(days=period_end.day)

                base = random.randint(250_000, 2_500_000)
                overtime_pay = random.randint(0, 200_000)
                bonuses = random.randint(0, 150_000)
                allowances = random.randint(0, 100_000)
                tax = int(base * 0.05)
                social = int(base * 0.03)

                items.append(Payroll(
                    employee=e,
                    period_start=period_start,
                    period_end=period_end,
                    pay_date=period_end + timedelta(days=5),
                    base_salary=base,
                    overtime_pay=overtime_pay,
                    bonuses=bonuses,
                    allowances=allowances,
                    tax=tax,
                    social_security=social,
                    other_deductions=0,
                    gross_salary=0,  # recalculé en save()
                    net_salary=0,  # recalculé en save()
                    status=random.choice(["DRAFT", "PROCESSED", "PAID"]),
                    payroll_number=f"PAY-{tenant_id_str[:6].upper()}-{uuid.uuid4().hex[:10].upper()}",
                    tenant_id=tenant_id_str,
                ))

        # save un par un (Payroll.save calcule totals)
        for p in items:
            p.save()

    def _create_performance_reviews(self, tenant_id_str, employees):
        items = []
        today = date.today()
        for e in random.sample(employees, k=min(len(employees), 70)):
            reviewer = random.choice([x for x in employees if x.id != e.id])
            start = rand_date_between(today - timedelta(days=365), today - timedelta(days=60))
            end = start + timedelta(days=90)
            items.append(PerformanceReview(
                employee=e,
                review_period_start=start,
                review_period_end=end,
                review_date=end + timedelta(days=random.randint(1, 15)),
                reviewer=reviewer,
                overall_rating=round(random.uniform(1.0, 5.0), 1),
                goals_achievement=random.randint(30, 100),
                strengths=fake.text(max_nb_chars=120),
                areas_for_improvement=fake.text(max_nb_chars=120),
                goals_next_period=fake.text(max_nb_chars=120),
                status=random.choice(["DRAFT", "IN_REVIEW", "FINALIZED", "ACKNOWLEDGED"]),
                tenant_id=tenant_id_str,
            ))
        PerformanceReview.objects.bulk_create(items)

    def _create_recruitment_pipeline(self, tenant, tenant_id_str, departments, positions, employees, workflows):
        # Recruitment
        recruitments = []
        for i in range(8):
            dept = random.choice(departments)
            pos = random.choice([p for p in positions if p.department_id == dept.id] or positions)
            ref = f"REC-{tenant_id_str[:6].upper()}-{uuid.uuid4().hex[:6].upper()}"
            recruitments.append(Recruitment(
                title=f"{pos.title}",
                reference=ref,
                position=pos,
                department=dept,
                job_description=fake.text(max_nb_chars=200),
                requirements={
                    "skills": random.sample(["Python", "Django", "SQL", "Excel", "RH", "Compta", "Linux"], k=3)},
                contract_type=random.choice(["CDI", "CDD", "STAGE", "ALTERNANCE"]),
                salary_min=random.randint(200_000, 600_000),
                salary_max=random.randint(700_000, 2_000_000),
                location=random.choice(["Abidjan", "Bouaké", "San-Pédro"]),
                remote_allowed=random.random() < 0.3,
                hiring_manager=random.choice(employees),
                status=random.choice(["OPEN", "IN_REVIEW", "INTERVIEW", "OFFER", "CLOSED"]),
                publication_date=date.today() - timedelta(days=random.randint(1, 90)),
                closing_date=None,
                target_hiring_date=date.today() + timedelta(days=random.randint(15, 90)),
                number_of_positions=random.randint(1, 3),
                ai_scoring_enabled=True,
                ai_scoring_criteria={"min_exp": random.randint(0, 5)},
                minimum_ai_score=random.uniform(50.0, 80.0),
                tenant=tenant,
            ))
        Recruitment.objects.bulk_create(recruitments)
        recruitments = list(Recruitment.objects.filter(tenant=tenant))

        # Ajouter recruiters M2M
        for r in recruitments:
            r.recruiters.add(*random.sample(employees, k=min(3, len(employees))))

        # Applications + IA + interviews + feedback + analytics + offers
        for r in recruitments:
            applications = []
            for _ in range(random.randint(10, 25)):
                applications.append(JobApplication(
                    recruitment=r,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=f"{uuid.uuid4().hex[:8]}@candidate.com",
                    phone=fake.phone_number(),
                    cv="job_applications/cv/seed.pdf",  # chemin factice: si tu veux vrai fichier, il faut upload réel
                    cover_letter=None,
                    portfolio=None,
                    extracted_data={"seed": True},
                    ai_score=round(random.uniform(0, 100), 2),
                    ai_feedback={"summary": "Auto IA seed"},
                    status=random.choice([
                        "APPLIED", "AI_SCREENED", "AI_REJECTED", "HR_REVIEW",
                        "SHORTLISTED", "INTERVIEW_1", "OFFERED", "HIRED", "REJECTED"
                    ]),
                    reviewed_by=random.choice(employees),
                    reviewed_at=timezone.now() if random.random() < 0.7 else None,
                    internal_notes=fake.text(max_nb_chars=120),
                    tenant_id=tenant_id_str,
                ))
            JobApplication.objects.bulk_create(applications)
            applications = list(JobApplication.objects.filter(recruitment=r))

            # AIProcessingResult (pour ~50%)
            for app in random.sample(applications, k=min(len(applications), len(applications) // 2)):
                AIProcessingResult.objects.create(
                    job_application=app,
                    extracted_skills=random.sample(["Python", "Django", "SQL", "Docker", "React", "HR"], k=3),
                    extracted_experience=[{"role": "Dev", "years": random.randint(0, 8)}],
                    extracted_education=[{"degree": random.choice(["Licence", "Master", "BTS"])}],
                    extracted_languages=[{"lang": "Français", "level": "C1"}],
                    skills_match_score=round(random.uniform(0, 100), 2),
                    experience_match_score=round(random.uniform(0, 100), 2),
                    education_match_score=round(random.uniform(0, 100), 2),
                    overall_match_score=round(random.uniform(0, 100), 2),
                    missing_skills=[],
                    strong_skills=[],
                    experience_gaps=[],
                    red_flags=[],
                    processing_time=round(random.uniform(0.2, 5.0), 3),
                    ai_model_version="seed-v1",
                    status=random.choice(["COMPLETED", "COMPLETED", "FAILED"]),
                    error_message="" if random.random() < 0.9 else "Parse error",
                    tenant_id=tenant_id_str,
                )

            # Interviews + feedback
            for app in random.sample(applications, k=min(len(applications), 10)):
                itv = Interview.objects.create(
                    job_application=app,
                    interview_type=random.choice(["PHONE", "VIDEO", "IN_PERSON", "TECHNICAL", "HR"]),
                    candidate=app,
                    scheduled_date=timezone.now() + timedelta(days=random.randint(1, 20)),
                    duration=random.choice([30, 45, 60]),
                    location=random.choice(["Siège", "Visio", "Agence"]),
                    meeting_link="https://meet.example.com/" + uuid.uuid4().hex[:8] if random.random() < 0.6 else "",
                    interview_guide=fake.text(max_nb_chars=120),
                    key_points_to_assess=["Motivation", "Compétences", "Culture fit"],
                    conducted_at=None,
                    interviewer_feedback={},
                    overall_rating=None,
                    recommendation="",
                    notes="",
                    status=random.choice(["SCHEDULED", "CONFIRMED"]),
                    tenant_id=tenant_id_str,
                )
                itv.interviewers.add(*random.sample(employees, k=min(2, len(employees))))

                for interviewer in itv.interviewers.all():
                    InterviewFeedback.objects.create(
                        interview=itv,
                        interviewer=interviewer,
                        criteria={"communication": round(random.uniform(1, 5), 1),
                                  "tech": round(random.uniform(1, 5), 1)},
                        summary=fake.sentence(),
                        rating=round(random.uniform(1, 5), 1),
                        tenant_id=tenant_id_str,
                    )

            # Analytics
            total = len(applications)
            hires = sum(1 for a in applications if a.status == "HIRED")
            ai_scr = sum(1 for a in applications if a.status == "AI_SCREENED")
            ai_rej = sum(1 for a in applications if a.status == "AI_REJECTED")
            hr_rev = sum(1 for a in applications if a.status == "HR_REVIEW")
            offered = sum(1 for a in applications if a.status == "OFFERED")

            RecruitmentAnalytics.objects.update_or_create(
                recruitment=r,
                defaults=dict(
                    total_applications=total,
                    ai_screened_applications=ai_scr,
                    ai_rejected_applications=ai_rej,
                    hr_reviewed_applications=hr_rev,
                    interviews_scheduled=random.randint(0, 15),
                    offers_made=offered,
                    hires=hires,
                    average_processing_time=round(random.uniform(1, 72), 2),
                    time_to_hire=round(random.uniform(7, 45), 2),
                    ai_accuracy_rate=round(random.uniform(40, 95), 2),
                    ai_false_positives=random.randint(0, 5),
                    ai_false_negatives=random.randint(0, 5),
                    application_sources={"LinkedIn": random.randint(0, total), "Site": random.randint(0, total)},
                    tenant_id=tenant_id_str,
                )
            )

            # Offers (pour quelques "OFFERED")
            offered_apps = [a for a in applications if a.status == "OFFERED"]
            for app in random.sample(offered_apps, k=min(len(offered_apps), 3)):
                JobOffer.objects.update_or_create(
                    job_application=app,
                    defaults=dict(
                        title=r.title,
                        proposed_salary=random.randint(300_000, 2_500_000),
                        start_date=date.today() + timedelta(days=random.randint(15, 60)),
                        contract_type=r.contract_type,
                        offer_pdf=None,
                        status=random.choice(["SENT", "ACCEPTED", "DECLINED", "EXPIRED"]),
                        sent_at=timezone.now(),
                        decided_at=timezone.now() if random.random() < 0.5 else None,
                        tenant_id=tenant_id_str,
                    )
                )
