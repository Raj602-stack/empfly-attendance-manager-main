import uuid
import logging

logger = logging.getLogger(__name__)

from django.core.exceptions import ValidationError
from kiosk.models import Kiosk
from organization.models import Organization


def get_kiosk_object(org:Organization, uuid:uuid, kiosk_obj:Kiosk=None):
    try:
        if not kiosk_obj:
            return Kiosk.objects.get(uuid=uuid, organization=org)
        
        return kiosk_obj.get(uuid=uuid)
    except (Kiosk.DoesNotExist, ValidationError) as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_shift")
        return None