from django.core.exceptions import ValidationError
from attendance.exceptions import DitAuthError
from datetime import datetime

from attendance.models import MemberScan, PresentByDefault

from uuid import uuid4
import logging

from kiosk.models import Kiosk
from utils import read_data

logging.basicConfig(
    filename="logs/kiosk_scan.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)


def get_present_by_default(org_uuid: uuid4, uuid: uuid4) -> PresentByDefault:

    try:
        return PresentByDefault.objects.get(uuid=uuid, organization__uuid=org_uuid)
    except (PresentByDefault.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_present_by_default"
        )
    return None


def autenticated_dit(dit:str, kiosk:Kiosk, curr_dt:datetime):
    """ Auth for devices identifier token
    """
    if not dit:
        raise DitAuthError("Device Identifier Token not found.")

    kiosk_dit = kiosk.dit
    kiosk_dit_expiry = kiosk.dit_expiry

    if not kiosk_dit or not kiosk_dit_expiry:
        raise DitAuthError("Device identifier Token not found. Please login again.")

    if curr_dt > kiosk_dit_expiry:
        raise DitAuthError("Device Identifier Token Expired. Please login again.")

    decrypted_dit = read_data.decrypt_text(kiosk_dit)

    if decrypted_dit != dit:
        raise DitAuthError("Incorrect Device Identifier Token. Please login again.")


def is_last_scan_before_5min(scans: MemberScan, curr_dt:datetime) -> bool:
    """Member can create attendance scan after 5 min of every scan"""

    logging.info("================== Checking last scan is before 5 min or not ==================")
    last_scan = scans.order_by("-date_time").first()
    if last_scan is None:
        return False

    logging.info(
        f"=========== Last scan date time : {last_scan.date_time} ==========="
    )
    logging.info(f"=========== Curr date time : {curr_dt} ===========")

    diff = curr_dt - last_scan.date_time
    total_seconds = diff.total_seconds()
    logging.info(
        f"=========== diff : {diff}, in total seconds: {total_seconds} ==========="
    )
    logging.info(
        f"=========== is within 5 min : {(total_seconds / 60) <= 5}, total_min: {total_seconds / 60} ==========="
    )

    return (total_seconds / 60) <= 5
