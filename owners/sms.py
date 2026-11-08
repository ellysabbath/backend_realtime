"""
SMS helpers for owner and technician notifications.
"""
from django.conf import settings

try:
    from core.sms import send_sms as _core_send
except Exception:
    _core_send = None

import africastalking

_initialized = False


def _ensure_init():
    global _initialized
    if _initialized:
        return
    if not settings.AT_USERNAME or not settings.AT_API_KEY:
        raise RuntimeError("Africa's Talking credentials missing")
    africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    _initialized = True


def _send(phone: str, message: str) -> dict:
    if _core_send is not None:
        return _core_send(phone, message)

    try:
        _ensure_init()
        response = africastalking.SMS.send(
            message,
            [phone],
            sender_id=settings.AT_SENDER_ID or None,
        )
        data = response.get('SMSMessageData', {})
        recipients = data.get('Recipients', [])
        if recipients and recipients[0].get('status') == 'Success':
            return {'ok': True, 'id': recipients[0].get('messageId'), 'error': None}
        return {'ok': False, 'id': None, 'error': data.get('Message', 'Unknown error')}
    except Exception as e:
        return {'ok': False, 'id': None, 'error': str(e)}


def send_treaty_sms(phone: str, owner_name: str, garage_name: str, treaty_url: str) -> dict:
    """
    Send the treaty download link to the owner via SMS.
    """
    first_name = (owner_name or 'Owner').split(' ')[0]
    message = (
        f"Hello {first_name}, your tApp treaty for {garage_name} is ready. "
        f"Download, sign and re-upload it here: {treaty_url}"
    )
    return _send(phone, message)


def send_garage_approved_sms(phone: str, owner_name: str, garage_name: str, garage_id: str) -> dict:
    """
    Congratulate the owner on garage approval and invite them to add a new garage.
    """
    first_name = (owner_name or 'Owner').split(' ')[0]
    message = (
        f"Congratulations {first_name}! Your garage '{garage_name}' (ID: {garage_id}) "
        f"has been approved on tApp. You can now manage technicians and accept jobs. "
        f"Ready to expand? Open the app to add a new garage!"
    )
    return _send(phone, message)


def send_technician_application_sms(
    tech_phone: str, 
    tech_name: str, 
    owner_phone: str, 
    owner_name: str, 
    garage_name: str
) -> dict:
    """
    Sends two SMS messages: 
    1. To the technician confirming their application.
    2. To the garage owner notifying them of a new applicant.
    """
    
    tech_first = (tech_name or 'Technician').split(' ')[0]
    owner_first = (owner_name or 'Owner').split(' ')[0]
    
    # Message 1: To Technician
    tech_msg = (
        f"Hello {tech_first}, your application to join '{garage_name}' has been received. "
        f"The garage owner will review your profile shortly."
    )
    
    # Message 2: To Garage Owner
    owner_msg = (
        f"Hello {owner_first}, you have a new technician application on tApp! "
        f"{tech_name} has requested to join your garage '{garage_name}'. "
        f"Open the admin panel to review and approve."
    )

    # Send to technician
    tech_result = _send(tech_phone, tech_msg) if tech_phone else {'ok': False, 'error': 'No tech phone'}
    
    # Send to owner
    owner_result = _send(owner_phone, owner_msg) if owner_phone else {'ok': False, 'error': 'No owner phone'}

    return {
        'technician': tech_result,
        'owner': owner_result,
    }