import logging
from attendance.exceptions import CaptureFRImagError
from member.models import Member, MemberImage
from organization.models import SystemLocation
from rest_framework.response import Response
from rest_framework import status

import pandas as pd
import datetime as dt
import json

from django.conf import settings
from cryptography.fernet import Fernet

from utils import face_rec, utils

logger = logging.getLogger(__name__)

from django.core.files.base import ContentFile
import face_recognition

logging.basicConfig(
    filename="logs/fr_images.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)


def get_cipher_key():
    """ cipher_key user for encrypt and decrypt key.
    """
    return bytes(settings.CIPHER_KEY, 'utf-8')


def encrypt_text(text):
    """ Encrypt text using cryptography model.
        This function used for Encrypt kiosk access code.
    """

    key = get_cipher_key()

    try:
        text = (Fernet(key)
                .encrypt(bytes(text, 'utf-8'))
                .decode("utf-8"))
    except TypeError:
        logging.error(f"Cannot encrypt text of type {type(text)}")
    except Exception as e:
        logging.critical(f"Add exception {e.__class__.__name__} "
                         f"in encrypt_text")
        logging.error(f"Failed to encrypt text: {e}")
        return None

    return text


def decrypt_text(text):
    """ Convert back to orginal form.
    """

    key = get_cipher_key()

    try:
        text = (Fernet(key)
                .decrypt(bytes(text, 'utf-8'))
                .decode("utf-8"))
    except TypeError:
        logging.error(f"Cannot decrypt text of type {type(text)}")
    except Exception as e:
        logging.critical(f"Add exception {e.__class__.__name__} "
                         f"in decrypt_text")
        logging.error(f"Failed to decrypt text: {e}")
        return None

    return text



def get_json(response: Response, default: dict = None) -> dict:

    try:
        return response.json()
    except json.JSONDecodeError as e:
        logging.error(e)
    except Exception as e:
        logging.error(e)

    return default


def get_200_delete_response(model: str) -> Response:
    return Response(
        {"message": f"Successfully deleted {model}"},
        status=status.HTTP_200_OK,
    )


def get_403_response(message: str = None) -> Response:

    if message is None:
        message = "You do not have permission to perform this action."

    return Response(
        {"message": message},
        status=status.HTTP_403_FORBIDDEN,
    )


def get_404_response(object=None) -> Response:
    return Response(
        {"message": f"{object} not found"}, status=status.HTTP_404_NOT_FOUND
    )


def get_409_response(model: str, field: str) -> Response:
    return Response(
        {
            "message": f"{model} with {field} already exists.",
        },
        status=status.HTTP_409_CONFLICT
    )


def get_current_datetime() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def get_current_date() -> dt.datetime.date:
    return dt.datetime.now(dt.timezone.utc).date()


def get_current_datetime_as_str() -> str:
    return get_current_datetime().__str__()


def get_difference_between_datetimes_as_time(
    start_time: dt.datetime, end_time: dt.datetime
) -> dt.datetime.time:

    start_time = start_time.replace(tzinfo=None)
    end_time = end_time.replace(tzinfo=None)

    diff = end_time - start_time
    days, seconds = diff.days, diff.seconds
    hours = days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return dt.datetime.strptime(f"{hours}:{minutes}:{seconds}", "%H:%M:%S").time()


def read_csv(csv_file) -> pd.DataFrame:
    """ For export csv user provide csv file. This files we will read.
    """

    try:
        df = pd.read_csv(csv_file, encoding="ISO-8859-1")
        df = df.where(pd.notnull(df), None)
        # Replaces nan values with empty string
        df = df.fillna("")
        return df
    except UnicodeDecodeError as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__}"
            " in LocationsUploadCSVAPI > read_csv"
        )
        return None



def is_inactive_system_location(system_location:SystemLocation) -> bool:
    return system_location.status == "inactive"




def match_img_with_all_FR(image: str) -> dict:
    """ Find member from all org member images.
        Get fr images from org and match with member images.
    """
    # Error
    logging.info(
        "match_img_with_all_FR Started working"
    )

    fr_images = MemberImage.objects.filter(member__status="active").select_related("member")

    if not fr_images.exists():
        logging.info(
            "FR not exists in org"
        )
        return None, []

    known_face_encodings = face_rec.get_face_encodings(fr_images)

    known_face_ids = face_rec.get_member_ids(fr_images)

    logging.info(
        f"known_face_encodings = {len(known_face_encodings)}, known_face_member_ids = {len(known_face_ids)}"
    )

    image = utils.base64_to_contentfile(image)
    if isinstance(image, ContentFile) is False:
        logging.error("========= image type is not ContentFile =========")
        raise CaptureFRImagError("Invalid image.")

    face_encoding = face_rec.get_image_encoding(image)

    if not len(face_encoding):
        logging.error("========= face encoding have no length =========")
        raise CaptureFRImagError("No face detected.")

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.35
    )
    logging.info(f"Matches: {matches}")

    all_matched_member_ids = set()
    for index, match in enumerate(matches):
        logging.info(f"type of match before: {type(match)}")
        match = bool(match)
        logging.info(f"type of match after: {type(match)}")
        logging.info(f"match: {match}")
        if match is False:
            continue

        logging.info(f"member id: {known_face_ids[index]}")
        all_matched_member_ids.add(known_face_ids[index])

    len_all_match_member = len(all_matched_member_ids)
    logging.info(f"len_all_match_member: {len_all_match_member}")
    logging.info(f"all_matched_member_ids: {all_matched_member_ids}")

    if  len_all_match_member == 0:
        return None, all_matched_member_ids

    if len_all_match_member >= 2:
        logging.info("Multiple user match for the same FR image.")
        raise CaptureFRImagError("Unable to complete identification. Error CFR2012.")

    member_id = all_matched_member_ids.pop()
    logging.info(f"member id get using pop: {member_id}")

    try:
        member = Member.objects.get(id=member_id)
    except Member.DoesNotExist:
        raise CaptureFRImagError("Member not Found.")

    logging.info(f"member: {member}")
    logging.info(
        "Got member from find_member_from_all_fr_images function"
    )

    return member, all_matched_member_ids


def round_num(num) -> int:
    """Round number and convert to int.

    Args:
        num (int|float|str): number

    Returns:
        int: number
    """
    try:
        if num is None:
            return num

        if isinstance(num, str):
            num = float(num)
        return round(num)
    except Exception as err:
        print(err)
        print("Error occurred in round_num")
    return num
