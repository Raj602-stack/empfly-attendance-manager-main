import logging

from datetime import datetime, date, timedelta
from typing import Tuple
import pytz
from os import system
from time import time
from tracemalloc import start
from django.db import IntegrityError
from account.models import User
from django.utils import timezone as tz
from attendance.attendance_utils import (
    check_geo_fencing,
    face_rec,
    geo_fencing,
    geo_fencing_for_loc_settings,
    # shift_logic,
)
from attendance.filters import filter_member_scan
from attendance.search import search_member_scan
from attendance.utils import is_last_scan_before_5min
from export.utils import create_export_request
from kiosk.models import Kiosk
from member.models import Member, MemberImage
from organization.models import Organization, SystemLocation
from organization.views import system_location
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
import face_recognition
import numpy as np
from shift.models import LocationSettings, Shift, ShiftScheduleLog
from geopy.distance import geodesic
from django.db.models import Case, When
from django.db import transaction

from utils.response import HTTP_200, HTTP_400

from api import permissions
from attendance.models import MemberScan, Attendance
from attendance import serializers
from roster.utils import get_roster
from utils import read_data, fetch_data, create_data, email_funcs


from utils.face_rec import get_face_encodings, get_image_encoding, get_user_ids
from utils.utils import base64_to_contentfile, convert_to_time, pagination
import zoneinfo


# configure logging
logging.basicConfig(
    filename="logs/scan_view.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)


# class MemberScansAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = serializers.MemberScanSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         requesting_member = fetch_data.get_member(request.user, org.uuid)

#         uuid = self.kwargs.get("uuid")
#         member = fetch_data.get_member_by_uuid(org.uuid, uuid)
#         if member is None:
#             return read_data.get_404_response("Member")

#         member_scans = member.scans.all()
#         per_page = request.GET.get("per_page", 10)
#         page = request.GET.get("page", 1)
#         paginator = Paginator(member_scans, per_page)
#         page_obj = paginator.get_page(page)

#         serializer = self.serializer_class(page_obj.object_list, many=True)
#         return Response(
#             {
#                 "data": serializer.data,
#                 "pagination": {"total_pages": paginator.num_pages, "page": page},
#             },
#             status=status.HTTP_200_OK,
#         )


class CheckInOrCheckoutAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberScanSerializer

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
    org: Organization
    org_enable_face_recognition: bool
    org_enable_geo_fencing: bool
    org_timezone: zoneinfo.ZoneInfo

    temp_date_time = datetime.strptime("05/10/09 00:00:00", "%d/%m/%y %H:%M:%S")
    day_start_time = temp_date_time.time()
    day_end_time = (temp_date_time - timedelta(microseconds=1)).time()

    curr_scan_type = {
        "check_in": "check_out",
        "check_out": "check_in",
    }


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
                    raise ValidationError(f"Location settings not found {actual_date}.")

                # logging.info(f"loc_settings_restriction : {loc_settings_restriction}")

                yesterday_loc = yesterday_loc.filter(system_location__status="active")
                if not yesterday_loc.exists():
                    raise ValidationError("Not found any active system locations.")

                # Check for night loc settings
                # if loc_settings_restriction is True:
                #     yesterday_loc = yesterday_loc.filter(
                #         start_time__gt=F("end_time"),
                #         end_time__gte=self.curr_time,
                #     )

                # if loc_settings_restriction and yesterday_loc.exists() is False:
                #     raise ValidationError("Location settings start time exceeded.")

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
                    raise ValidationError("No location settings found for today.")
                
                today_loc_settings = today_loc_settings.filter(system_location__status="active")
                if not today_loc_settings.exists():
                    raise ValidationError("Not found any active system locations.")

                # if loc_settings_restriction is True:
                #     today_loc_settings = today_loc_settings.filter(
                #         start_time__gte=self.curr_time
                #     )

                # if loc_settings_restriction and today_loc_settings.exists() is False:
                #     raise ValidationError("Location settings start time exceeded.")

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
                raise ValidationError("Location settings not found.")

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
                raise ValidationError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive.")
                raise ValidationError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )

        else:
            system_location = None
        
        return system_location

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
                    raise ValidationError(f"Location settings not found for {actual_date}.")

                tomorrow_loc = tomorrow_loc.filter(system_location__status="active")
                if not tomorrow_loc.exists():
                    raise ValidationError("Not found any active system locations.")

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
                raise ValidationError("Location settings not found.")

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
                raise ValidationError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive for tomorrow shift.")
                raise ValidationError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )
        else:
            system_location = None

        return system_location

    def post(self, request, *args, **kwargs):
        logging.info(
            ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> Req started <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
        )

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        print(request.user)
        logging.info("")
        logging.info("")
        logging.info(" ################### " * 5)
        logging.info(f"Requesting user : {request.user.username}")

        timezone = pytz.timezone(org.timezone)
        logging.info(f"Org Timezone : {timezone}")

        date_and_time = datetime.now(tz=timezone)
        self.date_time = date_and_time
        self.curr_date = date_and_time.date()
        self.today_date = self.curr_date
        self.curr_time = date_and_time.time()
        self.yesterday_date = self.curr_date - timedelta(days=1)
        self.tomorrow_date = self.curr_date + timedelta(days=1)
        self.req_user = request.user
        self.member = member
        self.org = org
        self.org_timezone = zoneinfo.ZoneInfo(org.timezone if org.timezone else "UTC")

        logging.info(f"Date time : {date_and_time}")

        try:
            mobile_kiosk = member.authorized_kiosks.get(kiosk_name="Mobile Kiosk")
        except Kiosk.DoesNotExist:
            return read_data.get_403_response(
                "User does not have access to mobile app."
            )

        shift_management_settings = member.organization.shift_management_settings
        org_enable_geo_fencing = shift_management_settings["enable_geo_fencing"]
        org_enable_face_recognition = shift_management_settings[
            "enable_face_recognition"
        ]

        self.org_enable_face_recognition = org_enable_face_recognition
        self.org_enable_geo_fencing = org_enable_geo_fencing

        member_scans = MemberScan.objects.filter(
            member=member, is_computed=False, status="pending"
        ).order_by("-date_time")

        if is_last_scan_before_5min(member_scans, self.date_time) is True:
            return HTTP_400(
                {},
                {
                    "message": "Your scan was saved recently, please wait for 5 mins before creating another scan."
                },
            )

        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        image = request.data.get("image")

        self.latitude = latitude
        self.longitude = longitude
        self.image = image

        logging.info(f"lati and long : {latitude}, {longitude}")
        logging.info("")

        logging.info(f"================== Finding Log ==================")
        yesterday_log, today_log, tomorrow_log = self.get_ssl(member, org)
        logging.info(f"yesterday_log : {yesterday_log}")
        logging.info(f"today_log : {today_log}")
        logging.info(f"tomorrow_log : {tomorrow_log}")
        logging.info(f"================== Finding Log Ended ==================")
        logging.info(f"")

        if not tomorrow_log:
            logging.error("+++++++++++++++++++++++++++++++ Error : Tomorrow Log not found +++++++++++++++++++++++++++++++")
            return HTTP_400({}, {"message": "Shift not found."})

        last_scan = member_scans.first()
        if last_scan:
            logging.info(
                f"last_scan_type ==: {last_scan.scan_type}, last scan dt : {last_scan.date_time}"
            )


        # Find out Current scan is for check in check out
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

        logging.info(f"scan_type ==: {scan_type}")
        # Check Out
        if scan_type == "check_out":
            scan_type = "check_out"

            logging.info("")
            logging.info(f"=========== Check out ===========")
            logging.info("")
            member_scan = member_scans.first()

            employee_log = None

            actual_data_of_scan = None
            system_location = None
            is_for_tomorrow = False

            if (
                (yesterday_log is not None)
                and (
                    yesterday_log.shift.start_time
                    > yesterday_log.shift.computation_time
                )
                and (self.curr_time >= self.day_start_time)
                and (self.curr_time <= yesterday_log.shift.computation_time)
            ):
                # Yesterday was night shift. Computation time still not passed.
                logging.info(
                    "=============== Yesterday log is not ended. yesterday night shift founded =============="
                )
                employee_log = yesterday_log
                actual_data_of_scan = self.yesterday_date

            elif (today_log) and (today_log.shift.start_time >= today_log.shift.computation_time
                or today_log.shift.start_time <= today_log.shift.computation_time
                and self.curr_time <= today_log.shift.computation_time
            ):
                # Yesterday shift not valid. Current time match with today shift.
                logging.info("=========== Today log =============")
                employee_log = today_log
                actual_data_of_scan = self.today_date

            else:
                # today log Computation time is passed or not found. User can start check in for tomorrow shift.
                logging.info("========= tomorrow log =========")
                employee_log = tomorrow_log
                actual_data_of_scan = self.tomorrow_date
                is_for_tomorrow = True

            logging.info(f"=========== {employee_log} =============")

            shift = employee_log.shift
            logging.info(f"SHIFT : {shift.name}")

            # face rec
            if (
                org_enable_face_recognition is True
                and shift.enable_face_recognition is True
            ):
                logging.info("")
                logging.info("Check out started face rec")
                logging.info("")

                try:
                    user, image = face_rec(member, image, self.req_user)
                except ValidationError as err:
                    logging.error(f"ERROR : {err.message}")
                    return HTTP_400({}, {"message": err.message})
                except Exception as err:
                    logging.error(f"Error {err.__class__.__name__}: {err}")
                    logging.error(
                        f"Failed to scan for"
                        f"{request.user.username}  shift : {shift.name}"
                    )
                    return HTTP_400({}, {"message": "Unknown error occurred."})
            else:
                image = None
                logging.info("Check out face rec not done")

            try:
                if is_for_tomorrow is False:
                    system_location = self.check_out_geo_fencing(employee_log, actual_data_of_scan)
                else:
                    system_location = self.geo_fencing_tomorrow_check_in(employee_log, actual_data_of_scan)
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
            #     logging.info("Checkout Started geo fencing is True")
            #     logging.info("")

            #     # For checkout geo fencing only prev scan
            #     prev_scan_system_loc = member_scan.system_location

            #     if prev_scan_system_loc is None:
            #         # The time of checkout prev system location use for geo fencing.
            #         # While doing the prev scan the geo fencing was false. But now its true.
            #         # in this case Without system location not possible to check out.

            #         logging.error(
            #             "========== Previous scan doesn't have any system location cannot do geo fencing ============"
            #         )
            #         return HTTP_400({}, {"message": "System Location used for check in is not found."})

            #     if read_data.is_inactive_system_location(prev_scan_system_loc):
            #         # Inactive system location cannot use for check in or check out.
            #         logging.error("prev system location is inactive now.")
            #         return HTTP_400({}, {"message": "System Location is inactive."})

            #     try:
            #         system_location = geo_fencing(
            #             latitude, longitude, prev_scan_system_loc
            #         )
            #     except ValidationError as err:
            #         logging.error(f"=========== {err.message} ===========")
            #         return HTTP_400({}, {"message": err.message})
            #     except Exception as err:
            #         logging.error(f"Error {err.__class__.__name__}: {err}")
            #         logging.error(
            #             f"Failed to scan for"
            #             f"{request.user.username}  shift : {shift.name}"
            #         )
            #         return HTTP_400({}, {"message": "Unknown error occured."})
            # else:
            #     system_location = None
            #     logging.info("============= No geo fencing ==============")

            RESPONSE = HTTP_200({"message": "Check out successfully."})

        else:
            #  Check in
            logging.info("")
            logging.info(f"=========== Check In Started ===========")
            scan_type = "check_in"
    
            # Find out user shift.
            if (
                (yesterday_log is not None)
                and (
                    yesterday_log.shift.start_time
                    > yesterday_log.shift.computation_time
                )
                and (self.curr_time >= self.day_start_time)
                and (self.curr_time <= yesterday_log.shift.computation_time)
            ):
                # Check yesterday is a night shift and computation time is passed
                logging.info(
                    "=============== Yesterday log is not ended. yesterday night shift founded =============="
                )
                try:
                    image, system_location = self.validate_check_in(
                        yesterday_log, self.yesterday_date
                    )
                except ValidationError as err:
                    return HTTP_400({}, {"message": err.message})

            elif (today_log) and (today_log.shift.start_time >= today_log.shift.computation_time
                or today_log.shift.start_time <= today_log.shift.computation_time
                and self.curr_time <= today_log.shift.computation_time
            ):
                logging.info("Today log ***************************************************")
                # Computation time cannot be passed
                logging.info("=========== Today log =============")
                try:
                    image, system_location = self.validate_check_in(
                        today_log, self.today_date
                    )
                except ValidationError as err:
                    return HTTP_400({}, {"message": err.message})

            else:  # if today log Computation time is passed user can check in for tomorrow shift
                logging.info("=========== Tomorrow log =============")
                try:
                    image, system_location = self.validate_tomorrow_check_in(
                        tomorrow_log, self.tomorrow_date
                    )
                except ValidationError as err:
                    return HTTP_400({}, {"message": err.message})

            RESPONSE = HTTP_200({"message": "Check in successfully."})

        member_scan = MemberScan.objects.create(
            member=member,
            system_location=system_location,
            date_time=self.date_time,
            image=image,
            latitude=latitude,
            longitude=longitude,
            kiosk=mobile_kiosk,
            organization=org,
            scan_type=scan_type,
        )
        logging.info(f"####################### Completed #######################")
        return RESPONSE

    def get_ssl_for_day_before_yesterday(self, date):
        """Get ssl of the date."""
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

    def find_last_computation_dt(self, yesterday_log, today_log, tomorrow_log):
        """Check the last computation date using log"""

        logging.info(
            "================================== find_last_computation_dt started =================================="
        )
        date = None

        # If today shift computation time is passed last computed dt is is today only.
        if today_log:
            shift = today_log.shift
            logging.info(f"today_log :  {today_log}")
            logging.info(f"yesterday_log :  {yesterday_log}")
            logging.info(f"shift :  {shift}")

            # Yesterday shift computation time still not completed.
            if (
                yesterday_log
                and yesterday_log.shift.start_time
                > yesterday_log.shift.computation_time
                and self.curr_time >= self.day_start_time
                and self.curr_time <= yesterday_log.shift.computation_time
            ):
                logging.info("======= Yesterday log is not ended")
                pass

            # Today shift completed. Today is the last computation dt.
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

        logging.info("Going for yesterday")

        if yesterday_log:
            shift = yesterday_log.shift

            logging.info(f"yesterday_log : {yesterday_log}")
            logging.info(f"shift : {shift}")

            if shift.start_time <= shift.computation_time:
                logging.info("shift start time is withing the day only")
                # Yesterday is a day shift. Yesterday last computation is runs.
                date = self.yesterday_date
                logging.info(f"date : {date}")
            elif shift.start_time > shift.computation_time:
                # yesterday was night shift

                date = (
                    self.today_date
                )  # If computation time is passed today is the current last comp day
                logging.info(f"date : {date}")

                # shift may not be ended
                if (
                    self.curr_time >= self.day_start_time
                    and self.curr_time <= shift.computation_time
                ):
                    # Yesterday shift computation is not runs. Day before yesterday is the last computed shift

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

            # Combine start date and time.
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

    def get_ssl(self, member: Member, org: Organization) -> ShiftScheduleLog:
        """Retrive member yesterday, today, tomorrow  Shift Schedule Log"""

        logs = ShiftScheduleLog.objects.filter(
            status="active", employee=member, organization=org
        )

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

    def validate_check_in(self, log, actual_date):
        """ Check restrictions. Validate yesterday and today log. Check geo fencing and face rec.
        """

        logging.info("@@@@@@@@@@@@@" * 5)

        logging.info(f"logs : {log}")
        logging.info(f"actual date : {actual_date}")

        start_time_restrictions_err = ValidationError("Exceeded the shift start time.")

        shift = log.shift
        shift_start_time_restriction = shift.shift_start_time_restriction
        computation_time = shift.computation_time
        loc_settings_restriction = shift.loc_settings_start_time_restriction

        # if shift.start_time < computation_time and self.curr_time > shift.start_time:
        #     """
        #     Raise Error
        #     """

        logging.info(f" shift_start_time_restriction : {shift_start_time_restriction} ")

        if shift_start_time_restriction:
            # If shift_start_time_restriction is True user can't check after shift start time.

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

        # Location settings of the check in day.
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

        logging.info(f" is location_settings exists : {location_settings.exists()} ")

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
                    raise ValidationError(f"Location settings not found {actual_date}.")

                yesterday_loc = yesterday_loc.filter(system_location__status="active")
                if not yesterday_loc.exists():
                    raise ValidationError("Not found any active system locations.")

                # Check for night loc settings
                if loc_settings_restriction is True:
                    yesterday_loc = yesterday_loc.filter(
                        start_time__gt=F("end_time"),
                        end_time__gte=self.curr_time,
                    )

                if loc_settings_restriction and yesterday_loc.exists() is False:
                    raise ValidationError("Location settings start time exceeded.")

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
                    raise ValidationError("No location settings found for today.")

                today_loc_settings = today_loc_settings.filter(
                    system_location__status="active"
                )
                if not today_loc_settings.exists():
                    raise ValidationError("Not found any active system locations.")

                if loc_settings_restriction is True:
                    today_loc_settings = today_loc_settings.filter(
                        start_time__gte=self.curr_time
                    )

                if loc_settings_restriction and today_loc_settings.exists() is False:
                    raise ValidationError("Location settings start time exceeded.")

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
                raise ValidationError("Location settings not found.")

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
                raise ValidationError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error("Default shift system location is inactive.")
                raise ValidationError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )

        else:
            system_location = None

        if (
            self.org_enable_face_recognition is True
            and shift.enable_face_recognition is True
        ):
            user, image = face_rec(self.member, self.image, self.req_user)
            logging.info(f"=========== Face Matched ===========")
        else:
            logging.info(f"=========== Face rec is Off ===========")
            image = None

        return image, system_location

    def validate_tomorrow_check_in(self, log, actual_date):
        """ No restrictions. Already before the time of check in. Face rec and geo fencing will considered.
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
                logging.info("Tomorrow date is finded")
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
                    raise ValidationError(f"Location settings not found {actual_date}.")

                tomorrow_loc = tomorrow_loc.filter(system_location__status="active")
                if not tomorrow_loc.exists():
                    raise ValidationError("Not found any active system locations.")

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
                raise ValidationError("Location settings not found.")

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
            # check with default from  shift level. If location settings is not configured.
            default_location = shift.default_location

            if default_location is None:
                raise ValidationError("System Location not found for shift.")

            if read_data.is_inactive_system_location(default_location):
                logging.error(
                    "Default shift system location is inactive for tomorrow shift."
                )
                raise ValidationError("System Location is inactive.")

            system_location = geo_fencing(
                self.latitude, self.longitude, default_location
            )

            logging.info(
                f"=========== system_location found from shift: {system_location} ==========="
            )
        else:
            system_location = None

        if (
            self.org_enable_face_recognition is True
            and shift.enable_face_recognition is True
        ):
            user, image = face_rec(self.member, self.image, self.req_user)
            logging.info(f"=========== Face Matched ===========")
        else:
            logging.info(f"=========== Face rec is Off ===========")
            image = None

        return image, system_location

    def covert_dt_to_org_tz(self, date, time):
        return  tz.make_aware(
            tz.datetime.combine(date, time), timezone=self.org_timezone
        )


class IsCheckInAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = VisitorSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        # created_at = date.today()

        scan_count = MemberScan.objects.filter(member=member, is_computed=False).count()

        return HTTP_200({"is_checkin": scan_count % 2 == 1})


class AllMemberScansAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberScanSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        member_scans = MemberScan.objects.filter(organization=org)

        filter_status = request.GET.get("status", "active")
        if filter_status in ("active", "inactive"):
            member_scans = member_scans.filter(member__status=filter_status)

        if member.role.name not in ("admin", "hr"):

            org_location_obj = member.org_location_head.all()
            department_obj = member.department_head.all()
            employees = member.members.all()

            if org_location_obj.exists() or department_obj.exists() or employees.exists():
                member_scans = member_scans.filter(
                    Q(member__org_location__in=org_location_obj) | Q(member__department__in=department_obj) | Q(member__manager=member)
                )
            else:
                # Only see his data
                member_scans = member_scans.filter(member=member)

        member_scans = filter_member_scan(member_scans, request)

        search_query = request.GET.get("search")
        member_scans = search_member_scan(member_scans, search_query)

        if bool(request.GET.get("export_csv")) is True:
            if not member_scans.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            departments_ids = member_scans.values_list("id", flat=True)
            export_request = create_export_request(
                member, "attendance_register", list(departments_ids)
            )
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(member_scans, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        temperature_integration = org.settings.get("temperature_integration", False)

        return Response(
            {
                "data": serializer.data,
                "temperature_integration": temperature_integration,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class MyMemberScansAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberScanSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        member_scans = MemberScan.objects.filter(organization=org, member=member)

        member_scans = filter_member_scan(member_scans, request)

        search_query = request.GET.get("search")
        member_scans = search_member_scan(member_scans, search_query)

        page_obj, num_pages, page = pagination(member_scans, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        temperature_integration = org.settings.get("temperature_integration", False)

        return Response(
            {
                "data": serializer.data,
                "temperature_integration": temperature_integration,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
