# hr/api_auth.py
from django.conf import settings
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class WhoAmIView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # marche avec SessionAuthentication + KeycloakJWTAuthentication

    def get(self, request):
        # Données session (si login via /auth/keycloak/login/)
        session_data = request.session.get(getattr(settings, "OIDC_SESSION_KEY", "oidc"), {})

        # JWT (si auth Bearer)
        jwt_data = getattr(request, 'auth', {}) or {}

        # Tenant résolu par middleware (préféré), sinon header, sinon session
        tenant_obj = getattr(request, "tenant", None)
        tenant_id = (getattr(request, "tenant_id", None)
                     or request.headers.get("X-Tenant-Id")
                     or request.session.get(getattr(settings, "TENANT_SESSION_KEY", "current_tenant")))

        # Harmonise : si middleware a mis l’objet, écrase tenant_id par la vraie PK
        if tenant_obj:
            tenant_id = str(tenant_obj.id)

        user = request.user
        user_data = {
            "username": getattr(user, "username", None),
            "email": getattr(user, "email", None),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
        }

        # Fusion OIDC
        if session_data:
            user_data.update({
                "preferred_username": session_data.get("preferred_username") or user_data["username"],
                "email": session_data.get("email", user_data["email"]),
            })

        # Infos utiles pour le front
        tenant_payload = {
            "id": tenant_id,
            "slug": getattr(tenant_obj, "slug", None) if tenant_obj else None,
            "name": getattr(tenant_obj, "name", None) if tenant_obj else None,
        }

        return Response({
            "user": user_data,
            "tenant": tenant_payload,     # ← le front peut utiliser slug/id
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