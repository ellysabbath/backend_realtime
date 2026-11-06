import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .firebase_config import db_ref


def _firebase_ready():
    if db_ref is None:
        return JsonResponse(
            {'error': 'Firebase not configured on server'},
            status=503,
        )
    return None


@csrf_exempt
@require_http_methods(["POST"])
def add_message(request):
    """Write a new message to Firebase Realtime DB."""
    if (err := _firebase_ready()) is not None:
        return err

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)

    text = (data.get('text') or '').strip()
    user = (data.get('user') or 'anonymous').strip()

    if not text:
        return JsonResponse({'error': 'text is required'}, status=400)

    new_ref = db_ref.child('messages').push({
        'text': text,
        'user': user,
        'timestamp': {'.sv': 'timestamp'},
    })
    return JsonResponse({'status': 'ok', 'id': new_ref.key})


@require_http_methods(["GET"])
def list_messages(request):
    """Read all messages (useful for debugging)."""
    if (err := _firebase_ready()) is not None:
        return err

    data = db_ref.child('messages').get() or {}
    messages = [{'id': k, **v} for k, v in data.items()]
    return JsonResponse({'messages': messages})


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({'status': 'ok', 'service': 'django-backend'})