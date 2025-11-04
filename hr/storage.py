# hr/storage.py
import os
import uuid

class TenantPath:
    """
    Callable sérialisable pour FileField.upload_to.
    Exemple d'usage: FileField(upload_to=TenantPath('job_applications/cv'))
    """
    def __init__(self, prefix: str):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename: str) -> str:
        tenant = getattr(instance, "tenant_id", "public")
        name = os.path.basename(filename or "")
        unique = f"{uuid.uuid4()}_{name}" if name else str(uuid.uuid4())
        return f"{tenant}/{self.prefix}/{unique}"

    def deconstruct(self):
        """
        Permet à Django de sérialiser ce callable dans les migrations.
        Doit retourner (path_import, args, kwargs).
        """
        path = "hr.storage.TenantPath"
        return (path, [self.prefix], {})