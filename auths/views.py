import json
import secrets
import time
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.firebase import rtdb
from core.sms import send_sms


def _ok(d, s=200):
    return JsonResponse(d, status=s, safe=False)


def _err(m, s=400):
    return JsonResponse({'error': m}, status=s)


OTP_TTL = 300
RESEND_COOLDOWN = 60
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days


def _normalize_phone(phone: str) -> str:
    p = (phone or '').strip().replace(' ', '').replace('-', '')
    if p.startswith('0') and len(p) == 10:
        p = '+255' + p[1:]
    if p and not p.startswith('+'):
        p = '+' + p
    return p


def _generate_and_store(phone: str, extra: dict | None = None):
    ref = rtdb.reference(f'/otps/{phone}')
    existing = ref.get() or {}
    sent_at = int(existing.get('sentAt', 0))
    now = int(time.time())

    if sent_at and now - sent_at < RESEND_COOLDOWN:
        return None, RESEND_COOLDOWN - (now - sent_at)

    code = f'{secrets.randbelow(1000000):06d}'
    payload = {'code': code, 'expiresAt': now + OTP_TTL, 'sentAt': now}
    if extra:
        payload.update(extra)
    ref.set(payload)
    return code, 0


def _send_and_report(phone: str, code: str):
    result = send_sms(
        phone,
        f"Your tApp verification code is {code}. "
        f"It expires in 5 minutes. Do not share this code.",
    )
    if not result['ok']:
        rtdb.reference(f'/otps/{phone}').delete()
        return JsonResponse({'error': f"SMS delivery failed: {result['error']}"}, status=502)

    payload = {'sent': True, 'retryAfter': RESEND_COOLDOWN, 'smsId': result['id']}
    if settings.DEBUG:
        payload['debugCode'] = code
    return _ok(payload)


def _find_user_by_phone(phone: str):
    users = rtdb.reference('/users').get() or {}
    for uid, u in users.items():
        if u.get('phone') == phone:
            return uid, u
    return None, None


def _issue_token(user_id: str) -> str:
    token = secrets.token_hex(32)
    expires = int(time.time()) + TOKEN_TTL
    rtdb.reference(f'/tokens/{token}').set({
        'userId': user_id,
        'expiresAt': expires,
    })
    return token


def _resolve_token(token: str):
    if not token:
        return None, None
    saved = rtdb.reference(f'/tokens/{token}').get()
    if not saved:
        return None, None
    if int(saved.get('expiresAt', 0)) < int(time.time()):
        rtdb.reference(f'/tokens/{token}').delete()
        return None, None
    uid = saved.get('userId')
    if not uid:
        return None, None
    user = rtdb.reference(f'/users/{uid}').get()
    if not user:
        return None, None
    return uid, user


# ─────────────── LOGIN ───────────────

@csrf_exempt
@require_http_methods(['POST'])
def send_otp(request):
    b = json.loads(request.body)
    phone = _normalize_phone(b.get('phone'))
    if not phone:
        return _err('phone required')

    uid, _ = _find_user_by_phone(phone)
    if not uid:
        return _err('No account for this phone — please register first', 404)

    code, wait = _generate_and_store(phone, {'mode': 'login'})
    if code is None:
        return JsonResponse(
            {'error': 'Please wait before requesting another code', 'retryAfter': wait},
            status=429,
        )
    return _send_and_report(phone, code)


@csrf_exempt
@require_http_methods(['POST'])
def resend_otp(request):
    b = json.loads(request.body)
    phone = _normalize_phone(b.get('phone'))
    if not phone:
        return _err('phone required')

    existing = rtdb.reference(f'/otps/{phone}').get() or {}
    mode = existing.get('mode', 'login')
    extra = {'mode': mode}
    if mode == 'register' and existing.get('fullName'):
        extra['fullName'] = existing['fullName']

    code, wait = _generate_and_store(phone, extra)
    if code is None:
        return JsonResponse(
            {'error': 'Please wait before requesting another code', 'retryAfter': wait},
            status=429,
        )
    return _send_and_report(phone, code)


@csrf_exempt
@require_http_methods(['POST'])
def verify_otp(request):
    b = json.loads(request.body)
    phone = _normalize_phone(b.get('phone'))
    code = (b.get('code') or '').strip()
    if not phone or not code:
        return _err('phone and code required')

    saved = rtdb.reference(f'/otps/{phone}').get()
    if not saved:
        return _err('No OTP for this phone', 404)
    if int(saved['expiresAt']) < int(time.time()):
        return _err('OTP expired', 410)
    if saved['code'] != code:
        return _err('Invalid OTP', 401)

    rtdb.reference(f'/otps/{phone}').delete()

    uid, user = _find_user_by_phone(phone)
    if not uid:
        return _err('No account — register first', 404)

    rtdb.reference(f'/users/{uid}/verified').set(True)
    token = _issue_token(uid)

    return _ok({
        'userId': uid,
        'user': user,
        'token': token,
    })


# ─────────────── REGISTER ───────────────

@csrf_exempt
@require_http_methods(['POST'])
def register_start(request):
    b = json.loads(request.body)
    phone = _normalize_phone(b.get('phone'))
    full_name = (b.get('fullName') or '').strip()
    if not phone or not full_name:
        return _err('phone and fullName required')

    uid, _ = _find_user_by_phone(phone)
    if uid:
        return _err('This phone is already registered. Please sign in.', 409)

    code, wait = _generate_and_store(phone, {'mode': 'register', 'fullName': full_name})
    if code is None:
        return JsonResponse(
            {'error': 'Please wait before requesting another code', 'retryAfter': wait},
            status=429,
        )
    return _send_and_report(phone, code)


@csrf_exempt
@require_http_methods(['POST'])
def register_verify(request):
    b = json.loads(request.body)
    phone = _normalize_phone(b.get('phone'))
    code = (b.get('code') or '').strip()
    if not phone or not code:
        return _err('phone and code required')

    saved = rtdb.reference(f'/otps/{phone}').get()
    if not saved:
        return _err('No OTP for this phone', 404)
    if saved.get('mode') != 'register':
        return _err('This OTP is not for registration', 400)
    if int(saved['expiresAt']) < int(time.time()):
        return _err('OTP expired', 410)
    if saved['code'] != code:
        return _err('Invalid OTP', 401)

    full_name = saved.get('fullName', '').strip()
    if not full_name:
        return _err('Registration data missing — please start again', 400)

    existing_uid, existing_user = _find_user_by_phone(phone)
    if existing_uid:
        rtdb.reference(f'/otps/{phone}').delete()
        token = _issue_token(existing_uid)
        return _ok({
            'userId': existing_uid,
            'user': existing_user,
            'token': token,
        })

    new = rtdb.reference('/users').push()
    new.set({
        'fullName': full_name,
        'phone': phone,
        'role': 'customer',
        'status': 'active',
        'verified': True,
        'createdAt': {'.sv': 'timestamp'},
    })
    rtdb.reference(f'/otps/{phone}').delete()
    token = _issue_token(new.key)

    return _ok({
        'userId': new.key,
        'user': {
            'fullName': full_name,
            'phone': phone,
            'role': 'customer',
            'verified': True,
        },
        'token': token,
    }, 201)


# ─────────────── SESSION ───────────────

@csrf_exempt
@require_http_methods(['GET'])
def me(request):
    """Resolve a token to a user. Used on page refresh to restore session."""
    token = request.GET.get('token')
    uid, user = _resolve_token(token)
    if not uid:
        return _err('Invalid or expired token', 401)
    return _ok({'userId': uid, 'user': user})


@csrf_exempt
@require_http_methods(['POST'])
def logout(request):
    b = json.loads(request.body)
    token = b.get('token')
    if token:
        rtdb.reference(f'/tokens/{token}').delete()
    return _ok({'loggedOut': True})


@csrf_exempt
@require_http_methods(['PATCH'])
def set_role(request, uid):
    b = json.loads(request.body)
    role = b.get('role')
    if role not in ('customer', 'technician', 'owner', 'admin'):
        return _err('invalid role')
    rtdb.reference(f'/users/{uid}/role').set(role)
    return _ok({'id': uid, 'role': role})