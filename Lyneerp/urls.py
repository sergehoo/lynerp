from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from hr.api.routers import urlpatterns as hr_urls
from hr.views import HRDashboardView, EmployeeManagementView, RecruitmentView, LeaveManagementView, AttendanceView
from django.contrib.auth import views as auth_views

from tenants.auth_views import keycloak_direct_login


def healthz(_):
    # ⚡ rapide : sans requête DB
    return JsonResponse({"status": "ok"})

def home(request):
    if request.user.is_authenticated:
        # ta home réelle
        return redirect("/")  # ou la page que tu veux
    return redirect("/oidc/authenticate/")  # lance le flow OIDC

urlpatterns = [
                  path("healthz", healthz),
                  path('admin/', admin.site.urls),
                  path('api/rh/', include((hr_urls, 'hr'))),
                  # path("api/rh/", include("hr.routers")),
                  path('schema/', SpectacularAPIView.as_view(), name='schema'),
                  path('docs/', SpectacularSwaggerView.as_view(url_name='schema')),
                  path('oidc/', include('mozilla_django_oidc.urls')),
                  path('', HRDashboardView.as_view(), name='hr-dashboard'),
                  path('employees/', EmployeeManagementView.as_view(), name='hr-employees'),
                  path('recruitment/', RecruitmentView.as_view(), name='hr-recruitment'),
                  path('leaves/', LeaveManagementView.as_view(), name='hr-leaves'),
                  path('attendance/', AttendanceView.as_view(), name='hr-attendance'),

                  path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
                  path("auth/keycloak/login", keycloak_direct_login, name="keycloak_direct_login"),

                  path('logout/', auth_views.LogoutView.as_view(), name='logout'),
              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
