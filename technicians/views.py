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
@require_http_methods(['POST'])
def register(request):
    b = json.loads(request.body)
    uid = b.get('userId')
    if not uid:
        return _err('userId required')

    new = rtdb.reference('/technicians').push()
    new.set({
        'userId': uid,
        'fullName': b.get('fullName', ''),
        'phone': b.get('phone', ''),
        'city': b.get('city', ''),
        'country': b.get('country', ''),
        'address': b.get('address', ''),
        'email': b.get('email', ''),
        'garage': b.get('garage', ''),
        'experience': b.get('experience', ''),
        'status': 'pending',
        'createdAt': {'.sv': 'timestamp'},
    })

    rtdb.reference(f'/users/{uid}/role').set('technician')

    return _ok({'id': new.key, 'status': 'pending'}, 201)


@csrf_exempt
@require_http_methods(['GET'])
def me(request):
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')

    techs = rtdb.reference('/technicians').get() or {}
    row = next(
        ({'id': k, **v} for k, v in techs.items() if v.get('userId') == uid),
        None,
    )
    if not row:
        return _err('Not registered', 404)
    return _ok(row)


@csrf_exempt
@require_http_methods(['GET'])
def available_requests(request):
    data = rtdb.reference('/technicianRequests').get() or {}
    rows = [{'id': k, **v} for k, v in data.items() if v.get('status') == 'pending']
    rows.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
    return _ok(rows)


@csrf_exempt
@require_http_methods(['POST'])
def accept_request(request, rid):
    b = json.loads(request.body)
    tid = b.get('technicianId')
    tname = b.get('technicianName', '')
    if not tid:
        return _err('technicianId required')

    patch = {'status': 'taken', 'technicianId': tid, 'technicianName': tname}
    rtdb.reference(f'/technicianRequests/{rid}').update(patch)
    rtdb.reference(f'/requests/{rid}').update(patch)
    return _ok({'id': rid, 'status': 'taken'})


@csrf_exempt
@require_http_methods(['GET'])
def my_jobs(request):
    tid = request.GET.get('technicianId')
    if not tid:
        return _err('technicianId required')

    data = rtdb.reference('/technicianRequests').get() or {}
    rows = [{'id': k, **v} for k, v in data.items() if v.get('technicianId') == tid]
    rows.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
    return _ok(rows)


@csrf_exempt
@require_http_methods(['GET'])
def revenue(request):
    tid = request.GET.get('technicianId')
    if not tid:
        return _err('technicianId required')

    data = rtdb.reference('/technicianRequests').get() or {}
    jobs = [
        {'id': k, **v}
        for k, v in data.items()
        if v.get('technicianId') == tid and v.get('status') == 'paid'
    ]
    total = sum(j.get('estimatedCost', 0) for j in jobs)
    commission = total * 0.1
    return _ok({
        'jobs': jobs,
        'total': total,
        'commission': commission,
        'net': total - commission,
    })


@csrf_exempt
@require_http_methods(['GET'])
def tech_dashboard(request):
    """
    Everything the technician dashboard needs in one call:
    profile row, active job count, total jobs, income, and recent jobs.
    """
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')

    techs = rtdb.reference('/technicians').get() or {}
    tech_row = next(
        ({'id': k, **v} for k, v in techs.items() if v.get('userId') == uid),
        None,
    )
    if not tech_row:
        return _err('Not registered as technician', 404)

    tid = tech_row['id']
    all_reqs = rtdb.reference('/technicianRequests').get() or {}
    jobs = [
        {'id': k, **v}
        for k, v in all_reqs.items()
        if v.get('technicianId') == tid
    ]

    active = [j for j in jobs if j.get('status') in ('taken', 'processing')]
    paid = [j for j in jobs if j.get('status') == 'paid']
    income = sum(j.get('estimatedCost', 0) for j in paid)

    return _ok({
        'technician': tech_row,
        'activeJobs': len(active),
        'totalJobs': len(jobs),
        'totalIncome': income,
        'recentJobs': sorted(
            jobs, key=lambda j: j.get('createdAt', 0), reverse=True
        )[:5],
    })


@csrf_exempt
@require_http_methods(['GET'])
def stream_technician_requests(request):
    """
    Server-Sent Events stream of every pending technician request.
    Watches Firebase /technicianRequests and pushes a fresh snapshot
    of pending rows on every change.
    """
    def event_stream():
        ref = rtdb.reference('/technicianRequests')

        yield 'event: open\ndata: {"connected":true}\n\n'

        try:
            for event in ref.listen(lambda e: e):
                tree = ref.get() or {}

                pending = []
                for rid, r in tree.items():
                    if isinstance(r, dict) and r.get('status') == 'pending':
                        pending.append({'id': rid, **r})

                pending.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
                payload = json.dumps({'requests': pending})
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
    return response


@csrf_exempt
@require_http_methods(['POST'])
def accept_request(request, rid):
    b = json.loads(request.body)
    tid = b.get('technicianId')
    tname = b.get('technicianName', '')
    tphone = b.get('technicianPhone', '')
    lat = b.get('lat')
    lng = b.get('lng')

    if not tid:
        return _err('technicianId required')

    patch = {
        'status': 'taken',
        'technicianId': tid,
        'technicianName': tname,
        'technicianPhone': tphone,
    }

    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        patch['technicianLat'] = float(lat)
        patch['technicianLng'] = float(lng)
        patch['technicianLocationUpdatedAt'] = {'.sv': 'timestamp'}

    rtdb.reference(f'/technicianRequests/{rid}').update(patch)
    rtdb.reference(f'/requests/{rid}').update(patch)

    return _ok({'id': rid, 'status': 'taken'})

# Add this import at the top
from owners.sms import send_technician_application_sms

@csrf_exempt
@require_http_methods(['POST'])
def register(request):
    b = json.loads(request.body)
    uid = b.get('userId')
    if not uid:
        return _err('userId required')

    new = rtdb.reference('/technicians').push()
    payload = {
        'userId': uid,
        'fullName': b.get('fullName', ''),
        'phone': b.get('phone', ''),
        'city': b.get('city', ''),
        'country': b.get('country', ''),
        'address': b.get('address', ''),
        'email': b.get('email', ''),
        'garage': b.get('garage', ''),
        'experience': b.get('experience', ''),
        'status': 'pending',
        'createdAt': {'.sv': 'timestamp'},
    }
    new.set(payload)

    # 1. Update user role
    rtdb.reference(f'/users/{uid}/role').set('technician')

    # 2. Send SMS to both Technician and Garage Owner
    sms_results = None
    garage_name = payload['garage']
    
    if garage_name:
        garages = rtdb.reference('/garages').get() or {}
        # Find the garage record to get the owner's phone
        garage_record = next((v for v in garages.values() if v.get('name') == garage_name), None)
        
        if garage_record:
            owner_phone = garage_record.get('primaryPhone', '')
            owner_name = garage_record.get('ownerName', 'Owner')
            
            sms_results = send_technician_application_sms(
                tech_phone=payload['phone'],
                tech_name=payload['fullName'],
                owner_phone=owner_phone,
                owner_name=owner_name,
                garage_name=garage_name
            )

    return _ok({
        'id': new.key, 
        'status': 'pending',
        'sms': sms_results
    }, 201)