import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.firebase import rtdb


def _ok(d, s=200):
    return JsonResponse(d, status=s, safe=False)


def _err(m, s=400):
    return JsonResponse({'error': m}, status=s)


@csrf_exempt
@require_http_methods(['GET'])
def list_for_user(request):
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')
    
    data = rtdb.reference('/notifications').get() or {}
    rows = [{'id': k, **v} for k, v in data.items() if v.get('userId') == uid]
    rows.sort(key=lambda n: n.get('createdAt', 0), reverse=True)
    return _ok(rows)


@csrf_exempt
@require_http_methods(['PATCH'])
def mark_read(request, nid):
    rtdb.reference(f'/notifications/{nid}/read').set(True)
    return _ok({'id': nid, 'read': True})


@csrf_exempt
@require_http_methods(['POST'])
def create(request):
    b = json.loads(request.body)
    uid = b.get('userId')
    if not uid:
        return _err('userId required')
        
    new = rtdb.reference('/notifications').push()
    new.set({
        'userId': uid,
        'title': b.get('title', ''),
        'message': b.get('message', ''),
        'type': b.get('type', 'info'),
        'read': False,
        'createdAt': {'.sv': 'timestamp'},
    })
    return _ok({'id': new.key}, 201)


@csrf_exempt
@require_http_methods(['GET'])
def stream_notifications(request):
    """
    Server-Sent Events stream for real-time notifications.
    Watches Firebase /notifications and pushes updates instantly.
    """
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')

    def event_stream():
        ref = rtdb.reference('/notifications')
        
        # Send initial handshake so the browser knows the connection opened
        yield 'event: open\ndata: {"connected":true}\n\n'

        try:
            # Firebase listen() blocks and yields an event whenever the node changes
            for _ in ref.listen(lambda e: e):
                data = ref.get() or {}
                
                # Filter only the notifications for this user
                mine = [
                    {'id': k, **v} 
                    for k, v in data.items() 
                    if isinstance(v, dict) and v.get('userId') == uid
                ]
                
                # Newest first
                mine.sort(key=lambda n: n.get('createdAt', 0), reverse=True)
                
                payload = json.dumps({'notifications': mine})
                yield f'event: notifications\ndata: {payload}\n\n'

        except GeneratorExit:
            return
        except Exception as e:
            try:
                yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'
            except Exception:
                pass

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response