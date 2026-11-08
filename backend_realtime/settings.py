from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──
SECRET_KEY = 'django-insecure-change-me-in-production'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# ── Apps ──
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',

    # local apps (in dependency order)
    'core',
    'api',
    'auths',
    'chats',
    'customers',
    'technicians',
    'owners',
    'admins',
    'notifications',
]

# ── Middleware ──
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',      # ← must be near top
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend_realtime.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend_realtime.wsgi.application'

# ── Database (only used by Django admin/auth) ──
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ── Password validators ──
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── i18n ──
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static ──
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS for React dev server (Vite on port 3000) ──
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# # ── Firebase ──
# FIREBASE_CREDENTIALS_PATH = BASE_DIR / 'serviceAccountKey.json'
# FIREBASE_DATABASE_URL = 'https://data-537e6-default-rtdb.firebaseio.com/'


# # ============================
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'qfix910@gmail.com'
# EMAIL_HOST_PASSWORD = 'sbntxflapmitoakx'
# DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# DEFAULT_FROM_EMAIL = 'noreply@omaflowers.com'
# AT_USERNAME = "qfix"                # your AT production username
# AT_API_KEY = "atsk_152378670676d07a251df2a73016e1c2a179a77584397dc5af2ff185ea5e250bcb267d17"                 # new key from AT dashboard
# AT_SENDER_ID = "QuickFix"                         # optional shortcode
# AT_BASE_URL = "https://api.africastalking.com/version1/messaging"
