"""
Bascule entre les fichiers de settings selon ``DJANGO_ENV``.

Valeurs admises :
    - ``dev``   (par défaut)
    - ``prod``
    - ``test``  (charge dev avec quelques overrides)
"""
import os

env = os.getenv("DJANGO_ENV", "dev").lower().strip()

if env == "prod":
    from .prod import *  # noqa: F401,F403
elif env == "test":
    from .test import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
