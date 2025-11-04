# tenants/auth_backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantModelBackend(ModelBackend):
    """
    Auth standard mais on **peut** refuser l’auth selon le tenant.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        tenant_id = (request.POST.get("tenant_id") if request else kwargs.get("tenant_id"))
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if not user:
            return None

        # TODO: contrôle d’accès tenant ici.
        # Exemple d’idée :
        # if not TenantUser.objects.filter(user=user, tenant__slug=tenant_id, is_active=True).exists():
        #     return None

        return user
