from datetime import timedelta
from pathlib import Path
import environ # type: ignore

import os
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Cargar el .env del proyecto (core/.env). No pisa variables ya
# exportadas en el entorno (supervisor, sistema, etc.).
_CORE_ENV = os.path.join(BASE_DIR, "core", ".env")
if os.path.exists(_CORE_ENV):
    environ.Env.read_env(_CORE_ENV)
else:
    environ.Env.read_env()  # fallback: .env del cwd (comportamiento anterior)
ENVIRONMENT = env


SUNAT_PHP = os.getenv("SUNAT_PHP", "").strip()
SUNAT_API_KEY = os.getenv("SUNAT_API_KEY", "").strip()

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "gonzafact_webhook_2026")

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
# Nombres usados en el .env (con fallback a los nombres antiguos):
# R2_ENDPOINT / R2_KEY / R2_SECRET / R2_BUCKET / R2_BASE_URL
R2_ACCESS_KEY_ID = os.getenv("R2_KEY", "") or os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET", "") or os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET", "") or os.getenv("R2_BUCKET_NAME", "")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT", "") or os.getenv("R2_ENDPOINT_URL", "")
R2_PUBLIC_URL = os.getenv("R2_BASE_URL", "") or os.getenv("R2_PUBLIC_URL", "")


SECRET_KEY = 'django-insecure-b_(uj)meht&*#4#223px8w@t=l6emfbdtw2jcw+ei39d!j&5c%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
# Configuración de CORS

ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
    f'http://{LOCAL_IP}:4200',
    'https://inventario-electronic-w7mn.vercel.app',
    'https://inventarioaxel.duckdns.org',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# CSRF Trusted Origins - AGREGAR TU VERCEL AQUÍ
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
    f'http://{LOCAL_IP}:4200',
    'https://inventario-electronic-w7mn.vercel.app',
]




# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
        "rest_framework_simplejwt.token_blacklist",

    "corsheaders",
    "rest_framework",
    "djoser",
                    "apps.user",
                    "apps.categoria",
                    "apps.inventario",
                    "apps.cliente",
                    "apps.producto",
                    "apps.proveedor",
                    "apps.tienda",
                    "apps.venta",
                    
                    "apps.comprobante",
                    
                    "apps.pedidos",
                    "apps.compras",
                    "apps.guia_remision",
                    "apps.whatsapp",
    "ckeditor",
    "ckeditor_uploader",
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    "rest_framework.authtoken",
     
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database


# Databases
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres:///ninerogues"), # type: ignore
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True


# Password validation


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}



AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)



DJOSER = {

    'DOMAIN': 'https://samubackend.onrender.com',
    'LOGIN_FIELD': 'email',
    'USER_CREATE_PASSWORD_RETYPE': True,
    'USERNAME_CHANGED_EMAIL_CONFIRMATION': True,
    'PASSWORD_CHANGED_EMAIL_CONFIRMATION': True,
    'SEND_CONFIRMATION_EMAIL': True,
    'SET_USERNAME_RETYPE': True,
    'PASSWORD_RESET_CONFIRM_URL': 'password/reset/confirm/{uid}/{token}',
    'SET_PASSWORD_RETYPE': True,
    'PASSWORD_RESET_CONFIRM_RETYPE': True,
    'USERNAME_RESET_CONFIRM_URL': 'email/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': 'activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'SOCIAL_AUTH_TOKEN_STRATEGY': 'djoser.social.token.jwt.TokenStrategy',
    'SERIALIZERS': {
        'user_create': 'apps.user.serializers.UserAcountCreateSerializer',
        'user': 'apps.user.serializers.UserAcountCreateSerializer',
        'current_user': 'apps.user.serializers.UserAcountCreateSerializer',
        'user_delete': 'djoser.serializers.UserDeleteSerializer',
        "token_create": "apps.user.serializers.CustomTokenObtainPairSerializer",

    },
}


SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("JWT",),
     "BLACKLIST_AFTER_ROTATION": True,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10080),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=15),
    "ROTATE_REFRESH_TOKEN": True,
    "AUTH_TOKEN_CLASES": (
        "rest_framework_simplejwt.tokens.AccessToken"
    )
}

# Internationalization

TIME_ZONE = 'America/Lima'
USE_TZ = True  # Asegúrate de que esto esté en True

LANGUAGE_CODE = 'es'



USE_I18N = True




# Static files (CSS, JavaScript, Images)


STATIC_URL = 'static/'

# Default primary key field type


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Static files (CSS, JavaScript, Images) (Por ahora no)

STATIC_URL = '/statics/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


SITE_DOMAIN = os.environ.get("SITE_DOMAIN")
DOMAIN = os.environ.get('DOMAIN')
SITE_NAME = ('SAMU ILO')

SITE_ID = 1
AUTH_USER_MODEL = "user.UserAccount"
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# URL para acceder a los archivos cargados
MEDIA_URL = '/media/'
# Configuración para django-ckeditor
CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/"
