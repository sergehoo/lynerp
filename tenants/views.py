from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import render

from tenants.forms import TenantAuthenticationForm


# Create your views here.


class TenantLoginView(LoginView):
    authentication_form = TenantAuthenticationForm

    def form_valid(self, form):
        # Auth OK -> login
        user = form.get_user()
        login(self.request, user)

        # Stocker le tenant en session pour l’appli
        tenant_key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
        self.request.session[tenant_key] = getattr(form, "tenant_id", None)

        # Remember me
        remember = getattr(form, "remember_me_value", False)
        if remember:
            self.request.session.set_expiry(
                getattr(settings, "REMEMBER_ME_SESSION_AGE", 60 * 60 * 24 * 30)
            )
        else:
            # expire à la fermeture du navigateur
            self.request.session.set_expiry(0)

        return super().form_valid(form)