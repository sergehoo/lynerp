# finance/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .routers import router  # <-- ton router existant (celui où tu register invoices)

urlpatterns = [
    path("", include(router.urls)),
]