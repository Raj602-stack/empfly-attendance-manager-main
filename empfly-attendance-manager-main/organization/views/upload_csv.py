from account.models import User
from member.models import Member
from utils.utils import convert_to_date
from visitor.models import Visitor
from organization.models import Department, Designation, Holiday, Role, SystemLocation
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import fetch_data, read_data
from utils.response import HTTP_200, HTTP_400
from utils import create_data
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from kiosk.models import Kiosk
from export.utils import string_status_to_bool
from django.db.models import Q


import logging

logger = logging.getLogger(__name__)


class DepartmentUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "department1",
                "description": "description1",
                "department head": "admin@peerxp.com, shahin.salim@peerxp.com",
                "status": "active",
            },
            {
                "name": "department2",
                "description": "description2",
                "department head": "admin@peerxp.com",
                "status": "inactive",
            },
        ]

        return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        member_role = fetch_data.get_member_role()
        all_departments = Department.objects.filter(organization=org)
        all_member = Member.objects.filter(organization=org)

        failed_departments = []
        failed_rows = []
        row_count = 1
        created_departments = 0
        updated_count = 0

        all_departments = Department.objects.filter(organization=org)

        for row in df.values:
            row_count += 1
            is_update = 0
            row_length = len(row)

            print(row, "@@@@@@@@@@@@@@@@@@@")

            try:

                if row_length == 4:  # import
                    dep_name = str(row[0]).strip()

                    if not dep_name:
                        raise ValidationError("department name is required")

                    department = all_departments.filter(name=dep_name)

                    if not department.exists():
                        print("======================================================")
                        dep_head = row[2]

                        department_heads = []
                        if dep_head:
                            dep_head = dep_head.split(", ")
                            department_heads = all_member.filter(
                                Q(user__email__in=dep_head)
                                | Q(user__phone__in=dep_head)
                            )

                        department = all_departments.filter(name=dep_name)

                        if not department.exists():
                            department_obj = Department.objects.create(
                                name=dep_name,
                                organization=org,
                                description=row[1],
                                is_active=string_status_to_bool(row[3]),
                            )

                            if department_heads:
                                department_obj.department_head.add(*department_heads)
                                department_obj.save()
                            created_departments += 1
                            continue

                    department = department.first()
                    print(department, "!!!!!!!!!!!!!!!!!!!!!!")

                if row_length == 5:  # Update

                    if not row[0]:
                        raise ValidationError("uuid is required")

                    department = all_departments.filter(uuid=row[0]).get()
                    is_update = 1

                    if row[1]:
                        department.name = row[1]

                if row[1 + is_update] in ("", "NA"):
                    department.description = None
                else:
                    department.description = row[1 + is_update]

                dep_head = row[2 + is_update]

                if dep_head:
                    dep_head = dep_head.split(", ")
                    department_heads = all_member.filter(
                        Q(user__email__in=dep_head) | Q(user__phone__in=dep_head)
                    )

                    department.department_head.clear()
                    department.department_head.add(*department_heads)

                department.is_active = string_status_to_bool(row[3 + is_update])
                department.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                try:
                    failed_departments.append(
                        {
                            "reason": str(e.__class__.__name__),
                            "detailed_reason": str(e),
                        }
                    )
                except Exception as e:
                    pass
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in DepartmentUploadCSVAPI"
                )

        return Response(
            {
                "failed_departments": failed_departments,
                "created_count": created_departments,
                "failed_rows": failed_rows,
                "updated_count": updated_count,
            },
            status=status.HTTP_201_CREATED,
        )


class SystemLocationsUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "Indiranagar",
                "description": "Indiranagar description",
                "latitude": 12.97837181055267,
                "longitude": 77.64436068922599,
                "radius": 200,
                "status": "active",
            },
            {
                "name": "HSR Layout",
                "description": "HSR Layout description",
                "latitude": 24.97837181055267,
                "longitude": 99.64436068922599,
                "radius": 55,
                "status": "active",
            },
        ]

        return JsonResponse(schema, safe=False, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        failed_rows = []
        failed_locations = []
        row_count = 1
        updated_count = 0
        created_locations = 0

        all_locations = SystemLocation.objects.filter(organization=org)

        for row in df.values:
            row_count += 1

            try:
                is_update = 0  # if not update value must be 0

                row_length = len(row)
                if row_length == 7:
                    is_update = 1

                system_location_status = row[5 + is_update]

                if system_location_status not in ("active", "inactive"):
                    raise ValidationError("Status must be active/inactive.")

                # Upload
                if row_length == 6:
                    if not row[0]:
                        raise ValidationError("name cannot be null.")

                    location = all_locations.filter(name=row[0])  # check with name

                    if row[4] is None or row[4] == "":
                        geo_fencing_radius = org.settings.get("geo_fencing_radius")
                        if geo_fencing_radius is None:
                            row[4] = 50
                        else:
                            row[4] = geo_fencing_radius

                    if not location.exists():
                        SystemLocation.objects.create(
                            organization=org,
                            name=row[0],
                            description=row[1],
                            latitude=row[2],
                            longitude=row[3],
                            radius=row[4],
                            status=system_location_status,
                        )
                        created_locations += 1
                        continue

                    location = location.first()

                # Update
                if row_length == 7:
                    location = all_locations.filter(uuid=row[0]).get()  # check with pk
                    is_update = 1

                    if row[1]:
                        location.name = row[1]

                description = row[1 + is_update]
                latitude = row[2 + is_update]
                longitude = row[3 + is_update]
                radius = row[4 + is_update]

                if not radius and not radius == 0 and not location.radius:
                    radius = org.settings.get("geo_fencing_radius")

                if description:
                    location.description = description
                elif description in ("", "NA"):
                    location.description = None

                if radius:
                    location.radius = radius
                if latitude and type(latitude) in (int, float):
                    location.latitude = latitude
                if longitude and type(latitude) in (int, float):
                    location.longitude = longitude

                location.status = system_location_status

                location.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                failed_locations.append(
                    {
                        "name": "",
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
                "created_count": created_locations,
                "failed_locations": failed_locations,
                "failed_rows": failed_rows,
                "updated_count": updated_count,
            },
            status=status.HTTP_201_CREATED,
        )


class DesignationUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "Indiranagar",
                "description": "Indiranagar description",
            },
            {
                "name": "HSR Layout",
                "description": "HSR Layout description",
            },
        ]

        return HTTP_200(schema)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        failed_rows = []
        failed_designation = []
        row_count = 1
        updated_count = 0
        created_designation = 0

        all_designation = Designation.objects.filter(organization=org)

        for row in df.values:
            row_count += 1

            try:
                is_update = 0  # if not update value must be 0
                row_length = len(row)

                # Upload
                if row_length == 2:
                    if not row[0]:
                        raise ValidationError("name cannot be null")

                    designation = all_designation.filter(name=row[0])  # check with name

                    if not designation.exists():
                        Designation.objects.create(
                            organization=org, name=row[0], description=row[1]
                        )
                        created_designation += 1
                        continue

                    designation = designation.first()

                # Update
                if row_length == 3:
                    designation = all_designation.filter(
                        uuid=row[0]
                    ).get()  # check with pk

                    is_update = 1

                    if row[1]:
                        designation.name = row[1]

                description = row[1 + is_update]

                if description:
                    designation.description = description
                elif description in ("", "NA"):
                    designation.description = None

                designation.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                failed_designation.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in designationUploadCSVAPI"
                )

        return Response(
            {
                "failed_designation": failed_designation,
                "created_count": created_designation,
                "failed_rows": failed_rows,
                "updated_count": updated_count,
            },
            status=status.HTTP_201_CREATED,
        )


class VisitorUploadCSVAPI(views.APIView):
    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "first_name": "user",
                "last_name": "1",
                "email": "user1@gmail.com",
                "phone": "8477457962",
                "status": "active",
            },
            {
                "first_name": "user",
                "last_name": "2",
                "email": "user2@gmail.com",
                "phone": "95146215624",
                "status": "inactive",
            },
        ]

        return HTTP_200(schema)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        if not csv_file:
            return HTTP_400({}, {})

        df = create_data.create_pandas_dataframe(csv_file)

        failed_rows = []
        failed_visitor = []
        row_count = 1
        updated_count = 0
        created_visitor = 0

        all_visitor = Visitor.objects.filter(organization=org)

        # first name, last name, email, phone, status

        visitor_role = Role.objects.get_or_create(name="visitor")[0]

        for row in df.values:
            row_count += 1

            try:
                is_update = 0

                print(row)

                row_length = len(row)
                if row_length == 6:
                    is_update = 1

                print(f"row_length : {row_length}")
                first_name = row[0 + is_update]
                last_name = row[1 + is_update]
                email = row[2 + is_update]
                phone = row[3 + is_update]
                visitor_status = row[4 + is_update]

                phone = str(phone)
                if phone.endswith(".0"):
                    print("Before split")
                    print(phone)
                    phone = phone.split(".0", maxsplit=1)[0]

                print(first_name)
                print(last_name)
                print(email)
                print(phone)
                print(visitor_status)
                print("#############")

                if visitor_status not in ("active", "inactive"):
                    raise ValidationError("Status must be active/inactive.")

                if not first_name:
                    raise ValidationError("first name is required.")

                if not email:
                    raise ValidationError("Email is required.")

                # Upload
                if row_length == 5:

                    visitor = all_visitor.filter(user__email=email)

                    if not visitor.exists():
                        user, _ = create_data.create_user(
                            email=email, first_name=first_name
                        )

                        visitor = Visitor.objects.create(
                            user=user,
                            role=visitor_role,
                            organization=org,
                            status=visitor_status,
                        )
                        created_visitor += 1

                        user.last_name = last_name
                        if (
                            phone != "NA"
                            and User.objects.filter(phone=phone).exists() is False
                        ):
                            user.phone = phone
                        user.save()
                        continue

                    visitor = visitor.first()
                    user = visitor.user

                # Update
                if row_length == 6:
                    visitor = all_visitor.filter(uuid=row[0]).get()
                    user = visitor.user

                if first_name:
                    user.first_name = first_name
                user.last_name = last_name

                if (
                    user.email != email
                    and User.objects.filter(email=email).exists() is False
                ):
                    user.email = email

                if phone in (None, ""):
                    user.phone = None
                elif (
                    phone != "NA"
                    and user.phone != phone
                    and User.objects.filter(phone=phone).exists() is False
                ):
                    user.phone = phone

                visitor.status = visitor_status
                visitor.save()
                user.save()
                updated_count += 1

            except Exception as e:
                failed_rows.append(row_count)
                failed_visitor.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in visitorUploadCSVAPI"
                )

        return Response(
            {
                "failed_visitor": failed_visitor,
                "created_count": created_visitor,
                "failed_rows": failed_rows,
                "updated_count": updated_count,
            },
            status=status.HTTP_201_CREATED,
        )


class HolidaysUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "name": "New Year",
                "description": "New Year",
                "date": "01-12-2023",
            },
            {
                "name": "Christmas",
                "description": "Happy Christmas",
                "date": "01-12-2023",
            },
        ]
        return HTTP_200(schema)

    def post(self, request, *args, **kwargs):
        print("-----------" * 10)
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        if df is None:
            return HTTP_400({}, {})

        failed_members = []

        created_count = 0
        update_count = 0
        failed_rows = []
        row_count = 1

        all_holidays = Holiday.objects.filter(organization=org)

        for row in df.values:
            print(row)
            row_count += 1
            row_length = len(row)
            is_create = False
            print(row_length, "----------row_length-----------")

            is_update = 0
            if row_length == 5:
                is_update = 1

            print(is_update, "######## is_update")

            name = str(row[0 + is_update]).lower()
            description = (str(row[1 + is_update])).split(".", maxsplit=1)[0]
            date = row[2 + is_update]
            print(date, "$$$$$$$ dateEEEEEEEEEE")
            try:
                if row_length not in (3, 5):
                    raise ValidationError("Row length must be 3 or 5.")

                valid_date = create_data.convert_string_to_datetime(
                    date, format="%d-%m-%Y"
                )
                if not valid_date:
                    raise ValidationError("Date is not valid")

                if row_length == 3:
                    # create

                    holidays = all_holidays.filter(name=name)
                    if holidays.exists():
                        holiday = holidays.first()
                    else:
                        Holiday.objects.create(
                            name=name,
                            description=description,
                            date=valid_date,
                            organization=org,
                        )
                        created_count += 1
                        continue
                elif row_length == 5:
                    holiday = all_holidays.get(uuid=row[0])

                holiday.date = valid_date
                holiday.name = name
                holiday.description = description

                holiday.save()
                update_count += 1

            except Exception as err:
                failed_rows.append(row_count)
                try:
                    failed_members.append(
                        {
                            "email": row[0],
                            "reason": str(err.__class__.__name__),
                            "detailed_reason": str(err),
                        }
                    )
                except Exception:
                    pass
                logger.error(err)
                logger.exception(
                    f"Add exception for {err.__class__.__name__} in MembersUploadCSVAPI"
                )

        return Response(
            {
                "failed_members": failed_members,
                "created_count": created_count,
                "failed_rows": failed_rows,
                "updated_count": update_count,
            },
            status=status.HTTP_201_CREATED,
        )
