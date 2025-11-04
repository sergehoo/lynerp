# settings/prod.py
import os
from .base import *

DEBUG = True
SECURE_SSL_REDIRECT = False
# pour le retour en HTTPS strict
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = [
    "http://www.lynerp.com",
    "https://media.lynerp.com",
    "http://media.lynerp.com",
    "http://lynerp.com",
    "https://lynerp.com",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
