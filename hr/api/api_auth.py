# hr/api_auth.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class WhoAmI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        oidc = getattr(request, "oidc", {}) or {}
        # tenant fallback: header > token claims
        tenant = request.headers.get("X-Tenant-Id") or oidc.get("tenant") or oidc.get("tenant_id") or None
        return Response({
            "user": {
                "username": getattr(request.user, "username", None),
                "email": getattr(request.user, "email", None),
                "sub": oidc.get("sub"),
                "roles": ((oidc.get("resource_access") or {}).get("rh-core") or {}).get("roles", []),
            },
            "tenant": tenant
        })