# tenants/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings


class TenantAuthenticationForm(AuthenticationForm):
    tenant_id = forms.CharField(
        label="Tenant",
        required=True,
        widget=forms.TextInput(attrs={"autocomplete": "organization"})
    )
    remember_me = forms.BooleanField(required=False)

    def confirm_login_allowed(self, user):
        """
        Appelé après l’auth. Ici tu peux vérifier que l’utilisateur a accès au tenant,
        plan actif, statut, etc. Ex:
        """
        tenant_id = self.cleaned_data.get("tenant_id")
        # TODO: vérifier l’accès du user au tenant_id (requête sur ton modèle TenantUser)
        # if not user.has_access_to(tenant_id): raise forms.ValidationError("Accès refusé", code="inactive")
        super().confirm_login_allowed(user)

    def clean(self):
        cleaned = super().clean()  # appelle authenticate(username, password)
        # Enregistrer le tenant dans la session via la vue (on ne l’a pas ici)
        # On place juste la valeur pour que la vue puisse la lire ensuite.
        self.tenant_id = self.cleaned_data.get("tenant_id")
        self.remember_me_value = self.cleaned_data.get("remember_me")
        return cleaned
