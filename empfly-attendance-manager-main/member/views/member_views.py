from datetime import date, datetime, timedelta
from django.db import IntegrityError
from export.utils import create_export_request
from member.filters import filter_members
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from kiosk.models import Kiosk
from api import permissions
from django.db.models.deletion import RestrictedError
import base64
from organization.models import Department, Designation, Organization, OrgLocation, Role
from organization.utils import get_cost_center, get_designation, get_member_role
from utils.shift import assign_applicable_shift
from utils.utils import base64_to_contentfile, filter_qs_by_status, is_allowed_to_add_members, send_limit_exceeded_notification
from account.models import User
from member.models import Member, MemberImage
from member import serializers, search
from attendance.models import MemberScan

# from roster.models import Shift
from shift.models import Shift, ShiftScheduleLog
from roster.utils import get_roster
from utils.response import HTTP_200, HTTP_400
from utils import read_data, fetch_data, create_data, email_funcs

import zoneinfo
from django.utils import timezone as tz
import pytz
from export import utils as export_utils

import logging

from visitor.models import Visitor


logger = logging.getLogger(__name__)

# configure logging
logging.basicConfig(
    filename="logs/scan_view.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)


class AllMembersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer
    # serializer_class = serializers.MinimalMemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        members = org.members.all()

        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)
        members = filter_members(members, request)
        members = filter_qs_by_status(request=request, qs=members, default="active", choice=("active", "inactive"))

        if bool(request.GET.get("export_csv")) is True:
            if not members.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            members_ids = export_utils.get_uuid_from_qs(members)
            export_request = create_export_request(member, "members", members_ids)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        fields = [
            "user",
            "photo",
            "organization",
            "role",
            "designation",
            "department",
            "cost_center",
            "rosters",
            "previous_roster",
        ]
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    # TODO Optimize this view
    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        if is_allowed_to_add_members(org) is False:
            send_limit_exceeded_notification(org, request.user)
            return Response(
                {"message": "Organization member limit reached. Please contact Empfly support."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "joining_date",
            "confirmation_date",
            "employee_id",
            "department",
            "designation",
            "org_location",
            "role",
            "manager",
            "authorized_kiosks",
            "allowed_to_meet",
            "photo",
            "status",
            "vehicle_number",
            "is_front_desk"
        ]

        field_with_value = {}

        for field in fields:
            value = request.data.get(field)
            if isinstance(value, str):
                field_with_value[field] = value.strip()
                continue
            field_with_value[field] = value

        member = Member.objects.filter(organization=org)
        validated_data = {}
        authorized_obj = []

        if field_with_value["joining_date"]:
            joining_date = create_data.convert_string_to_datetime(field_with_value["joining_date"])
            if joining_date is None:
                return HTTP_400({}, {"message": "Enter valid joining date (yyyy-mm-dd)"})
            validated_data["joining_date"] = joining_date

        # if isinstance(field_with_value["is_front_desk"], bool) is False:
        #     field_with_value["is_front_desk"] = False

        if isinstance(field_with_value["is_front_desk"], bool) is False:
            return HTTP_400({}, {"message": "Is front desk must be a True/False."})

        validated_data["is_front_desk"] = field_with_value["is_front_desk"]

        if field_with_value["confirmation_date"]:
            confirmation_date = create_data.convert_string_to_datetime(field_with_value["confirmation_date"])
            if confirmation_date is None:
                return HTTP_400({}, {"message": "Enter valid confirmation date (yyyy-mm-dd)"})
            validated_data["confirmation_date"] = confirmation_date

        if not field_with_value["email"] and not field_with_value["phone"]:
            return HTTP_400({}, {"message": "Enter email or phone number"})

        if not field_with_value["first_name"]:
            return HTTP_400({}, {"message": "First Name is required."})

        if field_with_value["employee_id"] or field_with_value["employee_id"] == 0:
            if member.filter(employee_id=field_with_value["employee_id"]).exists():
                return HTTP_400({}, {"message": "Employee id already exist"})
            validated_data["employee_id"] = field_with_value["employee_id"]

        if field_with_value["department"]:
            department_obj = Department.objects.filter(uuid=field_with_value["department"], organization=org)
            if not department_obj.exists():
                return HTTP_400({}, {"message": "Department not exists"})

            if department_obj.first().is_active is False:
                return HTTP_400({}, {"message": "Department is inactive."})

            validated_data["department"] = department_obj.first()

        if field_with_value["designation"]:
            designation_obj = Designation.objects.filter(uuid=field_with_value["designation"], organization=org)
            if not designation_obj.exists():
                return HTTP_400({}, {"message": "Designation not exists"})

            if designation_obj.first().is_active is False:
                return HTTP_400({}, {"message": "Designation is inactive."})

            validated_data["designation"] = designation_obj.first()

        if field_with_value["org_location"]:
            org_location_obj = OrgLocation.objects.filter(uuid=field_with_value["org_location"], organization=org)
            if not org_location_obj.exists():
                return HTTP_400({}, {"message": "Organization location not exists"})

            if org_location_obj.first().status == "inactive":
                return HTTP_400({}, {"message": "Org location is inactive."})

            validated_data["org_location"] = org_location_obj.first()

        if field_with_value["role"]:
            role_obj = Role.objects.filter(uuid=field_with_value["role"])
            if not role_obj.exists():
                return HTTP_400({}, {"message": "Role not exists"})

            if role_obj.first().name not in ("admin", "hr", "member"):
                return HTTP_400({}, {"message": "Role must be in Admin/Hr/Member."})

            validated_data["role"] = role_obj.first()
        else:
            validated_data["role"] = get_member_role()

        if validated_data["role"].name != "member" and validated_data["is_front_desk"] is True:
            return HTTP_400({}, {"message": "Only Member role users can be assigned Front Desk permissions."})

        if field_with_value["manager"]:
            manager_ins = member.filter(uuid=field_with_value["manager"])
            if not manager_ins.exists():
                return HTTP_400({}, {"message": "Manager not exists"})
            validated_data["manager"] = manager_ins.first()

        if field_with_value["status"] not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inactive"})
        validated_data["status"] = field_with_value["status"]

        kiosks_ids = []
        if field_with_value["authorized_kiosks"]:
            kiosk_uuids = field_with_value["authorized_kiosks"]
            all_kiosks = Kiosk.objects.filter(organization=org, uuid__in=kiosk_uuids, status=True)
            kiosks_ids = list(all_kiosks.values_list("id", flat=True))
            # kiosks_ids.append(*all_kiosks)

        if field_with_value["photo"]:
            content = base64_to_contentfile(field_with_value["photo"])
            if isinstance(content, ContentFile):
                validated_data["photo"] = content
            else:
                return content  # response

        if field_with_value["vehicle_number"]:
            validated_data["vehicle_number"] = field_with_value["vehicle_number"]

        if isinstance(field_with_value["allowed_to_meet"], bool) is False:
            field_with_value["allowed_to_meet"] = False

        validated_data["allowed_to_meet"] = field_with_value.get("allowed_to_meet")

        if field_with_value["email"]:
            lower_email = field_with_value["email"]
            field_with_value["email"] = lower_email.lower()

            is_users = User.objects.filter(email=field_with_value["email"])
            if is_users.exists() is True:
                created = False
                user = is_users.first()
            else:
                user = User.objects.create(
                    email=field_with_value["email"],
                    first_name=field_with_value["first_name"],
                )
                created = True

            if created:
                user.last_name = field_with_value["last_name"]
                if not User.objects.filter(phone=field_with_value["phone"]).exists():
                    user.phone = field_with_value["phone"]
                user.save()

                email_funcs.send_activation_mail(user)

        elif field_with_value["phone"]:
            is_users = User.objects.filter(phone=field_with_value["phone"])
            if is_users.exists() is True:
                created = False
                user = is_users.first()
            else:
                user = User.objects.create(
                    phone=field_with_value["phone"],
                    first_name=field_with_value["first_name"],
                )
                created = True

            if created:
                user.first_name = field_with_value["first_name"]
                user.last_name = field_with_value["last_name"]
                user.save()
                # TODO phone activation

        # Check user is visitor
        if Visitor.objects.filter(user=user, organization=org).exists():
            return HTTP_400({}, {"message": "User is already a visitor."})

        member = Member.objects.filter(Q(organization=org) & Q(user=user))
        if member.exists():
            return Response({"message": "Member already exists"}, status=status.HTTP_409_CONFLICT)

        validated_data["organization"] = org
        validated_data["user"] = user
        member = Member.objects.create(**validated_data)

        # Defualt mobile kiosk assign for every employee
        mobile_kiosk, _ = Kiosk.objects.get_or_create(kiosk_name="Mobile Kiosk", organization=org)

        kiosks_ids.append(mobile_kiosk.id)
        member.authorized_kiosks.add(*kiosks_ids)

        user.save()
        member.save()

        # Create shift schedule log for employee with org default shift
        create_data.initial_employee_log(member)

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MemberAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        print(requesting_member, "@@@@@@@@@@@"*5)
        print(fetch_data.is_admin_hr_member(requesting_member), "#############"*4)

        # if fetch_data.is_admin_hr_member(requesting_member) is False:
        #     return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        # print("========%%%%%%%%%%%%%%%"*10)
        # print(requesting_member.role.name not in ("admin",))
        # print(member.role.name in ("admin", "hr"))
        # print(requesting_member.role.name not in ("admin",) and member.role.name in ("admin", "hr"))
        # print("========%%%%%%%%%%%%%%%%"*10)

        # if requesting_member.role.name not in ("admin",) and member.role.name in ("admin", "hr"):
        #     return read_data.get_403_response()

        # if fetch_data.has_access(org.uuid, request.user, "member", member) is False:
        #     return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        print(requesting_member.role.name in ("hr", "member"))
        print(member.role.name in ("admin", "hr"))

        if requesting_member.role.name in ("hr", "member") and member.role.name in ("admin", "hr") :
            return read_data.get_403_response()

        # if fetch_data.has_access(org.uuid, request.user, "member", member) is False:
        #     return read_data.get_403_response()

        email = str(request.data.get("email", "")).strip()
        email = email.lower()
        first_name = str(request.data.get("first_name", "")).strip()
        last_name = str(request.data.get("last_name", "")).strip()
        phone = str(request.data.get("phone", "")).strip()
        joining_date = request.data.get("joining_date")
        confirmation_date = request.data.get("confirmation_date")
        employee_id = str(request.data.get("employee_id", "")).strip()
        department = request.data.get("department")
        designation = request.data.get("designation")
        org_location = request.data.get("org_location")
        role = request.data.get("role")
        manager = request.data.get("manager")
        allowed_to_meet = request.data.get("allowed_to_meet", False)
        photo = request.data.get("photo")
        member_status = request.data.get("status", None)
        vehicle_number = str(request.data.get("vehicle_number", "")).strip()
        authorized_kiosks = request.data.get("authorized_kiosks", [])
        is_front_desk = request.data.get("is_front_desk", False)

        if isinstance(is_front_desk, bool) is False:
            return HTTP_400({}, {"message": "Is front desk must be a True/False."})

        if not first_name:
            return HTTP_400({}, {"message": "First Name is required."})

        if not email and not phone:
            return HTTP_400({}, {"message": "Email/Phone number is required."})

        member.is_front_desk = is_front_desk
        if joining_date:
            joining_date = create_data.convert_string_to_datetime(joining_date)
            if joining_date is None:
                return HTTP_400({}, {"message": "Enter valid joining date (yyyy-mm-dd)"})
            member.joining_date = joining_date
        else:
            member.joining_date = None

        if confirmation_date:
            confirmation_date = create_data.convert_string_to_datetime(confirmation_date)
            if confirmation_date is None:
                return HTTP_400({}, {"message": "Enter valid confirmation date (yyyy-mm-dd)"})
            member.confirmation_date = confirmation_date
        else:
            member.confirmation_date = None

        if isinstance(allowed_to_meet, bool) is False:
            return Response(
                {"message": "allowed_to_meet must be a boolean value"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member.allowed_to_meet = allowed_to_meet

        if member_status not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inactive"})
        member.member_status = member_status

        all_users = User.objects.all()
        all_member = Member.objects.filter(organization=org)

        if email:
            if all_users.filter(email=email).exclude(id=member.user.id).exists():
                return HTTP_400({}, {"message": "User with this email already exists."})

        if phone:
            if all_users.filter(phone=phone).exclude(id=member.user.id).exists():
                return HTTP_400({}, {"message": "User with this phone number already exists."})

        if employee_id or employee_id == 0:
            qs = all_member.filter(employee_id=employee_id).exclude(id=member.id)
            if qs.exists():
                return HTTP_400({}, {"message": "Employee id already exists."})
            member.employee_id = employee_id
        else:
            member.employee_id = None

        if department:
            try:
                department_obj = Department.objects.get(uuid=department, organization=org)
            except Department.DoesNotExist:
                return HTTP_400({}, {"message": "Department not exists"})

            if department_obj != member.department and department_obj.is_active is False:
                return HTTP_400({}, {"message": "Department is inactive."})

            member.department = department_obj
        else:
            member.department = None

        if designation:
            try:
                designation_obj = Designation.objects.get(uuid=designation, organization=org)
            except Department.DoesNotExist:
                return HTTP_400({}, {"message": "Designation not exists"})

            if designation_obj != member.designation and designation_obj.is_active is False:
                return HTTP_400({}, {"message": "Designation is inactive."})

            member.designation = designation_obj
        else:
            member.designation = None

        if org_location:
            try:
                org_location_obj = OrgLocation.objects.get(uuid=org_location, organization=org)
            except OrgLocation.DoesNotExist:
                return HTTP_400({}, {"message": "Org Location not exists"})

            if org_location_obj != member.org_location and org_location_obj.status == "inactive":
                return HTTP_400({}, {"message": "Org Location is inactive."})

            member.org_location = org_location_obj
        else:
            member.org_location = None

        if role:
            try:
                role_obj = Role.objects.get(uuid=role)
                if role_obj.name not in ("admin", "hr", "member"):
                    return HTTP_400({}, {"message": "Role must be in Admin/Hr/Member."})
            except Role.DoesNotExist:
                return HTTP_400({}, {"message": "Role not exists"})
            member.role = role_obj

        if role_obj.name != "member" and is_front_desk is True:
            return HTTP_400({}, {"message": "Only Member role users can be assigned Front Desk permissions."})

        if manager and manager != member.uuid:
            try:
                manager_ins = all_member.get(uuid=manager)
            except Member.DoesNotExist:
                return HTTP_400({}, {"message": "Manager not exists"})
            member.manager = manager_ins
        else:
            member.manager = None

        if authorized_kiosks:
            member.authorized_kiosks.clear()
            all_kiosks = Kiosk.objects.filter(organization=org, uuid__in=authorized_kiosks)
            member.authorized_kiosks.add(*all_kiosks)
        else:
            member.authorized_kiosks.clear()

        if photo:
            content = base64_to_contentfile(photo)
            if isinstance(content, ContentFile):
                member.photo = content
            else:
                return content  # response

        if vehicle_number:
            member.vehicle_number = vehicle_number
        else:
            member.vehicle_number = None

        user = member.user
        if first_name:
            user.first_name = first_name
        user.last_name = last_name

        if email:
            user.email = email
            # TODO Send verification email
        if phone:
            user.phone = phone
            # TODO Send verification SMS

        member.joining_date = joining_date
        member.confirmation_date = confirmation_date

        try:
            member.user.save()
            member.save()
        except IntegrityError as e:
            logger.error(e)
            return Response(
                {"message": "Email/Phone already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member.role.name not in ("admin",) and member.role.name in ("admin", "hr"):
            return read_data.get_403_response()

        # if fetch_data.has_access(org.uuid, request.user, "member", member) is False:
        #     return read_data.get_403_response()

        try:
            member.delete()
        except RestrictedError as err:
            print(err)
            return HTTP_400({}, {"message": "Member is assigned as department head. Please assign any other member as department head and continue."})
        return Response({"message": "Successfully deleted member"}, status=status.HTTP_200_OK)


class MemberRoleAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)

        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member == member:
            return Response(
                {"message": "You cannot edit your own role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uuid = request.data.get("role_uuid")
        try:
            role = Role.objects.get(uuid=uuid)
        except (Role.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Role")

        member.role = role
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberManagerAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        manager_uuid = request.data.get("manager_uuid")
        manager = fetch_data.get_member_by_uuid(org.uuid, manager_uuid)
        if manager is None:
            return read_data.get_404_response("Manager")

        if member == manager:
            return Response(
                {"message": "A member cannot be assigned as manager to themselves."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.manager = manager
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberDesignationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member == member:
            return Response(
                {"message": "You cannot edit your own role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uuid = request.data.get("designation_uuid")
        designation = get_designation(uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        member.designation = designation
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberDepartmentAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member == member:
            return Response(
                {"message": "You cannot edit your own role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uuid = request.data.get("department_uuid")
        department = get_designation(uuid)
        if department is None:
            return read_data.get_404_response("Department")

        member.department = department
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberCostCenterAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org_uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.has_access(org_uuid, request.user, "member", member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ! Admin only
    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if requesting_member == member:
            return Response(
                {"message": "You cannot edit your own role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if member.department is None:
            return Response(
                {"message": "Cannot assign Cost Center without assigning a Department"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uuid = request.data.get("cost_center_uuid")
        cost_center = get_cost_center(uuid)
        if cost_center is None:
            return read_data.get_404_response("Cost Center")

        if member.department != cost_center.department:
            return Response(
                {"message": "Cannot assign Cost Center of another Department"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.cost_center = cost_center
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberRostesrAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        uuid = request.data.get("roster_uuid")
        roster = get_roster(uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        member.rosters.add(roster)
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        member_uuid = self.kwargs.get("uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        uuid = request.data.get("roster_uuid")
        roster = get_roster(uuid)
        if roster is None:
            return read_data.get_404_response("Roster")

        member.rosters.remove(roster)
        member.save()

        serializer = self.serializer_class(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberImagesAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        member_images = member.member_images.all()

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(member_images, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class HostAllowedToMeetAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def get(self, request, *args, **kwargs):
        """ Both member and visitor have access to this api.
        """

        org_uuid = request.headers.get("organization-uuid")
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            member = fetch_data.get_member(request.user, org.uuid)
            role = member.role.name
            requesting_user = member
        except Member.DoesNotExist:
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            visitor = fetch_data.get_visitor(request.user, org.uuid)
            role = visitor.role.name
            requesting_user = visitor

        # if role not in ("admin", "hr", "member", "visitor"):
        #     return read_data.get_403_response()
        if fetch_data.is_admin_hr_member_visitor(requesting_user) is False:
            return read_data.get_403_response()

        org_location = request.GET.get("org_location")
        print(org_location)
        if not org_location:
            return HTTP_400({}, {"message": "Organization location is required"})

        try:
            org_loc = OrgLocation.objects.get(uuid=org_location)

            if org_loc.status == "inactive":
                return HTTP_400({}, {"message": "Org Location is inactive."})
        except OrgLocation.DoesNotExist:
            return read_data.get_404_response("Org Location")

        try:
            members = Member.objects.filter(allowed_to_meet=True, org_location__uuid=org_location, status="active")
        except ValidationError:
            return HTTP_400({}, {"message": "Organization location is required"})

        serializer = self.serializer_class(members, many=True)
        return HTTP_200(serializer.data)


class CheckInStatusAPIView(views.APIView):

    # Assign permissions to the view
    permission_classes = [permissions.IsTokenAuthenticated]

    curr_scan_type = {
        "check_in": "check_out",
        "check_out": "check_in",
    }

    temp_date_time = datetime.strptime("05/10/09 00:00:00", "%d/%m/%y %H:%M:%S")
    day_start_time = temp_date_time.time()
    day_end_time = (temp_date_time - timedelta(microseconds=1)).time()

    req_user: User
    curr_time: datetime
    curr_date: datetime
    yesterday_date: datetime
    date_time: datetime
    tomorrow_date: datetime
    today_date: datetime
    member: Member
    org: Organization
    org_timezone: zoneinfo.ZoneInfo
    

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

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()        

        timezone = org.timezone
        date_and_time = datetime.now(tz=pytz.timezone(timezone))
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

        member_scans = MemberScan.objects.filter(
            member=member, is_computed=False, status="pending"
        ).order_by("-date_time")

        last_scan = member_scans.first()
        if last_scan:
            logging.info(
                f"last_scan_type ==: {last_scan.scan_type}, last scan dt : {last_scan.date_time}"
            )

        logging.info(f"================== Finding Log ==================")
        yesterday_log, today_log, tomorrow_log = self.get_ssl(member, org)
        logging.info(f"yesterday_log : {yesterday_log}")
        logging.info(f"today_log : {today_log}")
        logging.info(f"tomorrow_log : {tomorrow_log}")
        logging.info(f"================== Finding Log Ended ==================")
        logging.info(f"")


        if last_scan is None:
            scan_type = "check_in"
        elif last_scan.scan_type == "check_out":
            scan_type = "check_in"
        elif last_scan.scan_type == "check_in":

            last_scan_dt = last_scan.date_time

            last_computed_dt = self.find_last_computation_dt(
                yesterday_log, today_log, tomorrow_log
            )

            logging.info(f"last_scan_dt --: {last_scan_dt}")
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

        logging.info(f"scan type : {scan_type}")

        image_count = member.member_images.all().count()

        if image_count > 0:
            allowed = True
        else:
            allowed = False

        check_in = True
        if scan_type == "check_in":
            check_in = False

        return Response({"check_in": check_in, "allowed": allowed}, status=status.HTTP_200_OK)


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

        logging.info(f"Today log is not working for for tomorrwo")

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


class ActivateMemberAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberSerializer

    def patch(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()


        try:
            member = Member.objects.get(organization=org, uuid=kwargs["uuid"])
        except Member.DoesNotExist:
            return read_data.get_404_response("Member")

        if requesting_member.role.name not in ("admin",) and member.role.name in ("admin", "hr"):
            return read_data.get_403_response()

        if member.status == "inactive":

            if is_allowed_to_add_members(org) is False:
                send_limit_exceeded_notification(org, request.user)
                return Response(
                    {"message": "Organization member limit reached. Please contact Empfly support."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            member.status="active"
        else:
            member.status="inactive"

        member.save()

        serializer = self.serializer_class( member )
        return HTTP_200(serializer.data)



class AllMembersDataAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberDataSerializer
    # serializer_class = serializers.MinimalMemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        members = org.members.all().select_related("user")

        search_query = request.GET.get("search")
        members = search.search_members(members, search_query)
        # members = filter_members(members, request)
        members = filter_qs_by_status(
            request=request, qs=members, default="active", choice=("active", "inactive")
        )

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
