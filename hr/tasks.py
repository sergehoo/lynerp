# hr/tasks.py
from celery import shared_task
from .models import JobApplication
from .ai_recruitment_service import AIRecruitmentService

@shared_task
def process_application_task(app_id):
    app = JobApplication.objects.get(id=app_id)
    AIRecruitmentService().process_application(app)