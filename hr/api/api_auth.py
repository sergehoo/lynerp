# hr/api_auth.py
from django.conf import settings
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class WhoAmIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Données de session
        session_data = request.session.get(settings.OIDC_SESSION_KEY, {})

        # Données JWT
        jwt_data = getattr(request, 'auth', {})

        # Tenant
        tenant_id = (request.headers.get("X-Tenant-Id") or
                     getattr(request, "tenant_id", None) or
                     request.session.get("tenant_id"))

        user_data = {
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
        }

        # Fusion avec données OIDC
        if session_data:
            user_data.update({
                "preferred_username": session_data.get("preferred_username"),
                "email": session_data.get("email", user_data["email"]),
            })

        return Response({
            "user": user_data,
            "tenant": tenant_id,
            "auth_via": "jwt" if jwt_data else "session"
        })


class LicenseStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant_id = request.headers.get("X-Tenant-Id")
        if not tenant_id:
            return Response({"detail": "Tenant manquant"}, status=400)

        from tenants.models import License
        from django.utils import timezone

        try:
            lic = License.objects.filter(
                tenant_id=tenant_id,
                module="rh",
                active=True,
                valid_until__gte=timezone.now().date()
            ).first()

            if lic:
                return Response({
                    "status": "active",
                    "plan": lic.plan,
                    "valid_until": lic.valid_until,
                    "seats": lic.seats
                })
            else:
                return Response({
                    "status": "invalid",
                    "detail": "Licence non trouvée ou expirée"
                })

        except Exception as e:
            return Response({
                "status": "error",
                "detail": str(e)
            }, status=500)


class RefreshLicenseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Simuler un rafraîchissement de licence
        return Response({
            "status": "refreshed",
            "message": "Licence rafraîchie avec succès"
        })


class LicensePortalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # URL vers le portail de facturation
        return Response({
            "url": "/billing/portal/"
        })