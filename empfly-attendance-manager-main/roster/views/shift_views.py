from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse

from api import permissions
from roster.models import Roster
# TODO Shift
# from roster.models import Shift, Roster
from roster import serializers, search
from roster.utils import get_shift
from shift.models import Shift
from utils import read_data, fetch_data, create_data, email_funcs

import csv
import pandas as pd
import datetime as dt
import logging


logger = logging.getLogger(__name__)


class AllShiftsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = serializers.ShiftSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role.name not in ("admin", "hr"):
            return read_data.get_403_response()

        shifts = org.shifts.all()
        search_query = request.GET.get("search")
        shifts = search.search_shifts(shifts, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(shifts, per_page)
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

        if requesting_member.role.name not in ("admin", "hr"):
            return read_data.get_403_response()


        name = request.data.get("name")
        description = request.data.get("description")
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        computation_time = request.data.get("computation_time")
        duration = request.data.get("duration")
        overtime = request.data.get("overtime")
        settings = request.data.get("settings")

        start_time = dt.datetime.strptime(start_time, "%H:%M")
        end_time = dt.datetime.strptime(end_time, "%H:%M")
        computation_time = dt.datetime.strptime(computation_time, "%H:%M")

        if duration is None:
            # start_time = start_time.replace(tzinfo=None)
            # start_time = start_time.replace(tzinfo=None)
            duration = end_time - start_time
        else:
            duration = dt.datetime.strptime(duration, "%H:%M").time()
            duration = dt.timedelta(hours=duration.hour, minutes=duration.minute)

        if overtime:
            overtime = dt.datetime.strptime(overtime, "%H:%M").time()
            overtime = dt.timedelta(hours=overtime.hour, minutes=overtime.minute)

        start_time = start_time.time()
        end_time = end_time.time()
        computation_time = computation_time.time()

        try:
            shift = {}
            # TODO Shift

            # shift = Shift.objects.create(
            #     organization=org,
            #     name=name,
            #     description=description,
            #     start_time=start_time,
            #     end_time=end_time,
            #     computation_time=computation_time,
            #     duration=duration,
            #     overtime=overtime,
            #     settings=settings,
            # )
        except IntegrityError as e:
            return Response(
                {"message": "Shift with name already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(shift)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShiftAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = serializers.ShiftSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role.name not in ("admin", "hr"):
            return read_data.get_403_response()

        shift_uuid = self.kwargs.get("uuid")
        shift = get_shift(shift_uuid)
        if shift is None:
            return read_data.get_404_response("Shift")

        serializer = self.serializer_class(shift)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role.name not in ("admin", "hr"):
            return read_data.get_403_response()

        shift_uuid = self.kwargs.get("uuid")
        try:
            shift = org.shifts.get(uuid=shift_uuid)
        except (Shift.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Shift")

        name = request.data.get("name", shift.name)
        description = request.data.get("description", shift.description)

        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        computation_time = request.data.get("computation_time")
        duration = request.data.get("duration")
        settings = request.data.get("settings")

        start_time = dt.datetime.strptime(start_time, "%H:%M")
        end_time = dt.datetime.strptime(end_time, "%H:%M")
        computation_time = dt.datetime.strptime(computation_time, "%H:%M")

        is_active = request.data.get("is_active", shift.is_active)
        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if duration is None:
            # start_time = start_time.replace(tzinfo=None)
            # start_time = start_time.replace(tzinfo=None)
            duration = end_time - start_time
        else:
            duration = dt.datetime.strptime(duration, "%H:%M").time()
            duration = dt.timedelta(hours=duration.hour, minutes=duration.minute)

        start_time = start_time.time()
        end_time = end_time.time()
        computation_time = computation_time.time()

        shift.name = name
        shift.description = description
        shift.start_time = start_time
        shift.end_time = end_time
        shift.duration = duration
        shift.is_active = is_active
        shift.settings = settings
        try:
            shift.save()
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Shift with name already exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.serializer_class(shift)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role.name not in ("admin", "hr"):
            return read_data.get_403_response()

        shift_uuid = self.kwargs.get("uuid")
        try:
            shift = org.shifts.get(uuid=shift_uuid)
        except (Shift.DoesNotExist, ValidationError) as e:
            return read_data.get_404_response("Shift")

        shift.delete()

        return Response(
            {"message": "Successfully deleted Shift"},
            status=status.HTTP_200_OK,
        )


class ShiftsUploadCSVAPI(views.APIView):

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

        df = read_data.read_csv(csv_file)
        if df is None:
            return Response(
                {"message": "Failed to load CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        added_objects_count = 0
        failed_pbjects = []

        for row in df.values:
            try:
                name = row[0]
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in ShiftsUploadCSVAPI"
                )
                failed_pbjects.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                continue

            try:
                Shift.objects.create(
                    organization=org,
                    name=name,
                    description=row[1],
                    start_time=row[2],
                    end_time=row[3],
                    duration=row[4],
                    computation_time=row[5],
                    overtime=row[6],
                )
                added_objects_count += 1
            except IntegrityError as e:
                logger.error(e)
                detailed_reason = "Shift with name already exists"
                failed_pbjects.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": detailed_reason,
                    }
                )
            except Exception as e:
                failed_pbjects.append(
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
                "added_objects_count": added_objects_count,
                "failed_pbjects": failed_pbjects,
            },
            status=status.HTTP_201_CREATED,
        )
