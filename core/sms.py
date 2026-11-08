import africastalking
from django.conf import settings


_initialized = False


def _ensure_init():
    global _initialized
    if _initialized:
        return
    if not settings.AT_USERNAME or not settings.AT_API_KEY:
        raise RuntimeError("Africa's Talking credentials missing in settings")
    africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    _initialized = True


def send_sms(phone: str, message: str) -> dict:
    """
    Send an SMS via Africa's Talking.
    Returns { ok: bool, id: str | None, error: str | None }.
    Never raises — caller decides what to do on failure.
    """
    try:
        _ensure_init()
        sms = africastalking.SMS
        response = sms.send(
            message,
            [phone],
            sender_id=settings.AT_SENDER_ID or None,
        )
        data = response.get('SMSMessageData', {})
        recipients = data.get('Recipients', [])
        if recipients and recipients[0].get('status') == 'Success':
            return {'ok': True, 'id': recipients[0].get('messageId'), 'error': None}
        return {'ok': False, 'id': None, 'error': data.get('Message', 'Unknown SMS error')}
    except Exception as e:
        return {'ok': False, 'id': None, 'error': str(e)}