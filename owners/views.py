from django.shortcuts import render

# Create your views here.
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.firebase import rtdb
from .utils import generate_treaty_pdf
from .sms import send_treaty_sms


def _ok(d, s=200): return JsonResponse(d, status=s, safe=False)
def _err(m, s=400): return JsonResponse({'error': m}, status=s)


@csrf_exempt
@require_http_methods(['POST'])
def register(request):
    b = json.loads(request.body)
    uid = b.get('userId')
    if not uid: return _err('userId required')

    new = rtdb.reference('/garages').push()
    payload = {
        'ownerId': uid,
        'ownerName': b.get('fullName', ''),
        'name': b.get('garageName', ''),
        'address': b.get('address', ''),
        'email': b.get('email', ''),
        'primaryPhone': b.get('primaryPhone', ''),
        'secondaryPhone': b.get('secondaryPhone', ''),
        'status': 'pending',
        'technicians': 0,
        'revenue': 0,
        'createdAt': {'.sv': 'timestamp'},
    }
    new.set(payload)

    # Send treaty SMS to the owner after registration
    sms_result = None
    phone = payload['primaryPhone']
    if phone:
        base_url = getattr(settings, 'PUBLIC_BASE_URL', 'http://127.0.0.1:8000')
        treaty_url = f"{base_url}/api/owner/treaty/{new.key}/download/"
        sms_result = send_treaty_sms(
            phone,
            payload['ownerName'],
            payload['name'],
            treaty_url,
        )

    return _ok({
        'id': new.key,
        'status': 'pending',
        'sms': sms_result,
    }, 201)


@csrf_exempt
@require_http_methods(['GET'])
def me(request):
    """
    Return ALL garages owned by the user as an array.
    """
    uid = request.GET.get('userId')
    if not uid:
        return _err('userId required')

    garages = rtdb.reference('/garages').get() or {}
    owned = [
        {'id': k, **v}
        for k, v in garages.items()
        if v.get('ownerId') == uid
    ]
    # Sort by creation time (newest first) so the UI shows the latest garage on top
    owned.sort(key=lambda g: g.get('createdAt', 0), reverse=True)

    return _ok(owned)


@csrf_exempt
@require_http_methods(['POST'])
def pay_fee(request, gid):
    b = json.loads(request.body)
    t = rtdb.reference('/treaties').push()
    t.set({
        'garageId': gid,
        'amount': 50000,
        'method': b.get('method', 'cash'),
        'reference': b.get('reference', ''),
        'status': 'pending',
        'createdAt': {'.sv': 'timestamp'},
    })
    rtdb.reference(f'/garages/{gid}/treatyId').set(t.key)
    return _ok({'treatyId': t.key, 'status': 'pending'}, 201)


@csrf_exempt
@require_http_methods(['GET'])
def dashboard(request):
    """
    Return dashboard stats for one specific garage:
    - The garage record itself
    - All technicians assigned to it
    - All requests handled by those technicians
    - Total revenue from paid requests
    """
    gid = request.GET.get('garageId')
    if not gid:
        return _err('garageId required')

    garage = rtdb.reference(f'/garages/{gid}').get()
    if not garage:
        return _err('Not found', 404)

    techs = rtdb.reference('/technicians').get() or {}
    my_techs = [
        {'id': k, **v}
        for k, v in techs.items()
        if v.get('garage') == garage.get('name')
    ]

    reqs = rtdb.reference('/requests').get() or {}
    tech_names = [t.get('fullName') for t in my_techs if t.get('fullName')]
    my_reqs = [
        {'id': k, **v}
        for k, v in reqs.items()
        if v.get('technicianName') in tech_names
    ]
    revenue = sum(r.get('estimatedCost', 0) for r in my_reqs if r.get('status') == 'paid')

    return _ok({
        'garage': {'id': gid, **garage},
        'technicians': my_techs,
        'requests': my_reqs,
        'revenue': revenue,
        'totalTechnicians': len(my_techs),
        'totalRequests': len(my_reqs),
    })


@require_http_methods(['GET'])
def download_treaty(request, gid):
    """
    Stream the generated treaty PDF for a given garage.
    """
    garage = rtdb.reference(f'/garages/{gid}').get()
    if not garage:
        return _err('Garage not found', 404)

    owner_uid = garage.get('ownerId')
    owner = {}
    if owner_uid:
        owner = rtdb.reference(f'/users/{owner_uid}').get() or {}

    pdf_bytes = generate_treaty_pdf(garage, owner)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    safe_name = (garage.get('name') or 'garage').replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="tApp_Treaty_{safe_name}.pdf"'
    return response

@csrf_exempt
@require_http_methods(['GET'])
def garage_documents(request, gid):
    """
    Returns a complete record of a garage:
    - The garage record itself
    - The treaty generated at registration
    - Every technician who joined this garage
    """
    garage = rtdb.reference(f'/garages/{gid}').get()
    if not garage:
        return _err('Garage not found', 404)

    # Treaty — created at registration time and stored under /treaties
    treaty_id = garage.get('treatyId')
    treaty = {}
    if treaty_id:
        treaty = rtdb.reference(f'/treaties/{treaty_id}').get() or {}
        treaty['id'] = treaty_id

    # Technicians who joined this garage (matched by garage name)
    techs_tree = rtdb.reference('/technicians').get() or {}
    technicians = [
        {'id': k, **v}
        for k, v in techs_tree.items()
        if v.get('garage') == garage.get('name')
    ]
    # Newest first
    technicians.sort(key=lambda t: t.get('createdAt', 0), reverse=True)

    return _ok({
        'garage': {'id': gid, **garage},
        'treaty': treaty,
        'technicians': technicians,
    })






# =============================  file  upload  treaty  =============
import base64

@csrf_exempt
@require_http_methods(['POST'])
def upload_treaty(request, gid):
    """
    Accept a signed treaty PDF, convert it to base64, and store it in Firebase.
    """
    garage = rtdb.reference(f'/garages/{gid}').get()
    if not garage:
        return _err('Garage not found', 404)

    file = request.FILES.get('file')
    if not file:
        return _err('No file uploaded')
    
    if file.content_type != 'application/pdf':
        return _err('Only PDF files are allowed')

    # Read the file and encode it as a base64 string
    file_data = file.read()
    encoded_data = base64.b64encode(file_data).decode('utf-8')
    
    # Save the base64 string to Firebase
    rtdb.reference(f'/garages/{gid}/signedTreaty').set({
        'fileName': file.name,
        'data': encoded_data,
        'uploadedAt': {'.sv': 'timestamp'},
    })

    # Update the treaty status if it exists, or create a new one
    treaty_id = garage.get('treatyId')
    if treaty_id:
        rtdb.reference(f'/treaties/{treaty_id}').update({'status': 'submitted'})
    else:
        # If the treaty doesn't exist yet, create it
        new_t = rtdb.reference('/treaties').push()
        new_t.set({
            'garageId': gid,
            'amount': 50000,
            'status': 'submitted',
            'createdAt': {'.sv': 'timestamp'},
        })
        rtdb.reference(f'/garages/{gid}/treatyId').set(new_t.key)

    return _ok({'status': 'submitted'}, 200)


@csrf_exempt
@require_http_methods(['GET'])
def list_active_garages(request):
    """
    Returns a list of garages with status 'active'.
    Used by the technician registration dropdown.
    """
    garages = rtdb.reference('/garages').get() or {}
    
    active_garages = [
        {
            'id': k, 
            'name': v.get('name'), 
            'city': v.get('address')
        }
        for k, v in garages.items() 
        if v.get('status') == 'active'
    ]
    
    # Sort alphabetically by name
    active_garages.sort(key=lambda x: x.get('name', ''))
    
    return _ok(active_garages)


from owners.sms import send_technician_application_sms  # Add this import

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
    rtdb.reference(f'/users/{uid}/role').set('technician')

    # --- NEW SMS LOGIC ---
    sms_results = None
    garage_name = payload['garage']
    
    if garage_name:
        # 1. Find the garage record to get the owner's phone
        garages = rtdb.reference('/garages').get() or {}
        garage_record = next((v for v in garages.values() if v.get('name') == garage_name), None)
        
        if garage_record:
            owner_phone = garage_record.get('primaryPhone', '')
            owner_name = garage_record.get('ownerName', 'Owner')
            
            # 2. Send the SMS
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


# Add these to owners/views.py

@csrf_exempt
@require_http_methods(['GET'])
def get_garage_technicians(request):
    """
    Returns all technicians who applied to the garages owned by this user.
    """
    uid = request.GET.get('ownerId')
    if not uid:
        return _err('ownerId required')

    # 1. Find all garages owned by this user
    garages = rtdb.reference('/garages').get() or {}
    my_garages = [v.get('name') for k, v in garages.items() if v.get('ownerId') == uid]

    # 2. Find all technicians who applied to those garages
    techs = rtdb.reference('/technicians').get() or {}
    my_techs = [
        {'id': k, **v} 
        for k, v in techs.items() 
        if v.get('garage') in my_garages
    ]
    my_techs.sort(key=lambda t: t.get('createdAt', 0), reverse=True)

    return _ok(my_techs)


@csrf_exempt
@require_http_methods(['PATCH'])
def approve_technician(request, tid):
    """
    Allows an owner to approve a technician.
    """
    b = json.loads(request.body)
    new_status = b.get('status')
    
    if new_status not in ('active', 'rejected'):
        return _err('Invalid status')

    tech = rtdb.reference(f'/technicians/{tid}').get()
    if not tech:
        return _err('Technician not found', 404)

    rtdb.reference(f'/technicians/{tid}').update({
        'status': new_status,
        'approvedAt': {'.sv': 'timestamp'}
    })

    return _ok({'id': tid, 'status': new_status})
