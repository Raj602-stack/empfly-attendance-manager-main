from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import IntegrityError

from api import permissions
from roster.models import Location
# TODO Shift
# from roster.models import Location, Shift, Roster
from roster import serializers, search
from roster.utils import get_location
from utils import read_data, fetch_data, create_data, email_funcs

import csv
import pandas as pd
import logging


logger = logging.getLogger(__name__)


class AllLocationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LocationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        locations = org.locations.all()
        search_query = request.GET.get("search")
        locations = search.search_locations(locations, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(locations, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

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


        name = request.data.get("name")
        description = request.data.get("description")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        radius = request.data.get("radius", 50)
        email = str(request.data.get("email", "")).lower()
        phone = request.data.get("phone")

        try:
            location = Location.objects.create(
                organization=org,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                email=email,
                phone=phone,
            )
        except IntegrityError as e:
            logger.error(e)
            if "location_radius_range" in str(e):
                message = "Radius has to be between 0.0-5000.0"
            else:
                message = "Location with name already exists"
            return Response(
                {"message": message},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.serializer_class(location)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LocationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        location_uuid = self.kwargs.get("uuid")
        location = get_location(location_uuid)
        if location is None:
            return read_data.get_404_response("Location")

        serializer = self.serializer_class(location)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()


        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.locations.get(uuid=location_uuid)
        except (Location.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Location")

        name = request.data.get("name", location.name)
        description = request.data.get("description", location.description)
        latitude = request.data.get("latitude", location.latitude)
        longitude = request.data.get("longitude", location.longitude)
        radius = request.data.get("radius", location.radius)
        email = request.data.get("email", location.email)
        phone = request.data.get("phone", location.phone)

        if isinstance(email, str):
            email = email.lower().strip()

        location.name = name
        location.description = description
        location.latitude = latitude
        location.longitude = longitude
        location.radius = radius
        location.email = email
        location.phone = phone

        try:
            location.save()
        except IntegrityError as e:
            logger.error(e)
            if "location_radius_range" in str(e):
                message = "Radius has to be between 0.0-5000.0"
            else:
                message = "Location with name already exists"
            return Response(
                {"message": message},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.serializer_class(location)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()


        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.locations.get(uuid=location_uuid)
        except (Location.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Location")

        location.delete()

        return Response(
            {"message": "Successfully deleted Location"},
            status=status.HTTP_200_OK,
        )


class LocationsUploadCSVAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.LocationSerializer

    def get(self, request, *args, **kwargs):

        response = HttpResponse(content_type="text/csv")
        response[
            "Content-Disposition"
        ] = 'attachment; filename="sample_locations_file.csv"'

        writer = csv.writer(response)
        writer.writerow(["name", "description", "latitude", "longitude", "radius"])
        writer.writerow(
            [
                "Indiranagar",
                "Indiranagar description",
                12.97837181055267,
                77.63963223890426,
                200,
            ]
        )
        writer.writerow(["MG Road", "", 12.97546852742838, 77.60664169046560, 200])
        writer.writerow(
            [
                "HSR Layout",
                "HSR Layout description",
                12.91224192821739,
                77.64436068922599,
                200,
            ]
        )

        return response

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org.uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        csv_file = request.data.get("csv_file")

        try:
            df = pd.read_csv(csv_file, encoding="ISO-8859-1")
            df = df.where(pd.notnull(df), None)
            # Replaces nan values with empty string
            df = df.fillna("")
        except UnicodeDecodeError as e:
            logger.error(e)
            return Response(
                {"message": "Failed to load CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__}"
                " in LocationsUploadCSVAPI > read_csv"
            )
            return Response(
                {"message": "Failed to load CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        added_locations_count = 0
        failed_locations = []

        for row in df.values:
            try:
                name = row[0]
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in LocationsUploadCSVAPI"
                )
                failed_locations.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                continue

            try:
                Location.objects.create(
                    organization=org,
                    name=name,
                    description=row[1],
                    latitude=row[2],
                    longitude=row[3],
                    radius=row[4],
                )
                added_locations_count += 1
            except IntegrityError as e:
                logger.error(e)
                if "location_radius_range" in str(e):
                    detailed_reason = "Radius has to be between 0.0-5000.0"
                else:
                    detailed_reason = "Location with name already exists"
                failed_locations.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": detailed_reason,
                    }
                )
            except Exception as e:
                failed_locations.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in LocationsUploadCSVAPI"
                )

        return Response(
            {
                "added_locations_count": added_locations_count,
                "failed_locations": failed_locations,
            },
            status=status.HTTP_201_CREATED,
        )
