from urllib import response
from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from member.models import Member
# from roster.models import Roster
from roster import serializers
from roster.search import search_rosters
from roster.utils import get_location, get_shift, get_roster
from utils import read_data, fetch_data, create_data

import logging


logger = logging.getLogger(__name__)


class AllRostersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = serializers.RosterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        rosters = org.rosters.all()
        search_query = request.GET.get("search")
        rosters = search_rosters(rosters, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(rosters, per_page)
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
        member = fetch_data.get_member(request.user, org.uuid)

        # if fetch_data.is_admin(member) is False:
        #     return read_data.get_409_response()

        name = request.data.get("name")
        description = request.data.get("description")
        location_uuid = request.data.get("location_uuid")
        shift_uuid = request.data.get("shift_uuid")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        if location_uuid:
            location = get_location(org.uuid, location_uuid)
            if location is None:
                return read_data.get_404_response("Location")
        else:
            location = None

        shift = get_shift(org.uuid, shift_uuid)
        if shift is None:
            return read_data.get_404_response("Shift")

        if start_date:
            start_date = create_data.convert_string_to_datetime(start_date)
            start_date = start_date.date()
        if end_date:
            end_date = create_data.convert_string_to_datetime(end_date)
            end_date = end_date.date()

        member_uuids = request.data.get("member_uuids", [])
        try:
            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuids)
            )
        except (ValidationError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            roster = Roster.objects.create(
                organziation=org,
                name=name,
                description=description,
                location=location,
                shift=shift,
                start_date=start_date,
                end_date=end_date,
            )
        except IntegrityError as e:
            logger.error(e)
            return read_data.get_409_response("Roster", "name")

        # if not members.exists():
        #     return read_data.get_404_response("Member(s)")

        for member in members:
            member.rosters.add(roster)
            member.save()

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RosterAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = serializers.RosterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        # if fetch_data.is_admin(member) is False:
        #     return read_data.get_409_response()


        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        name = request.data.get("name", roster.name)
        description = request.data.get("description", roster.description)
        location_uuid = request.data.get("location_uuid")
        shift_uuid = request.data.get("shift_uuid")
        start_date = request.data.get("start_date", roster.start_date)
        end_date = request.data.get("end_date", roster.end_date)

        if location_uuid:
            location = get_location(org.uuid, location_uuid)
            if location is None:
                return read_data.get_404_response("Location")

        shift = get_shift(org.uuid, shift_uuid)
        if shift is None:
            return read_data.get_404_response("Shift")

        roster.name = name
        roster.description = description
        roster.start_date = create_data.convert_string_to_datetime(start_date)
        roster.end_date = create_data.convert_string_to_datetime(end_date)
        roster.location = location
        roster.shift = shift
        roster.save()

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        try:
            roster.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Roster is assigned to member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return read_data.get_200_delete_response("Roster")


class RosterMembersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = serializers.RosterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        member_uuids = request.data.getlist("member_uuids", [])
        try:
            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuids)
            )
        except (ValidationError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not members.exists():
            return read_data.get_404_response("Member(s)")

        for member in members:
            member.rosters.add(roster)
            member.save()

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        roster = get_roster(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        member_uuids = request.data.getlist("member_uuids", [])
        try:
            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuids)
            )
        except (ValidationError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not members.exists():
            return read_data.get_404_response("Member(s)")

        for member in members:
            member.rosters.remove(roster)
            member.save()

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RostersCalendarAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    # serializer_class = serializers.RosterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        lookup = (Q(start_date__gte=start_date) & Q(end_date__lte=end_date)) | (
            Q(start_date__isnull=True) | Q(end_date__isnull=True)
        )
        rosters = Roster.objects.filter(lookup)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(rosters, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
