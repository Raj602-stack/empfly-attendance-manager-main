from datetime import datetime, date
from member.models import Member
from organization.models import SystemLocation
from shift.models import LocationSettings
from utils.face_rec import get_face_encodings, get_image_encoding, get_user_ids
from utils.response import HTTP_400
from utils.utils import base64_to_contentfile, convert_to_time
from django.core.exceptions import ValidationError
import face_recognition
import numpy as np
from account.models import User
from geopy.distance import geodesic
from django.db.models import Q
from django.core.files.base import ContentFile

import logging

logger = logging.getLogger(__name__)


def face_rec(member: Member, image: str, req_user: User) -> User:
    if not image:
        raise ValidationError("Image is required.")

    member_images = member.member_images.all()

    if member_images.count() == 0:
        raise ValidationError("Member doesn't have any images. Please upload images.")

    known_face_encodings = get_face_encodings(member_images)

    known_face_ids = get_user_ids(member_images)

    image = base64_to_contentfile(image)
    if isinstance(image, ContentFile) is False:
        raise ValidationError("Image is not valid.")

    face_encoding = get_image_encoding(image)

    if not len(face_encoding):
        raise ValidationError("Invalid image.")

    logging.info("----- Face Found -----")

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.35
    )

    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

    logging.info(f"Matches: {matches}")
    logging.info(f"Distances: {face_distances}")

    try:
        best_match_index = np.argmin(face_distances)
    except ValueError as e:
        logging.error(e)
        raise ValidationError(
            "Your images for Face Recognition are not available. Please upload them on Web UI."
        )
    except Exception as e:
        logging.error(e)
        logging.critical(f"Add exception for {e.__class__.__name__} in ")
        raise ValidationError("No Match Found.")

    if bool(matches[best_match_index]) is False:
        raise ValidationError("The face does not match your previous FR images. Please try again.")

    user_id = known_face_ids[best_match_index]

    user = User.objects.get(id=user_id)

    if req_user != user:
        raise ValidationError("No Match Found.")

    return user, image




def face_rec_for_fr(member: Member, image: str, req_user: User) -> User:
    if not image:
        raise ValidationError("Image is required.")

    member_images = member.member_images.all()

    if member_images.count() == 0:
        raise ValidationError("Member doesn't have any images. Please upload images.")

    known_face_encodings = get_face_encodings(member_images)

    known_face_ids = get_user_ids(member_images)

    image = base64_to_contentfile(image)
    if isinstance(image, ContentFile) is False:
        raise ValidationError("Image is not valid.")

    face_encoding = get_image_encoding(image)

    if not len(face_encoding):
        raise ValidationError("Invalid image.")

    logging.info("----- Face Found -----")

    matches = face_recognition.compare_faces(
        known_face_encodings, face_encoding, tolerance=0.35
    )

    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

    logging.info(f"Matches: {matches}")
    logging.info(f"Distances: {face_distances}")

    try:
        best_match_index = np.argmin(face_distances)
    except ValueError as e:
        logging.error(e)
        raise ValidationError("Given image is not matching with previous FR images.")
    except Exception as e:
        logging.error(e)
        logging.critical(f"Add exception for {e.__class__.__name__} in ")
        raise ValidationError("Given image is not matching with previous FR images.")

    if bool(matches[best_match_index]) is False:
        raise ValidationError("Given image is not matching with previous FR images.")

    user_id = known_face_ids[best_match_index]

    user = User.objects.get(id=user_id)

    return user, image



def check_geo_fencing(
    check_in_time_restriction,
    org_enable_geo_fencing,
    shift,
    location_settings,
    is_shift_have_loc_settings,
    request,
    is_check_out,
    current_time,
):
    latitude, longitude, applicable_loc_settings = None, None, None

    if is_shift_have_loc_settings is True:
        # Location settings found for shift

        if org_enable_geo_fencing is True and shift.enable_geo_fencing is True:
            print("Enable Geo fencing : ", "True")
            print("Location Settings : ", location_settings)
            # already time is checked if enable check in time restriction is
            # enable already filtered .that kind of location settings

            latitude = request.data.get("latitude")
            longitude = request.data.get("longitude")

            if not latitude and not longitude:
                raise ValidationError("Latitude and Longitude is required.")

            scan_coords = (latitude, longitude)

            if is_check_out is True:

                system_location = location_settings.system_location

                location_settings_coords = (
                    system_location.latitude,
                    system_location.longitude,
                )

                distance = geodesic(location_settings_coords, scan_coords)
                radius = float(system_location.radius)

                if distance.m <= radius:
                    applicable_loc_settings = location_settings

            else:
                # Match with all location
                for location in location_settings:
                    location_settings_coords = (
                        location.system_location.latitude,
                        location.system_location.longitude,
                    )

                    distance = geodesic(location_settings_coords, scan_coords)
                    radius = float(location.system_location.radius)

                    if distance.m <= radius:
                        applicable_loc_settings = location
                        break

                if location_settings.exists() is False:
                    raise ValidationError("Location settings not found.")

            # time restriction already cheked
            if not applicable_loc_settings:
                raise ValidationError("Location Does Not Match.")

            print("Geo fencing is Success")
            return latitude, longitude, applicable_loc_settings
        else:
            if is_check_out:
                applicable_loc_settings = location_settings
            else:
                if location_settings.exists() is False:
                    raise ValidationError("Location not found.")

                # if geo fencing is false we can took first location settings.
                # becuse here the location settings dont have time restriction
                applicable_loc_settings = location_settings.first()

            return latitude, longitude, applicable_loc_settings

    elif is_shift_have_loc_settings is False:
        # shift dont have any location settings in this case defualt location conf
        # in the shift is used for create the scan.

        if is_check_out:

            if org_enable_geo_fencing is True and shift.enable_geo_fencing is True:

                latitude = request.data.get("latitude")
                longitude = request.data.get("longitude")

                if not latitude and not longitude:
                    raise ValidationError("Latitude and Longitude is required.")

                scan_coords = (latitude, longitude)
                system_location = shift.default_location

                default_location_coords = (
                    system_location.latitude,
                    system_location.longitude,
                )

                distance = geodesic(default_location_coords, scan_coords)
                radius = float(system_location.radius)

                if distance.m <= radius:
                    applicable_loc_settings = None
                else:
                    raise ValidationError("Location Does Not Match.")

            else:
                applicable_loc_settings = None

            return latitude, longitude, applicable_loc_settings

        else:
            current_time = convert_to_time(current_time)[0]
            end_time = shift.end_time

            if current_time > end_time:
                raise ValidationError("Cannot check in now.")

            # chek in time restrction
            if check_in_time_restriction:
                start_time = shift.start_time

                if current_time > start_time:
                    raise ValidationError("Cannot check in. Start time is exceeded.")

            if org_enable_geo_fencing is True and shift.enable_geo_fencing is True:

                latitude = request.data.get("latitude")
                longitude = request.data.get("longitude")

                if not latitude and not longitude:
                    raise ValidationError("Latitude and Longitude is required.")

                scan_coords = (latitude, longitude)
                system_location = shift.default_location

                default_location_coords = (
                    system_location.latitude,
                    system_location.longitude,
                )

                distance = geodesic(default_location_coords, scan_coords)
                radius = float(system_location.radius)

                if distance.m <= radius:
                    applicable_loc_settings = None
                else:
                    raise ValidationError("Location Does Not Match.")

            else:
                applicable_loc_settings = None

            return latitude, longitude, applicable_loc_settings


def geo_fencing(
    latitude,
    longitude,
    system_location: SystemLocation,
):
    """ Match user lat and log with system location lat and log.
    """

    if not latitude or not longitude:
        raise ValidationError("Latitude and Longitude is required.")

    system_coords = (
        system_location.latitude,
        system_location.longitude,
    )

    scan_coords = (latitude, longitude)
    distance = geodesic(system_coords, scan_coords)
    radius = float(system_location.radius)

    logging.info(f"=========== Geo fecning distance : {distance} ===========")
    logging.info(f"=========== Geo fecning meter : {distance.m} , radius: {radius} ===========")

    if distance.m <= radius:
        logging.info(f"=========== Geo Location Matched Successfully ===========")
        return system_location

    logging.info(f"=========== Geo Location Does Not Match. Outside of Geo fencing are ===========")
    raise ValidationError("Location Does Not Match. User is outside of the system location radius.")


def geo_fencing_for_loc_settings(
    latitude: str,
    longitude: str,
    location_settings: LocationSettings,
):
    """ Check geo fencing for location settings. If system location matched function will end.
    """
    if not latitude or not longitude:
        raise ValidationError("Latitude and Longitude is required.")

    for location in location_settings:

        system_loc = location.system_location
        try:
            return geo_fencing(latitude, longitude, system_loc)
        except ValidationError:
            pass

    raise ValidationError("Location Does Not Match.")
