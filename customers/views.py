from django.shortcuts import render

# Create your views here.
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
@require_http_methods(['GET', 'POST'])
def requests(request):
    ref = rtdb.reference('/requests')

    if request.method == 'GET':
        cid = request.GET.get('customerId')
        data = ref.get() or {}
        rows = [{'id': k, **v} for k, v in data.items()]
        if cid:
            rows = [r for r in rows if r.get('customerId') == cid]
        rows.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
        return _ok(rows)

    # ─── POST: Create new request ───
    b = json.loads(request.body)
    cid = b.get('customerId')
    if not cid:
        return _err('customerId required')

    new = ref.push()
    payload = {
        'customerId': cid,
        'customerName': b.get('fullName', ''),
        'customerPhone': b.get('phone', ''),
        'location': b.get('location', ''),
        'distance': b.get('distance', 0),
        'vehicleName': b.get('vehicleName', ''),
        'vehicleType': b.get('vehicleType', ''),
        'vehicleYear': b.get('vehicleYear', ''),
        'vehicleModel': b.get('vehicleModel', ''),
        'plateNumber': b.get('plateNumber', ''),
        'problemType': b.get('problemType', ''),
        'problemDescription': b.get('problemDescription', ''),
        'status': 'pending',
        'estimatedCost': 0,
        'createdAt': {'.sv': 'timestamp'},
    }
    new.set(payload)
    rtdb.reference('/technicianRequests').child(new.key).set(payload)

    # ─── NEW: Create Notifications ───
    # 1. Notify all active technicians
    techs = rtdb.reference('/technicians').get() or {}
    active_techs = [t for t in techs.values() if t.get('status') == 'active']
    
    for tech in active_techs:
        tech_uid = tech.get('userId')
        if tech_uid:
            notif = rtdb.reference('/notifications').push()
            notif.set({
                'userId': tech_uid,
                'title': 'New Job Available',
                'message': f"{payload['customerName']} requested help for a {payload['problemType']} in {payload['location']}.",
                'type': 'info',
                'read': False,
                'createdAt': {'.sv': 'timestamp'},
            })
            
    # 2. Notify the Admin (if you use an 'admin' ID or notify all admins)
    notif_admin = rtdb.reference('/notifications').push()
    notif_admin.set({
        'userId': 'admin',
        'title': 'New System Request',
        'message': f"{payload['customerName']} created a new vehicle request.",
        'type': 'warning',
        'read': False,
        'createdAt': {'.sv': 'timestamp'},
    })

    return _ok({'id': new.key}, 201)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def request_detail(request, rid):
    ref = rtdb.reference(f'/requests/{rid}')

    if request.method == 'GET':
        d = ref.get()
        if not d:
            return _err('Not found', 404)
        return _ok({'id': rid, **d})

    if request.method == 'PATCH':
        ref.update(json.loads(request.body))
        return _ok({'id': rid, 'updated': True})

    ref.delete()
    rtdb.reference(f'/technicianRequests/{rid}').delete()
    return _ok({'id': rid, 'deleted': True})


@csrf_exempt
@require_http_methods(['POST'])
def pay(request, rid):
    b = json.loads(request.body)
    rtdb.reference(f'/requests/{rid}').update({
        'status': 'paid',
        'paymentMethod': b.get('method', 'cash'),
        'referenceNumber': b.get('reference', ''),
        'paidAt': {'.sv': 'timestamp'},
    })
    return _ok({'id': rid, 'status': 'paid'})


@csrf_exempt
@require_http_methods(['GET'])
def customer_dashboard(request):
    cid = request.GET.get('customerId')
    if not cid:
        return _err('customerId required')

    data = rtdb.reference('/requests').get() or {}
    rows = [{'id': k, **v} for k, v in data.items() if v.get('customerId') == cid]

    return _ok({
        'totalRequests': len(rows),
        'activeRequests': sum(1 for r in rows if r.get('status') in ('pending', 'taken', 'processing')),
        'completedRequests': sum(1 for r in rows if r.get('status') == 'paid'),
        'totalSpent': sum(r.get('estimatedCost', 0) for r in rows if r.get('status') == 'paid'),
        'recentRequests': sorted(rows, key=lambda r: r.get('createdAt', 0), reverse=True)[:5],
    })


@csrf_exempt
@require_http_methods(['GET'])
def stream_customer_requests(request):
    customer_id = request.GET.get('customerId')
    if not customer_id:
        return _err('customerId required')

    def event_stream():
        requests_ref = rtdb.reference('/requests')

        yield 'event: open\ndata: {"connected":true}\n\n'

        try:
            for event in requests_ref.listen(lambda e: e):
                tree = requests_ref.get() or {}

                mine = []
                for rid, r in tree.items():
                    if isinstance(r, dict) and r.get('customerId') == customer_id:
                        mine.append({'id': rid, **r})

                mine.sort(key=lambda r: r.get('createdAt', 0), reverse=True)

                payload = json.dumps({'requests': mine})
                yield f'event: requests\ndata: {payload}\n\n'

                if isinstance(event, dict) and event.get('event_type') == 'cancel':
                    break
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
    response['Connection'] = 'keep-alive'
    return response


@csrf_exempt
@require_http_methods(['PATCH'])
def update_location(request, rid):
    b = json.loads(request.body)
    lat = b.get('lat')
    lng = b.get('lng')
    if lat is None or lng is None:
        return _err('lat and lng required')
    rtdb.reference(f'/requests/{rid}/customerLocation').set({
        'lat': float(lat),
        'lng': float(lng),
        'updatedAt': {'.sv': 'timestamp'},
    })
    return _ok({'id': rid, 'lat': lat, 'lng': lng})


@csrf_exempt
@require_http_methods(['GET'])
def stream_location(request, rid):
    def event_stream():
        ref = rtdb.reference(f'/requests/{rid}/customerLocation')
        yield 'event: open\ndata: {"connected":true}\n\n'
        try:
            for _ in ref.listen(lambda e: e):
                data = ref.get() or {}
                yield f'event: location\ndata: {json.dumps(data)}\n\n'
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
    response['Connection'] = 'keep-alive'
    return response

@csrf_exempt
@require_http_methods(['GET'])
def get_location(request, rid):
    """
    Returns the latest customer location for the technician to track.
    """
    data = rtdb.reference(f'/requests/{rid}/customerLocation').get()
    if not data:
        return _err('No location yet', 404)
    return _ok(data)