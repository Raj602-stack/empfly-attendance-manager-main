from urllib import request
from kiosk.serializers import KioskSerializer
from kiosk.utils import get_kiosk_object
from organization.models import OrgLocation
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.db.models import Q
from kiosk.models import Kiosk
import datetime as dt
from django.core.exceptions import ValidationError
from kiosk.search import search_kiosks
from django.db import IntegrityError
from django.db.utils import DataError, IntegrityError

from utils.read_data import encrypt_text
from utils import fetch_data, read_data
from utils.response import HTTP_200, HTTP_400

import logging

from utils.utils import convert_to_date, convert_to_time, filter_qs_by_is_active, filter_qs_by_status
logger = logging.getLogger(__name__)


class AllKioskAPI(views.APIView):
    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = KioskSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(requesting_member) is False:
            return read_data.get_403_response()

        search_query = request.GET.get("search")
        kiosks = search_kiosks(org.kiosks.all(), search_query)

        filtering_status = {
            "active": True,
            "inactive": False
        }

        kioks_status = request.GET.get("status", "active")
        kioks_status =  filtering_status.get(kioks_status)

        if isinstance(kioks_status, bool):
            kiosks = kiosks.filter(status=kioks_status)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(kiosks, per_page)
        page_obj = paginator.get_page(page)

        serializer = KioskSerializer(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
    )

    def post(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        kiosk_name = request.data.get("name")
        kiosk_status = request.data.get("status", True)
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        settings = request.data.get("settings")
        access_code = request.data.get("access_code")
        org_location = request.data.get("org_location")
        installed_latitude  = request.data.get("installed_latitude")
        installed_longitude = request.data.get("installed_longitude")

        if not kiosk_name:
            return HTTP_400({}, {"message": "Kiosk Name is required."})

        if not start_time:
            return HTTP_400({}, {"message": "Start time is required."})

        if not end_time:
            return HTTP_400({}, {"message": "End time is required."})

        if not access_code:
            return HTTP_400({}, {"message": "Access code is required."})

        if not installed_latitude:
            return HTTP_400({}, {"message": "Installed Latitude is required."})

        if not installed_longitude:
            return HTTP_400({}, {"message": "Installed Longitude is required."})

        start_time, is_valid = convert_to_time(start_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})

        end_time, is_valid = convert_to_time(end_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})

        if isinstance(kiosk_status, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if org_location:
            try:
                org_location = OrgLocation.objects.get(uuid=org_location, organization=org)
            except OrgLocation.DoesNotExist:
                return read_data.get_404_response("Org Location")

            if org_location.status == "inactive":
                return HTTP_400({} ,{"message": "Org location is inactive."})

        else:
            org_location = None

        try:
            kiosk_obj = Kiosk.objects.create(
                kiosk_name=kiosk_name,
                organization=org,
                start_time=start_time,
                end_time=end_time,
                status=kiosk_status,
                settings=settings,
                access_code=access_code,
                dit=None,
                dit_expiry=None,
                org_location=org_location,

                installed_latitude=installed_latitude,
                installed_longitude=installed_longitude
            )
        except IntegrityError:
            return Response(
                {"message": "Kiosk with name already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except DataError as err:
            print(err)
            return HTTP_400(
                {},
                {"message": "Ensure that there are no more than 2 digits before the decimal point for latitude/longitude"}
            )

        except Exception as err:
            logger.error(err)
            logger.exception(
                f"Add exception for {err.__class__.__name__} in KioskAPI"
            )
            return Response(
                {"message": "Unknown error occurred. Please try again."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = KioskSerializer(kiosk_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class KioskAPI(views.APIView):
    permission_classes = [permissions.IsTokenAuthenticated]


    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        kiosk = get_kiosk_object(org, self.kwargs.get("uuid"), org.kiosks.all())
        if kiosk is None:
            return read_data.get_404_response("Kiosk")

        return HTTP_200(KioskSerializer(kiosk).data)

    def put(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        kiosk_uuid = self.kwargs.get("uuid")
        try:
            kiosk_obj = org.kiosks.get(uuid=kiosk_uuid)
        except (Kiosk.DoesNotExist, ValidationError):
            return read_data.get_404_response("Kiosk")

        kiosk_name = request.data.get("name")
        kiosk_status = request.data.get("status", True)
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        settings = request.data.get("settings")
        access_code = request.data.get("access_code")
        org_location = request.data.get("org_location")
        installed_latitude  = request.data.get("installed_latitude")
        installed_longitude = request.data.get("installed_longitude")
    
        if not kiosk_name:
            return HTTP_400({}, {"message": "Kiosk Name is required."})

        if not start_time:
            return HTTP_400({}, {"message": "Start time is required."})

        if not end_time:
            return HTTP_400({}, {"message": "End time is required."})

        if not installed_latitude:
            return HTTP_400({}, {"message": "Installed Latitude is required."})

        if not installed_longitude:
            return HTTP_400({}, {"message": "Installed Longitude is required."})

        start_time, is_valid = convert_to_time(start_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})

        end_time, is_valid = convert_to_time(end_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})

        if isinstance(kiosk_status, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if org_location:
            try:
                org_location = OrgLocation.objects.get(uuid=org_location, organization=org)
            except OrgLocation.DoesNotExist:
                return read_data.get_404_response("Org Location")
        else:
            org_location = None

        if access_code:
            kiosk_obj.access_code = access_code

        if kiosk_obj.kiosk_name == "Mobile Kiosk":
            if kiosk_obj.kiosk_name != kiosk_name:
                return HTTP_400({}, {"message": "Cannot edit Mobile Kiosk name."})

            if kiosk_status is False:
                return HTTP_400({}, {"message": "Mobile Kiosk must be active."})

        kiosk_obj.kiosk_name=kiosk_name
        kiosk_obj.start_time=start_time
        kiosk_obj.end_time=end_time
        kiosk_obj.status=kiosk_status
        kiosk_obj.settings=settings
        kiosk_obj.org_location=org_location
        kiosk_obj.installed_latitude=installed_latitude
        kiosk_obj.installed_longitude=installed_longitude

        try:
            kiosk_obj.save()
        except IntegrityError:
            return Response(
                {"message": "Kiosk with name already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except DataError as err:
            print(err)
            return HTTP_400(
                {},
                {"message": "Ensure that there are no more than 2 digits before the decimal point for latitude/longitude"}
            )

        except Exception as err:
            logger.error(err)
            logger.exception(
                f"Add exception for {err.__class__.__name__} in KioskAPI"
            )
            return Response(
                {"message": "Unknown error occurred. Please try again."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = KioskSerializer(kiosk_obj)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        kiosk_uuid = self.kwargs.get("uuid")
        try:
            kiosk = org.kiosks.get(uuid=kiosk_uuid)
        except (Kiosk.DoesNotExist, ValidationError):
            return read_data.get_404_response("Kiosk")

        org_mobile_kiosk = "Mobile Kiosk"
        if kiosk.kiosk_name == org_mobile_kiosk:
            return HTTP_400({}, {"message": "Mobile kiosk cannot delete."})

        kiosk.delete()

        return read_data.get_200_delete_response("Kiosk")


class ResetKioskAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = KioskSerializer

    def patch(self, request, *args, **kwargs):
        """ Reset current dit and expiry from kiosk model.
        """

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            kiosk = Kiosk.objects.get(uuid=kwargs["uuid"], organization=org)
        except Kiosk.DoesNotExist:
            read_data.get_404_response("Kiosk")

        kiosk.dit = None
        kiosk.dit_expiry = None
        kiosk.save()

        serializer = self.serializer_class( kiosk )
        return HTTP_200(serializer.data)
