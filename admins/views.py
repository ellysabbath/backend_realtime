from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.firebase import rtdb
from core.sms import send_sms


def _ok(d, s=200):
    return JsonResponse(d, status=s, safe=False)


def _err(m, s=400):
    return JsonResponse({'error': m}, status=s)


# ─────────────── USERS ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def users(request):
    data = rtdb.reference('/users').get() or {}
    return _ok([{'id': k, **v} for k, v in data.items()])


@csrf_exempt
@require_http_methods(['PATCH'])
def user_status(request, uid):
    b = json.loads(request.body)
    rtdb.reference(f'/users/{uid}').update({'status': b.get('status', 'active')})
    return _ok({'id': uid})


@csrf_exempt
@require_http_methods(['POST'])
def create_user(request):
    b = json.loads(request.body)
    full_name = (b.get('fullName') or '').strip()
    phone = (b.get('phone') or '').strip()
    role = b.get('role', 'customer')

    if not full_name or not phone:
        return _err('fullName and phone required')
    if role not in ('customer', 'technician', 'owner', 'admin'):
        return _err('invalid role')

    users_data = rtdb.reference('/users').get() or {}
    existing = next((uid for uid, u in users_data.items() if u.get('phone') == phone), None)
    if existing:
        return _err('A user with this phone already exists', 409)

    new = rtdb.reference('/users').push()
    new.set({
        'fullName': full_name,
        'phone': phone,
        'role': role,
        'status': 'active',
        'verified': False,
        'createdAt': {'.sv': 'timestamp'},
    })
    return _ok({
        'id': new.key,
        'user': {
            'fullName': full_name,
            'phone': phone,
            'role': role,
            'status': 'active',
            'verified': False,
        },
    }, 201)


@csrf_exempt
@require_http_methods(['PATCH'])
def update_user(request, uid):
    b = json.loads(request.body)
    patch = {}

    if 'fullName' in b:
        if not isinstance(b['fullName'], str) or not b['fullName'].strip():
            return _err('fullName must be a non-empty string')
        patch['fullName'] = b['fullName'].strip()

    if 'phone' in b:
        phone = (b['phone'] or '').strip()
        if not phone:
            return _err('phone must be non-empty')
        users_data = rtdb.reference('/users').get() or {}
        clash = next(
            (k for k, u in users_data.items() if k != uid and u.get('phone') == phone),
            None,
        )
        if clash:
            return _err('Another user already has this phone', 409)
        patch['phone'] = phone

    if 'role' in b:
        if b['role'] not in ('customer', 'technician', 'owner', 'admin'):
            return _err('invalid role')
        patch['role'] = b['role']

    if 'status' in b:
        if b['status'] not in ('active', 'suspended'):
            return _err('invalid status')
        patch['status'] = b['status']

    if not patch:
        return _err('no fields to update')

    rtdb.reference(f'/users/{uid}').update(patch)
    return _ok({'id': uid, 'updated': patch})


@csrf_exempt
@require_http_methods(['DELETE'])
def delete_user(request, uid):
    rtdb.reference(f'/users/{uid}').delete()

    tokens = rtdb.reference('/tokens').get() or {}
    for token, row in tokens.items():
        if isinstance(row, dict) and row.get('userId') == uid:
            rtdb.reference(f'/tokens/{token}').delete()

    return _ok({'id': uid, 'deleted': True})


# ─────────────── TECHNICIANS ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def technicians(request):
    data = rtdb.reference('/technicians').get() or {}
    return _ok([{'id': k, **v} for k, v in data.items()])


@csrf_exempt
@require_http_methods(['PATCH'])
def technician_status(request, tid):
    b = json.loads(request.body)
    new_status = b.get('status', 'active')

    ref = rtdb.reference(f'/technicians/{tid}')
    current = ref.get() or {}
    if not current:
        return _err('Technician not found', 404)

    previous_status = current.get('status', 'pending')
    technician_id = current.get('technicianId') or f'T-{tid[:6].upper()}'

    patch = {'status': new_status}
    if new_status == 'active':
        patch['technicianId'] = technician_id
        patch['activatedAt'] = {'.sv': 'timestamp'}

    ref.update(patch)

    # Send SMS only on approval transition (pending/suspended -> active)
    sms_report = None
    if new_status == 'active' and previous_status != 'active':
        phone = (current.get('phone') or '').strip()
        full_name = current.get('fullName') or 'Technician'
        garage = current.get('garage') or 'tApp'

        if phone:
            first_name = full_name.split(' ')[0]

            msg1 = (
                f"Congratulations {first_name}! Your tApp technician account "
                f"has been approved. Your Technician ID is {technician_id} "
                f"and you are registered under {garage}. You can now accept "
                f"job requests in the app."
            )

            msg2 = (
                f"Next step: you can open your own garage on tApp. "
                f"As a verified technician you are eligible to register as "
                f"a Garage Owner. Open the app and choose "
                f"\"Become Garage Owner\" to get started."
            )

            r1 = send_sms(phone, msg1)
            r2 = send_sms(phone, msg2)

            sms_report = {
                'phone': phone,
                'message1': {'sent': r1['ok'], 'error': r1['error']},
                'message2': {'sent': r2['ok'], 'error': r2['error']},
            }

    return _ok({
        'id': tid,
        'status': new_status,
        'technicianId': technician_id if new_status == 'active' else current.get('technicianId'),
        'sms': sms_report,
    })


@csrf_exempt
@require_http_methods(['DELETE'])
def delete_technician(request, tid):
    rtdb.reference(f'/technicians/{tid}').delete()
    return _ok({'id': tid, 'deleted': True})


# ─────────────── GARAGES ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def garages(request):
    data = rtdb.reference('/garages').get() or {}
    return _ok([{'id': k, **v} for k, v in data.items()])


@csrf_exempt
@require_http_methods(['PATCH'])
def garage_status(request, gid):
    b = json.loads(request.body)
    s = b.get('status', 'active')
    rtdb.reference(f'/garages/{gid}').update({'status': s})
    if s == 'active':
        rtdb.reference(f'/garages/{gid}/garageId').set(f'G-{gid[:6].upper()}')
    return _ok({'id': gid, 'status': s})


# ─────────────── STATS ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def stats(request):
    reqs = rtdb.reference('/requests').get() or {}
    users_ = rtdb.reference('/users').get() or {}
    garages_ = rtdb.reference('/garages').get() or {}
    techs = rtdb.reference('/technicians').get() or {}

    return _ok({
        'totalUsers': len(users_),
        'totalRequests': len(reqs),
        'activeRequests': sum(1 for r in reqs.values()
                              if r.get('status') in ('pending', 'taken', 'processing')),
        'paidRequests': sum(1 for r in reqs.values() if r.get('status') == 'paid'),
        'totalGarages': len(garages_),
        'totalTechnicians': len(techs),
        'revenue': sum(r.get('estimatedCost', 0) for r in reqs.values()
                       if r.get('status') == 'paid'),
        'pendingGarages': sum(1 for g in garages_.values() if g.get('status') == 'pending'),
        'pendingTechnicians': sum(1 for t in techs.values() if t.get('status') == 'pending'),
    })

# ─────────────── REQUESTS ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def requests(request):
    data = rtdb.reference('/requests').get() or {}
    rows = [{'id': k, **v} for k, v in data.items()]
    rows.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
    return _ok(rows)


@csrf_exempt
@require_http_methods(['PATCH'])
def update_request(request, rid):
    b = json.loads(request.body)
    patch = {}

    for field in ('status', 'estimatedCost', 'technicianName', 'technicianPhone',
                  'technicianLocation', 'technicianId'):
        if field in b:
            patch[field] = b[field]

    if 'status' in patch and patch['status'] not in (
        'pending', 'taken', 'processing', 'paid', 'cancelled',
    ):
        return _err('invalid status')
    if 'estimatedCost' in patch:
        try:
            patch['estimatedCost'] = float(patch['estimatedCost'])
        except (TypeError, ValueError):
            return _err('estimatedCost must be a number')

    if not patch:
        return _err('no fields to update')

    rtdb.reference(f'/requests/{rid}').update(patch)
    # Mirror non-cancelled updates into technicianRequests
    if patch.get('status') != 'cancelled':
        rtdb.reference(f'/technicianRequests/{rid}').update(patch)
    return _ok({'id': rid, 'updated': patch})


@csrf_exempt
@require_http_methods(['DELETE'])
def delete_request(request, rid):
    rtdb.reference(f'/requests/{rid}').delete()
    rtdb.reference(f'/technicianRequests/{rid}').delete()
    return _ok({'id': rid, 'deleted': True})