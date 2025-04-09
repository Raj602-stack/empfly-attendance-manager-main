from export.utils import create_export_request
from organization.models import SystemLocation
# from organization.serializers import SystemLocaitonSerializer
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.paginator import Paginator
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from shift.models import Shift
from utils import read_data, fetch_data, create_data
from api import permissions
from  organization.search import search_system_locations
from utils.response import HTTP_400
from utils.utils import pagination
from utils.response import HTTP_200
from django.db.utils import DataError, IntegrityError
from export import utils as export_utils
import logging

logger = logging.getLogger(__name__)

# TODO REMOVE FROM HERE
class SystemLocaitonSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = SystemLocation
        exclude = ["id"]


class AllSystemLocationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = SystemLocaitonSerializer
    fields = ["name", "description", "latitude", "longitude", "radius", "organization"]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        system_locations = org.system_locations.all()
        search_query = request.GET.get("search")
        system_locations = search_system_locations(system_locations, search_query)

        system_loc_status = request.GET.get("status", "active")
        if system_loc_status in ("active", "inactive"):
            system_locations = system_locations.filter(status=system_loc_status)

        if bool(request.GET.get("export_csv")) is True:

            if not system_locations.exists():
                return HTTP_400({}, {"message": "No data found for export csv."})
            
            system_location_ids = export_utils.get_uuid_from_qs(system_locations)

            export_request = create_export_request(member, "system_locations", system_location_ids)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(system_locations, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        longitude = str(request.data.get("longitude", ""))
        latitude = str(request.data.get("latitude", ""))
        radius = request.data.get("radius", "50")
        description = request.data.get("description")
        sys_loc_status = request.data.get("status")

        if not name:
            return HTTP_400({}, {"message": "Name is required"})

        if not latitude or latitude.isdecimal():
            return HTTP_400({}, {"message": "Enter a valid latitude"})

        if not longitude or longitude.isdecimal():
            return HTTP_400({}, {"message": "Enter a valid longitude"})

        if not radius:
            return HTTP_400({}, {"message": "Enter a valid radius"})

        if sys_loc_status not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inactive."})

        try:
            system_location = SystemLocation.objects.create(
                name=name,
                radius=radius,
                latitude=latitude,
                longitude=longitude,
                description=description,
                organization=org,
                status=sys_loc_status
            )
        except IntegrityError as e:
            return HTTP_400({}, {"message": "System Location with name already exists"})
        except DataError as e :
            return HTTP_400({}, {"message": "Ensure that there are no more than 2 digits before the decimal point for latitude/longitude"})
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllSystemLocationsAPI"
            )
            return HTTP_400({}, {"message": "An error occurred. While creating a System location."})
        return HTTP_200(self.serializer_class(system_location).data)

class SystemLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = SystemLocaitonSerializer
    serializer_fields = ["name", "description", "latitude", "longitude", "radius", "organization"]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            system_locations = org.system_locations.get(uuid=kwargs["uuid"])
        except SystemLocation.DoesNotExist as e:
            return read_data.get_404_response("System Location")

        serializer = self.serializer_class(system_locations)

        return Response(
            {"data": serializer.data,},status=status.HTTP_200_OK,
        )


    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            system_location = org.system_locations.get(uuid=self.kwargs.get("uuid"))
        except (SystemLocation.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("System Location")

        name = request.data.get("name")
        longitude = str(request.data.get("longitude", ""))
        latitude = str(request.data.get("latitude", ""))
        radius = request.data.get("radius")
        radius = radius if radius else "50"
        description = request.data.get("description")
        sys_loc_status = request.data.get("status")

        if sys_loc_status not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inacitve."})

        if not name:
            return HTTP_400({}, {"message": "Name is required"})

        if not latitude or latitude.isdecimal():
            return HTTP_400({}, {"message": "Enter a valid latitude"})

        if not longitude or longitude.isdecimal():
            return HTTP_400({}, {"message": "Enter a valid longitude"})

        try:
            system_location.name = name
            system_location.radius = radius
            system_location.latitude = latitude
            system_location.longitude = longitude
            system_location.description = description
            system_location.status = sys_loc_status

            system_location.save()
        except IntegrityError as e:
            return HTTP_400({}, {"message": "System Location with name already exists"})
        except DataError as e :
            return HTTP_400({}, {"message": "Ensure that there are no more than 2 digits before the decimal point for longitude/logtitude"})
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllSystemLocationsAPI"
            )
            return HTTP_400({}, {"message": "An error occurred. While creating a System location."})
        return HTTP_200(self.serializer_class(system_location).data)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()


        try:
            system_locations = org.system_locations.get(uuid=self.kwargs.get("uuid"))
        except (SystemLocation.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("System Location")

        shift_with_system_location = Shift.objects.filter(default_location=system_locations, organization=org)
        if shift_with_system_location.exists():
            return HTTP_400(
                {},
                {
                    "message": "Cannot delete this system location. System location assigned as default location in shift."
                }
            )

        system_locations.delete()

        return Response(
            {"message": "Successfully deleted Organization Location"},
            status=status.HTTP_200_OK,
        )
