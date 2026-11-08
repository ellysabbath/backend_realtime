import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.firebase import rtdb

def _ok(d, s=200): return JsonResponse(d, status=s, safe=False)
def _err(m, s=400): return JsonResponse({'error': m}, status=s)

@csrf_exempt
@require_http_methods(['GET'])
def list_for_user(request):
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')
    
    # Fetch all notifications from Firebase
    data = rtdb.reference('/notifications').get() or {}
    
    # Filter for this user (or 'admin')
    rows = [{'id': k, **v} for k, v in data.items() if v.get('userId') == uid]
    
    # Sort by newest first
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