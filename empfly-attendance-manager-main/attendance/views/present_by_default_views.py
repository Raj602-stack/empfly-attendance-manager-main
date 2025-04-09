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
from attendance.models import PresentByDefault
from attendance import serializers
from attendance.utils import get_present_by_default
from member.models import Member
from organization.serializers import OrganizationSerializer
from utils import read_data, fetch_data, create_data, email_funcs

import logging


logger = logging.getLogger(__name__)


class AllPresentByDefaultAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.PresentByDefaultSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        objects = PresentByDefault.objects.filter(Q(organization=org))

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(objects, per_page)
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

        name = request.data.get("name")
        description = request.data.get("description")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        reason = request.data.get("reason")

        if start_date:
            start_date = create_data.convert_string_to_datetime(start_date)
        if end_date:
            end_date = create_data.convert_string_to_datetime(end_date)

        present_by_default = PresentByDefault.objects.create(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )

        member_uuids = request.data.getlist("member_uuids", [])
        members = Member.objects.filter(Q(organization=org) & Q(uuid__in=member_uuids))
        for member in members:
            present_by_default.members.add(member)
        present_by_default.save()

        serializer = self.serializer_class(org)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PresentByDefaultAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.PresentByDefaultSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        present_by_default = get_present_by_default(org.uuid, uuid)
        if present_by_default is None:
            return read_data.get_404_response("PresentByDefault")

        serializer = self.serializer_class(present_by_default)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        present_by_default = get_present_by_default(org.uuid, uuid)
        if present_by_default is None:
            return read_data.get_404_response("PresentByDefault")

        name = request.data.get("name", present_by_default.name)
        description = request.data.get("description", present_by_default.description)
        start_date = request.data.get("start_date", present_by_default.start_date)
        end_date = request.data.get("end_date", present_by_default.end_date)
        reason = request.data.get("reason", present_by_default.reason)

        present_by_default.name = name
        present_by_default.description = description
        present_by_default.start_date = create_data.convert_string_to_datetime(
            start_date
        )
        present_by_default.end_date = create_data.convert_string_to_datetime(end_date)
        present_by_default.reason = reason
        try:
            present_by_default.save()
        except ValueError as e:
            logger.error(e)
            return Response(
                {"message": "Start date cannot be past end date or current date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(present_by_default)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        present_by_default = get_present_by_default(org.uuid, uuid)
        if present_by_default is None:
            return read_data.get_404_response("PresentByDefault")

        present_by_default.delete()

        return read_data.get_200_delete_response("PresentByDefault")


class PresentByDefaultMembersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.PresentByDefaultSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        roster = get_present_by_default(org.uuid, uuid)
        if roster is None:
            return read_data.get_404_response("PresentByDefault")

        serializer = self.serializer_class(roster)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        present_by_default = get_present_by_default(org.uuid, uuid)
        if present_by_default is None:
            return read_data.get_404_response("PresentByDefault")

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
            present_by_default.members.add(member)
        present_by_default.save()

        serializer = self.serializer_class(present_by_default)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_409_response()

        uuid = self.kwargs.get("uuid")
        present_by_default = get_present_by_default(org.uuid, uuid)
        if present_by_default is None:
            return read_data.get_404_response("PresentByDefault")

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
            present_by_default.members.remove(member)
        present_by_default.save()

        serializer = self.serializer_class(present_by_default)
        return Response(serializer.data, status=status.HTTP_200_OK)
