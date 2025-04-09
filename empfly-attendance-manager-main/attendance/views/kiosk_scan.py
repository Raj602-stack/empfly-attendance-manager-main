import logging
from datetime import timedelta, datetime
from account.models import User
from attendance.attendance_utils import geo_fencing, geo_fencing_for_loc_settings
from attendance.exceptions import KioskScanError
from attendance.utils import autenticated_dit, is_last_scan_before_5min
from kiosk.models import Kiosk
from kiosk.serializers import KioskSerializer
from member.models import Member, MemberImage
from organization.models import Organization, SystemLocation
from attendance.models import MemberScan
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import F
from attendance.serializers import MemberScanSerializer
from attendance import exceptions
from django.utils import timezone as tz
import zoneinfo
from env import scan_fr_in_instance


from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.models import ShiftScheduleLog
from utils import fetch_data, read_data
from utils import face_rec
from utils.response import HTTP_200, HTTP_400
from utils import utils
import face_recognition
from geopy.distance import geodesic
from django.db.models import Q
import numpy as np
from utils.date_time import convert_dt_to_another_tz, curr_date_time_with_tz, curr_dt_with_org_tz
from utils import shift
from utils import utils
import uuid



logging.basicConfig(
    filename="logs/kiosk_scan.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)



class KioskAccessAPI(views.APIView):

    permission_classes = []
    # serializer_class = VisitorSerializer

    def random_string(self):
        return str(uuid.uuid4())

    def validate_dit(self, dit, kiosk, curr_dt):
        """Check dit key is valid or not

        Args:
            dit (_type_): _description_
            kiosk (_type_): _description_
            curr_dt (_type_): _description_

        Returns:
            _type_: _description_
        """
        if not dit:
            return "Empfly Kiosk is being used on another device, please ask Admin to Reset Access.", False

        kiosk_dit = kiosk.dit
        kiosk_dit_expiry = kiosk.dit_expiry

        if not kiosk_dit or not kiosk_dit_expiry:
            return None, True

        if curr_dt > kiosk_dit_expiry:
            return None, True

        decrypted_dit = read_data.decrypt_text(kiosk_dit)

        if decrypted_dit != dit:
            return "Empfly Kiosk is being used on another device, please ask Admin to Reset Access.", True

        return None, True

    def post(self, request, *args, **kwargs):

        # pwd for kiosk.
        access_code = request.data.get("access_code")
        user_dit = request.data.get("dit")

        if not access_code:
            return HTTP_400({}, {"message": "Access code is required."})

        try:
            kiosk_obj = Kiosk.objects.get(uuid=kwargs["uuid"])
        except Kiosk.DoesNotExist:
            return read_data.get_404_response("Kiosk")

        kiosk_access_code = read_data.decrypt_text(kiosk_obj.access_code)
        if kiosk_access_code != access_code:
            return HTTP_400({}, {"message": "Invalid access code."})

        # TODO check
        org_tz = kiosk_obj.organization.timezone
        date_and_time = curr_date_time_with_tz(org_tz)

        if user_dit:
            kiosk_dit = kiosk_obj.dit
            kiosk_dit_expiry = kiosk_obj.dit_expiry

            if kiosk_dit and kiosk_dit_expiry:
                if date_and_time <= kiosk_dit_expiry:
                    decrypted_dit = read_data.decrypt_text(kiosk_dit)
                    if decrypted_dit != user_dit:
                        return HTTP_400(
                            {},
                            {
                                "message": "Incorrect dit key."
                            },
                        )
                    dit_expiry = kiosk_obj.dit_expiry
                    if dit_expiry:
                        dit_expiry = convert_dt_to_another_tz(dit_expiry, org_tz)

                    kiosk_serializer = KioskSerializer(kiosk_obj)
                    return HTTP_200({"dit": user_dit, "dit_expiry": dit_expiry, "kiosk": kiosk_serializer.data})
        elif (
            kiosk_obj.dit
            and kiosk_obj.dit_expiry
            and date_and_time <= kiosk_obj.dit_expiry
        ):
            return HTTP_400(
                {},
                {
                    "message": "Empfly Kiosk is being used on another device, please ask Admin to Reset Access."
                },
            )

        org = kiosk_obj.organization
        org_exp_time = org.kiosk_management_settings.get("dit_expiry", 24)

        dit = self.random_string()
        kiosk_obj.dit = read_data.encrypt_text(dit)
        kiosk_obj.dit_expiry = date_and_time + timedelta(hours=org_exp_time)
        kiosk_obj.save()

        dit_expiry = convert_dt_to_another_tz(kiosk_obj.dit_expiry, org_tz)

        kiosk_serializer = KioskSerializer(kiosk_obj)
        return HTTP_200(
            {
                "dit": dit,
                "dit_expiry": dit_expiry,
                "kiosk": kiosk_serializer.data
            }
        )


class KioskLogoutAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        # pwd for kiosk.
        access_code = request.data.get("access_code")
        user_dit = request.data.get("dit")

        if not access_code:
            return HTTP_400({}, {"message": "Access code is required."})

        if not user_dit:
            return HTTP_400({}, {"message": "dit code is required."})

        try:
            kiosk_obj = Kiosk.objects.get(uuid=kwargs["uuid"])
        except Kiosk.DoesNotExist:
            return read_data.get_404_response("Kiosk")

        kiosk_access_code = read_data.decrypt_text(kiosk_obj.access_code)
        if kiosk_access_code != access_code:
            return HTTP_400({}, {"message": "Invalid access code."})

        kiosk_dit = kiosk_obj.dit

        if not kiosk_dit:
            return HTTP_200({})

        decrypted_dit = read_data.decrypt_text(kiosk_dit)

        if decrypted_dit != user_dit:
            return HTTP_400({}, {"message": "Invalid dit."})

        kiosk_obj.dit = None
        kiosk_obj.dit_expiry = None
        kiosk_obj.save()

        return HTTP_200({})




class KioskScanAPI(views.APIView):

    permission_classes = []
    org: Organization
    req_user: User
    curr_time: datetime
    curr_date: datetime
    yesterday_date: datetime
    date_time: datetime
    latitude: str
    longitude: str
    tomorrow_date: datetime
    today_date: datetime
    member: Member
    image: str
    org_enable_face_recognition: bool
    org_enable_geo_fencing: bool
    org_timezone: zoneinfo.ZoneInfo

    curr_scan_type = {
        "check_in": "check_out",
        "check_out": "check_in",
    }

    temp_date_time = datetime.strptime("05/10/09 00:00:00", "%d/%m/%y %H:%M:%S")
    day_start_time = temp_date_time.time()
    day_end_time = (temp_date_time - timedelta(microseconds=1)).time()



    def geo_fencing_tomorrow_check_in(self, log, actual_date) ->  SystemLocation:
        """
        Check restrictions
        """
        logging.info("--------------- geo_fencing_tomorrow_check_in ------------")
        shift = log.shift
        location_settings = log.location_settings.all().order_by("start_time")
        location_settings = location_settings.filter(system_location__status="active").filter(
            Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__gte=actual_date,
            )
            | Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__isnull=True,
            )
        )

        logging.info(f"shift : {shift}")
        logging.info(f"log : {log}")
        logging.info(f"actual date : {actual_date}")

        # Geo fencing will auto enable if loc settings is exists
        if location_settings.exists():
            logging.info(f"Location settings found for shift")            

            loc_ids = []

            # find loc settings for tomorrow
            if actual_date == self.tomorrow_date:
                logging.info("Tomorrow date is fonded")
                tomorrow_loc = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                ).values_list("id", flat=True)

                if tomorrow_loc.exists() is False:
                    raise KioskScanError(f"Location settings not found for {actual_date}.")

                tomorrow_loc = tomorrow_loc.filter(system_location__status="active")
                if not tomorrow_loc.exists():
                    raise KioskScanError("Not found any active system locations.")

                loc_ids += tomorrow_loc.values_list("id", flat=True)

                logging.info(
                    f"=========== Location settings found on tomorrw day ==========="
                )

            print("Location settings :", loc_ids)
            logging.info(f" location settings ids : {loc_ids} ")

            valid_locations = location_settings.filter(id__in=loc_ids).order_by(
                "applicable_start_date", "start_time"
            )

            if valid_locations.exists() is False:
                logging.error(
                    " Matching location settings not found . In filtering maybe everything excluded."
                )
                raise KioskScanError("Location settings not found.")

            # Check all the locations
            system_location = geo_fencing_for_loc_settings(
                self.latitude,
                self.longitude,
                valid_locations,
            )

            logging.info(
                f" system_location found using Location Settings: {system_location} "
            )

        elif (self.org_enable_geo_fencing) and (shift.enable_geo_fencing):
            logging.info(f"=========== Geo fencing : True ===========")
            logging.info(
                f"=========== Log doesn't have location settings. Checking with shift default location ==========="
            )
            # check with default from  shift level
            default_location = shift.default_location

            if default_location is None:
                raise KioskScanError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive for tomorrow shift.")
                raise KioskScanError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )
        else:
            system_location = None

        return system_location



    def check_out_geo_fencing(self, log, actual_date):
        logging.info("======================Check out geo fencing======================")
        logging.info(f"actual_date: {actual_date}")

        shift = log.shift
        # loc_settings_restriction = shift.loc_settings_start_time_restriction

        logging.info(f"shift: {shift}")
        # logging.info(f"loc_settings_restriction: {loc_settings_restriction}")

        location_settings = log.location_settings.all().order_by("start_time")
        location_settings = location_settings.filter(system_location__status="active").filter(
            Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__gte=actual_date,
            )
            | Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__isnull=True,
            )
        )
        if location_settings.exists():

            loc_ids = []

            # find loc settings for tomorrow
            if actual_date == self.yesterday_date:
                yesterday_loc = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                ).values_list("id", flat=True)

                if yesterday_loc.exists() is False:
                    raise KioskScanError(f"Location settings not found {actual_date}.")

                # logging.info(f"loc_settings_restriction : {loc_settings_restriction}")

                yesterday_loc = yesterday_loc.filter(system_location__status="active")
                if not yesterday_loc.exists():
                    raise KioskScanError("Not found any active system locations.")

                # Check for night loc settings
                # if loc_settings_restriction is True:
                #     yesterday_loc = yesterday_loc.filter(
                #         start_time__gt=F("end_time"),
                #         end_time__gte=self.curr_time,
                #     )

                # if loc_settings_restriction and yesterday_loc.exists() is False:
                #     raise KioskScanError("Location settings start time exceeded.")

                loc_ids += yesterday_loc.values_list("id", flat=True)

                logging.info(
                    f"=========== Location settings found on previous day ==========="
                )

            # Check today location settings
            if actual_date == self.today_date:
                logging.info(
                    f"=========== Checking location settings today ==========="
                )

                today_loc_settings = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                )

                if today_loc_settings.exists() is False:
                    raise KioskScanError("No location settings found for today.")
                
                today_loc_settings = today_loc_settings.filter(system_location__status="active")
                if not today_loc_settings.exists():
                    raise KioskScanError("Not found any active system locations.")

                # if loc_settings_restriction is True:
                #     today_loc_settings = today_loc_settings.filter(
                #         start_time__gte=self.curr_time
                #     )

                # if loc_settings_restriction and today_loc_settings.exists() is False:
                #     raise KioskScanError("Location settings start time exceeded.")

                loc_ids += today_loc_settings.values_list("id", flat=True)

            print("Location settings :", loc_ids)
            logging.info(f" location settings ids : {loc_ids} ")

            valid_locations = location_settings.filter(id__in=loc_ids).order_by(
                "applicable_start_date", "start_time"
            )

            if valid_locations.exists() is False:
                logging.error(
                    " Matching location settings not found . In filrering maybe everything excluded."
                )
                raise KioskScanError("Location settings not found.")

            # Check all the locations
            system_location = geo_fencing_for_loc_settings(
                self.latitude,
                self.longitude,
                valid_locations,
            )

            logging.info(
                f" system_location found using Location Settings: {system_location} "
            )

        elif (self.org_enable_geo_fencing) and (shift.enable_geo_fencing):
            logging.info(f"=========== Geo fencing : True ===========")
            logging.info(
                f"=========== Log doesn't have location settings. Checking with shift default location ==========="
            )
            # check with defualt from  shift level
            default_location = shift.default_location

            logging.info(f"default_location: {default_location}")

            if default_location is None:
                raise KioskScanError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive.")
                raise KioskScanError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )

        else:
            system_location = None
        
        return system_location


    def find_member_from_fr_images(self, image: str) -> Member:
        """ Find member from all org member images.
            Get fr images from org and match with member images.
        """

        fr_images = MemberImage.objects.filter(organization=self.org)

        if fr_images.exists() is False:
            raise KioskScanError("No member images found in this organization.")

        known_face_encodings = face_rec.get_face_encodings(fr_images)

        known_face_ids = face_rec.get_user_ids(fr_images)

        logging.info(
            f"known_face_encodings = {len(known_face_encodings)}, known_face_ids = {len(known_face_ids)}"
        )

        image = utils.base64_to_contentfile(image)
        if isinstance(image, ContentFile) is False:
            logging.error("========= image type is not ContentFile =========")
            raise KioskScanError("Invalid image")

        face_encoding = face_rec.get_image_encoding(image)

        if not len(face_encoding):
            logging.error("========= face encoding have no lenght =========")
            raise KioskScanError("No face detected.")

        matches = face_recognition.compare_faces(
            known_face_encodings, face_encoding, tolerance=0.35
        )

        face_distances = face_recognition.face_distance(
            known_face_encodings, face_encoding
        )

        logging.info(f"Matches: {matches}")
        logging.info(f"Distances: {face_distances}")

        try:
            best_match_index = np.argmin(face_distances)
        except ValueError as err:
            logging.error(err)
            raise KioskScanError(
                "Your images for Face Recognition are not available. Please upload them on Web UI."
            )
        except Exception as err:
            logging.error(err)
            logging.critical(f"Add exception for {err.__class__.__name__} in ")
            raise KioskScanError("No Match Found.")

        logging.info(f"Best match index : {best_match_index}")

        if bool(matches[best_match_index]) is False:
            raise KioskScanError("No Match Found.")

        user_id = known_face_ids[best_match_index]
        logging.info(f"User ID : {known_face_ids}")

        try:
            member = Member.objects.get(user__id=user_id, organization=self.org)
        except Member.DoesNotExist:
            raise KioskScanError("Member not Found.")

        logging.info(f"Member : {member}")
        return member



    def find_member_from_all_fr_images(self, image: str) -> Member:
        """ Find member from all org member images.
            Get fr images from org and match with member images.
        """
        logging.info(
            "find_member_from_all_fr_images Started working"
        )

        fr_images = MemberImage.objects.filter(member__status="active").select_related("member")

        if fr_images.exists() is False:
            raise KioskScanError("Your images for Face Recognition are not available. Please upload them on Web UI.")

        known_face_encodings = face_rec.get_face_encodings(fr_images)

        known_face_ids = face_rec.get_member_ids(fr_images)

        logging.info(
            f"known_face_encodings = {len(known_face_encodings)}, known_face_member_ids = {len(known_face_ids)}"
        )

        image = utils.base64_to_contentfile(image)
        if isinstance(image, ContentFile) is False:
            logging.error("========= image type is not ContentFile =========")
            raise KioskScanError("Invalid image")

        face_encoding = face_rec.get_image_encoding(image)

        if not len(face_encoding):
            logging.error("========= face encoding have no length =========")
            raise KioskScanError("No face detected.")

        matches = face_recognition.compare_faces(
            known_face_encodings, face_encoding, tolerance=0.35
        )
        logging.info(f"Matches: {matches}")

        all_matched_user_ids = set()
        for index, match in enumerate(matches):
            logging.info(f"type of match before: {type(match)}")
            match = bool(match)
            logging.info(f"type of match after: {type(match)}")
            logging.info(f"match: {match}")
            if match is False:
                continue

            logging.info(f"member id: {known_face_ids[index]}")
            all_matched_user_ids.add(known_face_ids[index])

        len_all_match_user = len(all_matched_user_ids)
        logging.info(f"len_all_match_user: {len_all_match_user}")
        logging.info(f"all_matched_user_ids: {all_matched_user_ids}")

        if  len_all_match_user == 0:
            raise KioskScanError("Face does't match. Error KS2001.")
        if len_all_match_user >= 2:
            raise KioskScanError("Unable to complete identification. Error KS2002.")

        member_id = all_matched_user_ids.pop()
        logging.info(f"member id get using pop: {member_id}")

        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            raise KioskScanError("Member not Found.")

        logging.info(f"member: {member}")
        logging.info(
            "Got member from find_member_from_all_fr_images function"
        )

        return member

        # face_distances = face_recognition.face_distance(
        #     known_face_encodings, face_encoding
        # )

        # logging.info(f"Distances: {face_distances}")

        # try:
        #     best_match_index = np.argmin(face_distances)
        # except ValueError as err:
        #     logging.error(err)
        #     raise KioskScanError(
        #         "Your images for Face Recognition are not available. Please upload them on Web UI."
        #     )
        # except Exception as err:
        #     logging.error(err)
        #     logging.critical(f"Add exception for {err.__class__.__name__} in ")
        #     raise KioskScanError("No Match Found.")

        # logging.info(f"Best match index : {best_match_index}")

        # if bool(matches[best_match_index]) is False:
        #     raise KioskScanError("No Match Found.")

        # user_id = known_face_ids[best_match_index]
        # logging.info(f"User ID : {known_face_ids}")

        # try:
        #     member = Member.objects.get(user__id=user_id, organization=self.org)
        # except Member.DoesNotExist:
        #     raise KioskScanError("Member not Found.")

        # logging.info(f"Member : {member}")
        # return member


    def get_ssl_for_day_before_yesterday(self, date):
        logs = ShiftScheduleLog.objects.filter(
            status="active", employee=self.member, organization=self.org
        )

        try:
            yesterday_log = logs.get(
                Q(
                    start_date__lte=date,
                    end_date__gte=date,
                )
                | Q(start_date__lte=date, end_date__isnull=True)
            )
        except ShiftScheduleLog.DoesNotExist:
            yesterday_log = None
        return yesterday_log
        
    def post(self, request, *args, **kwargs):
        logging.info("------------------ Kiosk scan ------------------")

        image = request.data.get("image")
        if image is None:
            return HTTP_400({}, {"message": "Image is required."})

        try:
            kiosk = Kiosk.objects.get(uuid=kwargs["uuid"])
        except Kiosk.DoesNotExist:
            return read_data.get_404_response("Kiosk")

        if kiosk.status is False:
            return HTTP_400({}, {"message": "Kiosk is inactive."})

        self.org = kiosk.organization

        # Get time according to org tz
        self.date_time = curr_date_time_with_tz(self.org.timezone)
        self.curr_date = self.date_time.date()
        self.curr_time = self.date_time.time()
        self.today_date = self.curr_date
        self.tomorrow_date = self.curr_date + timedelta(days=1)
        self.yesterday_date = self.curr_date - timedelta(days=1)
        # self.req_user = request.user
        self.org_timezone = zoneinfo.ZoneInfo(self.org.timezone if self.org.timezone else "UTC")

        logging.info(f"Kiosk : {kiosk.kiosk_name}")
        logging.info(f"Org tz : {self.org.timezone}")
        logging.info(f"Curr date org : {self.date_time}")

        # Is user is authorized to access. dit is used for authenticated because users are not logged in.
        try:
            autenticated_dit(dit=request.data.get("dit"), kiosk=kiosk, curr_dt=self.date_time)
        except exceptions.DitAuthError as err:
            logging.error(f" authentication error : {err.message}")
            return read_data.get_403_response(err.message)

        logging.info(f"Kiosk authentication success")

        logging.info(f"Face rec started")


        if scan_fr_in_instance is False:
            logging.info(f"Scan only FR inside the org")
            # Find member
            try:
                member = self.find_member_from_fr_images(image)
            except KioskScanError as err:
                return HTTP_400({}, {"message": err.message})
        else:
            logging.info(f"Scan FR inside in whole instance")
            # Find member
            try:
                member = self.find_member_from_all_fr_images(image)
            except KioskScanError as err:
                return HTTP_400({}, {"message": err.message})

            if not member:
                return HTTP_400({}, {"message": "member not found."})

            self.org = member.organization

            # Get time according to org tz
            self.date_time = curr_date_time_with_tz(self.org.timezone)
            self.curr_date = self.date_time.date()
            self.curr_time = self.date_time.time()
            self.today_date = self.curr_date
            self.tomorrow_date = self.curr_date + timedelta(days=1)
            self.yesterday_date = self.curr_date - timedelta(days=1)
            # self.req_user = request.user
            self.org_timezone = zoneinfo.ZoneInfo(self.org.timezone if self.org.timezone else "UTC")

        image = utils.base64_to_contentfile(image)
        logging.info(f"Member : {member}")

        self.member = member
        self.req_user = member.user
        self.image = image

        if utils.is_member_inactive(member):
            return HTTP_400({} , {"message": "Member is Inactive."})

        # latitude = request.data.get("latitude")
        # longitude = request.data.get("longitude")

        latitude = kiosk.installed_latitude
        longitude = kiosk.installed_longitude

        print("============================================")
        print(f"latitude: {latitude}")
        print(f"longitude: {longitude}")
        print("============================================")

        if not latitude or not longitude:
            return HTTP_400({} , {"message": "Kiosk Installed Location is Unknown, can't create Scan."})

        self.latitude = latitude
        self.longitude = longitude

        # org settings of shift
        shift_management_settings = member.organization.shift_management_settings
        org_enable_geo_fencing = shift_management_settings["enable_geo_fencing"]
        self.org_enable_geo_fencing = org_enable_geo_fencing

        member_scans = MemberScan.objects.filter(
            member=member, status="pending", is_computed=False
        ).order_by("-date_time")

        if is_last_scan_before_5min(member_scans, self.date_time) is True:
            return HTTP_400(
                {},
                {
                    "message": "Your scan was saved recently, please wait for 5 mins before creating another scan."
                },
            )

        try:
            yesterday_log, today_log, tomorrow_log = self.get_ssl(member, self.org)
        except KioskScanError as err:
            logging.error(f"Getting Log : {err}")
            return HTTP_400({}, {"message": err.message})

        logging.info(f"yesterday_log: {yesterday_log}")
        logging.info(f"today_log: {today_log}")
        logging.info(f"tomorrow_log: {tomorrow_log}")

        if not tomorrow_log:
            logging.error("+++++++++++++++++++++++++++++++ Error : Tomorrow Log not found +++++++++++++++++++++++++++++++")
            return HTTP_400({}, {"message": "Shift not found."})

        logging.info(f"================== Finding Log ==================")
        logging.info(f"yesterday_log : {yesterday_log}")
        logging.info(f"today_log : {today_log}")
        logging.info(f"tomorrow_log : {tomorrow_log}")
        logging.info(f"================== Finding Log Ended ==================")
        logging.info(f"")


        last_scan = member_scans.first()
        if last_scan:
            logging.info(
                f"last_scan_type ==: {last_scan.scan_type}, last scan dt : {last_scan.date_time}"
            )

        if last_scan is None:
            scan_type = "check_in"
        elif last_scan.scan_type == "check_out":
            scan_type = "check_in"
        elif last_scan.scan_type == "check_in":

            last_scan_dt = last_scan.date_time

            last_computed_dt = self.find_last_computation_dt(
                yesterday_log, today_log, tomorrow_log
            )

            logging.info(f"Last Scan dt with org tz --: {last_scan_dt}")
            logging.info(f"last_computed_dt ==: {last_computed_dt}")

            if not last_computed_dt:
                # There is not shift found in the past. Today shift starting
                scan_type = self.curr_scan_type.get(last_scan.scan_type, "check_in")
            else:
                logging.info(
                    f"Is Last scan before computation time : {last_scan.date_time <= last_computed_dt}"
                )
                if last_scan_dt <= last_computed_dt:
                    scan_type = "check_in"
                else:
                    scan_type = self.curr_scan_type.get(last_scan.scan_type, "check_in")

        # Check out
        if scan_type == "check_out":
            scan_type = "check_out"

            logging.info("")
            logging.info(f"=========== Check out Started ===========")
            logging.info("")
            member_scan = member_scans.first()
            employee_log = None
            actual_data_of_scan = None
            system_location = None
            is_for_tomorrow = False

            # logging.info(f"{yesterday_log}==yesterday_log")
            # logging.info(f"yesterday_log.shift.start_time: {yesterday_log.shift.start_time}",)
            # logging.info(f"yesterday_log.shift.computation_time: {yesterday_log.shift.computation_time}")

            if (
                (yesterday_log is not None)
                and (
                    yesterday_log.shift.start_time
                    > yesterday_log.shift.computation_time
                )
                and (self.curr_time >= self.day_start_time)
                and (self.curr_time <= yesterday_log.shift.computation_time)
            ):
                logging.info(
                    "=============== Yesterday log is not ended. yesterday night shift founded =============="
                )
                employee_log = yesterday_log
                actual_data_of_scan = self.yesterday_date


            elif (today_log) and (today_log.shift.start_time >= today_log.shift.computation_time
                or today_log.shift.start_time <= today_log.shift.computation_time
                and self.curr_time <= today_log.shift.computation_time
            ):  # Computation time cannot be passed
                logging.info("=========== Today log =============")
                employee_log = today_log
                actual_data_of_scan = self.today_date

            else:  # today log Computation time is passed
                logging.info("========= tomorrow log =========")
                employee_log = tomorrow_log
                actual_data_of_scan = self.tomorrow_date
                is_for_tomorrow = True

            logging.info(f"=========== {employee_log} =============")

            shift = employee_log.shift
            logging.info(f"SHIFT : {shift.name}")

            try:
                if is_for_tomorrow is False:
                    system_location = self.check_out_geo_fencing(employee_log, actual_data_of_scan)
                else:
                    system_location = self.geo_fencing_tomorrow_check_in(employee_log, actual_data_of_scan)
            except KioskScanError as err:
                logging.error(f"=========== {err.message} ===========")
                return HTTP_400({}, {"message": err.message})
            except ValidationError as err:
                logging.error(f"=========== {err.message} ===========")
                return HTTP_400({}, {"message": err.message})
            except Exception as err:
                logging.error(f"Error {err.__class__.__name__}: {err}")
                logging.error(
                    f"Failed to scan for"
                    f"{request.user.username}  shift : {shift.name}"
                )
                return HTTP_400({}, {"message": "Unknown error occurred."})



            # if org_enable_geo_fencing is True and shift.enable_geo_fencing is True:
            #     logging.info("")
            #     logging.info(
            #         "Checkout Started geo fencing is True"
            #     )
            #     logging.info("")

            #     # For checkout geofencing only prev scan
            #     prev_scan_system_loc = member_scan.system_location

            #     # TODO confirm
            #     if prev_scan_system_loc is None:
            #         logging.error("========== Previous scan doesn't have any system location cannot do geo fencing ============")
            #         return HTTP_400({}, {"message": "System Location used for check in is not found."})

            #     if read_data.is_inactive_system_location(prev_scan_system_loc):
            #         logging.error("Prev system location is inactive for tomorrow shift.")
            #         return HTTP_400({}, {"message": "System Location is inactive."})

            #     try:
            #         system_location = geo_fencing(
            #             latitude, longitude, prev_scan_system_loc
            #         )
            #     except KioskScanError as err:
            #         logging.error(f"=========== {err.message} ===========")
            #         return HTTP_400({}, {"message": err.message})
            #     except ValidationError as err:
            #         logging.error(f"=========== {err.message} ===========")
            #         return HTTP_400({}, {"message": err.message})
            #     except Exception as err:
            #         logging.error(f"Error {err.__class__.__name__}: {err}")
            #         logging.error(
            #             f"Failed to scan for"
            #             f"{request.user.username}  shift : {shift.name}"
            #         )
            #         return HTTP_400({}, {"message": "Unknown error occurred."})
            # else:
            #     system_location = None
            #     logging.info("============= No geo fencing ==============")

        else:
            logging.info("")
            logging.info(f"=========== Check In Started ===========")
            scan_type = "check_in"

            # Check yesteray is a night shift and computation time is passed
            if (
                (yesterday_log is not None)
                and (
                    yesterday_log.shift.start_time
                    > yesterday_log.shift.computation_time
                )
                and (self.curr_time >= self.day_start_time)
                and (self.curr_time <= yesterday_log.shift.computation_time)
            ):
                logging.info(
                    "=============== Yesterday log is not ended. yesterday night shift founded =============="
                )
                try:
                    system_location = self.validate_check_in(
                        yesterday_log, self.yesterday_date
                    )
                except KioskScanError as err:
                    return HTTP_400({}, {"message": err.message})
                except ValidationError as err:
                    logging.error(f"=========== {err.message} ===========")
                    return HTTP_400({}, {"message": err.message})

            elif (today_log) and (today_log.shift.start_time >= today_log.shift.computation_time
                or today_log.shift.start_time <= today_log.shift.computation_time
                and self.curr_time <= today_log.shift.computation_time
            ):  # Computation time cannot be passed
                logging.info("=========== Today log =============")
                try:
                    system_location = self.validate_check_in(
                        today_log, self.today_date
                    )
                except KioskScanError as err:
                    return HTTP_400({}, {"message": err.message})
                except ValidationError as err:
                    logging.error(f"=========== {err.message} ===========")
                    return HTTP_400({}, {"message": err.message})


            else:  # if today log Computation time is passed user can check in for tomorrow shift
                logging.info("=========== Tomorrow log =============")
                try:
                    system_location = self.validate_tomorrow_check_in(
                        tomorrow_log, self.tomorrow_date
                    )
                except KioskScanError as err:
                    return HTTP_400({}, {"message": err.message})
                except ValidationError as err:
                    logging.error(f"=========== {err.message} ===========")
                    return HTTP_400({}, {"message": err.message})

        member_scan = MemberScan.objects.create(
            member=member,
            system_location=system_location,
            date_time=self.date_time,
            image=image,
            latitude=latitude,
            longitude=longitude,
            kiosk=kiosk,
            organization=self.org,
            scan_type=scan_type
        )
        logging.info(f"=========== Completed ===========")

        serializer =  MemberScanSerializer(member_scan)
        return HTTP_200(serializer.data)

    def get_ssl(self, member: Member, org: Organization) -> ShiftScheduleLog:
        """Retrive member yesterday, today, tomorrow  Shift Schedule Log"""

        logs = ShiftScheduleLog.objects.filter(
            status="active", employee=member, organization=org
        )

        logging.info(f"yesterday_date : {self.yesterday_date}")
        logging.info(f"curr_date : {self.curr_date}")
        logging.info(f"tomorrow_date : {self.tomorrow_date}")

        try:
            yesterday_log = logs.get(
                Q(
                    start_date__lte=self.yesterday_date,
                    end_date__gte=self.yesterday_date,
                )
                | Q(start_date__lte=self.yesterday_date, end_date__isnull=True)
            )
        except ShiftScheduleLog.DoesNotExist:
            yesterday_log = None

        try:
            today_log = logs.get(
                Q(
                    start_date__lte=self.curr_date,
                    end_date__gte=self.curr_date,
                )
                | Q(start_date__lte=self.curr_date, end_date__isnull=True),
            )
        except ShiftScheduleLog.DoesNotExist:
            today_log = None
            # raise KioskScanError("Shift not found.")

        try:
            tomorrow_log = logs.get(
                Q(
                    start_date__lte=self.tomorrow_date,
                    end_date__gte=self.tomorrow_date,
                )
                | Q(start_date__lte=self.tomorrow_date, end_date__isnull=True),
            )
        except ShiftScheduleLog.DoesNotExist:
            tomorrow_log = None

        return yesterday_log, today_log, tomorrow_log

    def validate_check_in(self, log, actual_date) -> SystemLocation:
        """
        Check restrictions. Validate yesterday and today log
        """

        logging.info("@@@@@@@@@@@@@"*5)

        logging.info(f"logs : {log}")
        logging.info(f"actual date : {actual_date}")

        start_time_restrictions_err = KioskScanError("Exceeded the shift start time.")

        shift = log.shift
        shift_start_time_restriction = shift.shift_start_time_restriction
        computation_time = shift.computation_time
        loc_settings_restriction = shift.loc_settings_start_time_restriction

        if shift_start_time_restriction and  shift.start_time < computation_time and self.curr_time > shift.start_time:
            raise start_time_restrictions_err

        logging.info(f"shift_start_time_restriction : {shift_start_time_restriction} ")
        # check shift start time exceeded
        if shift_start_time_restriction:
            logging.info(f"shift_start_time_restriction : {shift_start_time_restriction} ")

            if shift.start_time > computation_time:  # Night shift
                if (
                    self.curr_time > shift.start_time
                    and self.curr_time <= self.day_end_time
                ) or (
                    self.curr_time >= self.day_start_time
                    and self.curr_time <= computation_time
                ):
                    raise start_time_restrictions_err

            if (
                shift.start_time <= computation_time
                and self.curr_time > shift.start_time
            ):  # Normal shift
                raise start_time_restrictions_err

        location_settings = log.location_settings.all().order_by("start_time")
        location_settings = location_settings.filter(system_location__status="active").filter(
            Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__gte=actual_date,
            )
            | Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__isnull=True,
            )
        )

        logging.info(f" Location_settings exists : {location_settings.exists()} ")

        # Geo fencing will auto enable if loc settings is exists
        if location_settings.exists():

            loc_ids = []

            # find loc settings for tomorrow
            if actual_date == self.yesterday_date:
                yesterday_loc = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                ).values_list("id", flat=True)

                if yesterday_loc.exists() is False:
                    raise KioskScanError(f"Location settings not found {actual_date}.")

                logging.info(f"loc_settings_restriction : {loc_settings_restriction}")

                yesterday_loc = yesterday_loc.filter(system_location__status="active")
                if not yesterday_loc.exists():
                    raise KioskScanError("Not found any active system locations.")

                # Check for night loc settings
                if loc_settings_restriction is True:
                    yesterday_loc = yesterday_loc.filter(
                        start_time__gt=F("end_time"),
                        end_time__gte=self.curr_time,
                    )

                if loc_settings_restriction and yesterday_loc.exists() is False:
                    raise KioskScanError("Location settings start time exceeded.")

                loc_ids += yesterday_loc.values_list("id", flat=True)

                logging.info(
                    f"=========== Location settings found on previous day ==========="
                )

            # Check today location settings
            if actual_date == self.today_date:
                logging.info(
                    f"=========== Checking location settings today ==========="
                )

                today_loc_settings = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                )

                if today_loc_settings.exists() is False:
                    raise KioskScanError("No location settings found for today.")
                
                today_loc_settings = today_loc_settings.filter(system_location__status="active")
                if not today_loc_settings.exists():
                    raise KioskScanError("Not found any active system locations.")

                if loc_settings_restriction is True:
                    today_loc_settings = today_loc_settings.filter(
                        start_time__gte=self.curr_time
                    )

                if loc_settings_restriction and today_loc_settings.exists() is False:
                    raise KioskScanError("Location settings start time exceeded.")

                loc_ids += today_loc_settings.values_list("id", flat=True)

            print("Location settings :", loc_ids)
            logging.info(f" location settings ids : {loc_ids} ")

            valid_locations = location_settings.filter(id__in=loc_ids).order_by(
                "applicable_start_date", "start_time"
            )

            if valid_locations.exists() is False:
                logging.error(
                    " Matching location settings not found . In filrering maybe everything excluded."
                )
                raise KioskScanError("Location settings not found.")

            # Check all the locations
            system_location = geo_fencing_for_loc_settings(
                self.latitude,
                self.longitude,
                valid_locations,
            )

            logging.info(
                f" system_location found using Location Settings: {system_location} "
            )

        elif (self.org_enable_geo_fencing) and (shift.enable_geo_fencing):
            logging.info(f"=========== Geo fencing : True ===========")
            logging.info(
                f"=========== Log doesn't have location settings. Checking with shift default location ==========="
            )
            # check with defualt from  shift level
            default_location = shift.default_location

            if default_location is None:
                raise KioskScanError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive.")
                raise KioskScanError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )

        else:
            system_location = None

        return system_location

    def validate_tomorrow_check_in(self, log, actual_date) ->  SystemLocation:
        """
        Check restrictions
        """
        logging.info("--------------- Tomorrow log is finded")
        shift = log.shift
        location_settings = log.location_settings.all().order_by("start_time")
        location_settings = location_settings.filter(system_location__status="active").filter(
            Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__gte=actual_date,
            )
            | Q(
                applicable_start_date__lte=actual_date,
                applicable_end_date__isnull=True,
            )
        )

        logging.info(f"shift : {shift}")
        logging.info(f"log : {log}")
        logging.info(f"actual date : {actual_date}")

        # Geo fencing will auto enable if loc settings is exists
        if location_settings.exists():
            logging.info(f"Location settings found for shift")            

            loc_ids = []

            # find loc settings for tomorrow
            if actual_date == self.tomorrow_date:
                logging.info("Tomorrow date is fonded")
                tomorrow_loc = location_settings.filter(
                    Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__gte=actual_date,
                    )
                    | Q(
                        applicable_start_date__lte=actual_date,
                        applicable_end_date__isnull=True,
                    )
                ).values_list("id", flat=True)

                if tomorrow_loc.exists() is False:
                    raise KioskScanError(f"Location settings not found for {actual_date}.")

                tomorrow_loc = tomorrow_loc.filter(system_location__status="active")
                if not tomorrow_loc.exists():
                    raise KioskScanError("Not found any active system locations.")

                loc_ids += tomorrow_loc.values_list("id", flat=True)

                logging.info(
                    f"=========== Location settings found on tomorrw day ==========="
                )

            print("Location settings :", loc_ids)
            logging.info(f" location settings ids : {loc_ids} ")

            valid_locations = location_settings.filter(id__in=loc_ids).order_by(
                "applicable_start_date", "start_time"
            )

            if valid_locations.exists() is False:
                logging.error(
                    " Matching location settings not found . In filtering maybe everything excluded."
                )
                raise KioskScanError("Location settings not found.")

            # Check all the locations
            system_location = geo_fencing_for_loc_settings(
                self.latitude,
                self.longitude,
                valid_locations,
            )

            logging.info(
                f" system_location found using Location Settings: {system_location} "
            )

        elif (self.org_enable_geo_fencing) and (shift.enable_geo_fencing):
            logging.info(f"=========== Geo fencing : True ===========")
            logging.info(
                f"=========== Log doesn't have location settings. Checking with shift default location ==========="
            )
            # check with default from  shift level
            default_location = shift.default_location

            if default_location is None:
                raise KioskScanError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive for tomorrow shift.")
                raise KioskScanError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )
        else:
            system_location = None

        return system_location

    def find_last_computation_dt(self, yesterday_log, today_log, tomorrow_log):
        """Check the last computation date using log"""

        logging.info(
            "================================== find_last_computation_dt started =================================="
        )
        date = None

        # If today shift computation time is passed this is valid.
        if today_log:
            shift = today_log.shift
            logging.info(f"today_log :  {today_log}")
            logging.info(f"yesterday_log :  {yesterday_log}")
            logging.info(f"shift :  {shift}")

            # Still no the computation happend
            if (
                yesterday_log
                and yesterday_log.shift.start_time
                > yesterday_log.shift.computation_time
                and self.curr_time >= self.day_start_time
                and self.curr_time <= yesterday_log.shift.computation_time
            ):
                logging.info("======= Yesterday log is not ended")
                pass
            # shift is ended. This is the last shift
            elif (
                shift.start_time <= shift.computation_time
                and self.curr_time > shift.computation_time
            ):
                logging.info("Shift is ended for today")
                date = self.today_date

                last_computation_dt = tz.make_aware(
                    tz.datetime.combine(date, shift.computation_time),
                    timezone=self.org_timezone,
                )
                logging.info(f"last_computation_dt : {last_computation_dt}")
                return last_computation_dt

        logging.info("In today log computation not found. Going for tomorrow")

        if yesterday_log:
            shift = yesterday_log.shift

            logging.info(f"yesterday_log : {yesterday_log}")
            logging.info(f"shift : {shift}")

            if shift.start_time <= shift.computation_time:
                logging.info("shift start time is withing the day only")
                # shift is ended. This is the last shift
                date = self.yesterday_date
                logging.info(f"date : {date}")
            elif shift.start_time > shift.computation_time:

                date = (
                    self.today_date
                )  # If computation time is passed today is the current last comp day
                logging.info(f"date : {date}")

                # shift may not be ended
                if (
                    self.curr_time >= self.day_start_time
                    and self.curr_time <= shift.computation_time
                ):
                    # Yesterday shift computation is not runned. Day before yesterday is the last computed shift

                    logging.info(f"date : {date}")

                    day_before_yesterday_date = self.yesterday_date - timedelta(days=1)
                    day_before_yesterday_log = self.get_ssl_for_day_before_yesterday(
                        day_before_yesterday_date
                    )

                    if day_before_yesterday_log:
                        shift = day_before_yesterday_log.shift
                        if shift.start_time <= shift.computation_time:
                            date = day_before_yesterday_date
                        elif shift.start_time > shift.computation_time:
                            date = self.yesterday_date
                    else:
                        date = None

            if date:
                computation_time = shift.computation_time
                last_computation_dt = tz.make_aware(
                    tz.datetime.combine(date, computation_time),
                    timezone=self.org_timezone,
                )
                logging.info(
                    f"============== last_computation_dt : {last_computation_dt} =============="
                )
                return last_computation_dt

        logging.info(f"============== No conditions are met ==============")
