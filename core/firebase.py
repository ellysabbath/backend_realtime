import firebase_admin
from firebase_admin import credentials, db
from django.conf import settings

if not firebase_admin._apps:
    cred = credentials.Certificate(str(settings.FIREBASE_CREDENTIALS_PATH))
    firebase_admin.initialize_app(cred, {'databaseURL': settings.FIREBASE_DATABASE_URL})

rtdb = db