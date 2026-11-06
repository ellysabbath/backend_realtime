import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db
from django.conf import settings

logger = logging.getLogger(__name__)

db_ref = None

cred_path = Path(settings.FIREBASE_CREDENTIALS_PATH)

if not cred_path.exists():
    logger.warning(
        "Firebase credentials not found at %s — Firebase features disabled.",
        cred_path,
    )
else:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred, {
                'databaseURL': settings.FIREBASE_DATABASE_URL,
            })
        db_ref = db.reference('/')
    except Exception:
        logger.exception("Failed to initialize Firebase.")
        db_ref = None