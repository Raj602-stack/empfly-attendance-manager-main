import json
from uuid import uuid4
from member.models import Member, MemberImage

import numpy as np
import PIL.Image
import PIL.ImageOps
import face_recognition

import logging


logger = logging.getLogger(__name__)


def exif_transpose(img):
    if not img:
        return img

    exif_orientation_tag = 274

    # Check for EXIF data (only present on some files)
    if (
        hasattr(img, "_getexif")
        and isinstance(img._getexif(), dict)
        and exif_orientation_tag in img._getexif()
    ):
        exif_data = img._getexif()
        orientation = exif_data[exif_orientation_tag]

        # Handle EXIF Orientation
        if orientation == 1:
            # Normal image - nothing to do!
            pass
        elif orientation == 2:
            # Mirrored left to right
            img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            # Rotated 180 degrees
            img = img.rotate(180)
        elif orientation == 4:
            # Mirrored top to bottom
            img = img.rotate(180).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            # Mirrored along top-left diagonal
            img = img.rotate(-90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            # Rotated 90 degrees
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            # Mirrored along top-right diagonal
            img = img.rotate(90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            # Rotated 270 degrees
            img = img.rotate(90, expand=True)

    return img


def load_image_file(file, mode="RGB"):

    img = PIL.Image.open(file)

    if hasattr(PIL.ImageOps, "exif_transpose"):
        # Very recent versions of PIL can do exit transpose internally
        img = PIL.ImageOps.exif_transpose(img)
    else:
        # Otherwise, do the exif transpose ourselves
        img = exif_transpose(img)

    img = img.convert(mode)

    return np.array(img)


def get_image_encoding(image: "Image") -> np.ndarray:

    try:
        image = load_image_file(image)
        return face_recognition.face_encodings(image)[0]
    except IndexError as e:
        logger.error(f"{e}. No face detected")
        return []
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_image_encoding"
        )
        return []


def convert_encoding_to_json(encoding: np.ndarray) -> json:
    """
    Converts encoding to JSON

    Args:
        encoding (np.ndarray): Image encoding matrix

    Returns:
        JSON: JSON representation of image encoding
    """

    # Converts numpy array to python list
    encoding_arr = encoding.tolist()
    # Converts encoding to JSON
    json_data = json.dumps(encoding_arr)
    # Returns JSON object
    return json_data


def get_face_encodings(queryset: "Queryest") -> list:
    """ Member Images model have encoding. this is we will
        save while saving member image. Encoding use for 
        face rec.
    """

    encodings = []
    for member_image in queryset:
        encoding = np.asarray(json.loads(member_image.encoding))
        encodings.append(encoding)
    return encodings


def get_user_ids(queryset: "Queryset") -> list:
    """ Get user id for find user after face rec.
        Member images models have user ids.
    """

    user_ids = []
    for member_image in queryset:
        user_id = str(member_image.member.user.id)
        user_ids.append(user_id)
    return user_ids

def get_member_ids(queryset: "Queryset") -> list:
    """ Get user id for find user after face rec.
        Member images models have user ids.
    """

    member_ids = []
    for member_image in queryset:
        member_id = str(member_image.member.id)
        member_ids.append(member_id)
    return member_ids

# TODO deprecated
def identify_face(org_uuid: uuid4, face_encoding: list, actual_user_id: int) -> bool:

    if len(face_encoding) == 0:
        return False

    member_images = MemberImage.objects.filter(member__organization__uuid=org_uuid)
    # Get encodings from MemberImages
    known_face_encodings = get_face_encodings(member_images)
    # Get corresponding User IDs of MemberImages
    known_face_ids = get_user_ids(member_images)

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.4
    )
    user_id = None

    # Check if the face's encodings matches with any in the database
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    best_match_index = np.argmin(face_distances)
    if matches[best_match_index]:
        try:
            user_id = known_face_ids[best_match_index]
            return actual_user_id == int(user_id)
        except (TypeError, IndexError) as e:
            logger.error(e)
            return False
    return False
