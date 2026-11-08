from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from core.firebase import rtdb
# Make sure this is the correct path to your token verifier in auths/views.py
from auths.views import _resolve_token

def _ok(d, s=200):
    return JsonResponse(d, status=s, safe=False)

def _err(m, s=400):
    return JsonResponse({'error': m}, status=s)


@csrf_exempt
@require_http_methods(['GET'])
def messages(request):
    request_id = request.GET.get('requestId')
    if not request_id:
        return _err('requestId required')

    data = rtdb.reference(f'/chats/{request_id}').get() or {}
    # Filter out typing status objects (they don't have a 'text' field)
    rows = [{'id': k, **v} for k, v in data.items() if isinstance(v, dict) and 'text' in v]
    rows.sort(key=lambda m: m.get('sentAt', 0))
    return _ok(rows)


@csrf_exempt
@require_http_methods(['POST'])
def send_message(request):
    # 1. Extract Token
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip()
    
    if not token:
        return _err('Unauthorized: Missing token', 401)
        
    uid, user = _resolve_token(token)
    if not uid:
        return _err('Unauthorized: Invalid token', 401)

    # 2. Parse Message
    b = json.loads(request.body)
    request_id = b.get('requestId')
    text = (b.get('text') or '').strip()

    if not request_id or not text:
        return _err('requestId and text required')

    # 3. Save to Firebase
    # We strictly use 'uid' and 'user' from the token, NOT the frontend payload.
    new = rtdb.reference(f'/chats/{request_id}').push()
    new.set({
        'senderId': uid,                                      # <--- SECURE ID
        'senderRole': user.get('role', 'customer'),           # <--- SECURE ROLE
        'senderName': user.get('fullName', 'Unknown'),        # <--- SECURE NAME
        'text': text,
        'sentAt': {'.sv': 'timestamp'},
        'read': False,
    })
    return _ok({'id': new.key}, 201)

@csrf_exempt
@require_http_methods(['PATCH'])
def mark_read(request, request_id):
    b = json.loads(request.body)
    reader_role = b.get('readerRole')
    if reader_role not in ('customer', 'technician'):
        return _err('readerRole must be customer or technician')

    rows = rtdb.reference(f'/chats/{request_id}').get() or {}
    for mid, msg in rows.items():
        if isinstance(msg, dict) and 'text' in msg and msg.get('senderRole') != reader_role:
            rtdb.reference(f'/chats/{request_id}/{mid}/read').set(True)
    return _ok({'updated': True})


@csrf_exempt
@require_http_methods(['POST'])
def typing(request):
    b = json.loads(request.body)
    request_id = b.get('requestId')
    role = b.get('role')
    is_typing = bool(b.get('typing'))

    if not request_id or role not in ('customer', 'technician'):
        return _err('requestId and role required')

    # Save typing state to Firebase
    rtdb.reference(f'/chats/{request_id}/typing/{role}').set({
        'typing': is_typing,
        'updatedAt': {'.sv': 'timestamp'},
    })
    return _ok({'ok': True})


# ── (Optional) SSE fallback endpoints, though frontend now uses Firebase SDK ──

@csrf_exempt
@require_http_methods(['GET'])
def stream_messages(request):
    request_id = request.GET.get('requestId')
    if not request_id:
        return _err('requestId required')

    def event_stream():
        ref = rtdb.reference(f'/chats/{request_id}')
        yield 'event: open\ndata: {"connected":true}\n\n'
        try:
            for _ in ref.listen(lambda e: e):
                tree = ref.get() or {}
                rows = [{'id': k, **v} for k, v in tree.items() if isinstance(v, dict) and 'text' in v]
                rows.sort(key=lambda m: m.get('sentAt', 0))
                yield f'event: messages\ndata: {json.dumps({"messages": rows})}\n\n'
        except GeneratorExit:
            return
        except Exception:
            pass

    resp = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp

@csrf_exempt
@require_http_methods(['GET'])
def stream_presence(request):
    request_id = request.GET.get('requestId')
    if not request_id:
        return _err('requestId required')

    def event_stream():
        ref = rtdb.reference(f'/chats/{request_id}/typing')
        yield 'event: open\ndata: {"connected":true}\n\n'
        try:
            for _ in ref.listen(lambda e: e):
                data = ref.get() or {}
                yield f'event: presence\ndata: {json.dumps(data)}\n\n'
        except GeneratorExit:
            return
        except Exception:
            pass

    resp = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp