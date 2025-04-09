
from account.models import User
from attendance.models import Attendance, MemberScan
from member.models import Member
from visitor.filters import convert_query_params_to_dict, set_if_not_none


def filter_member_scan(qs: MemberScan, request) -> MemberScan:

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "start_date": "date_time__date__gte",
        "end_date": "date_time__date__lte",
        "employee_uuids": "member__uuid__in",
        "system_location_uuids": "system_location__uuid__in",
        "department_uuids": "member__department__uuid__in",
        "org_location_uuids": "member__org_location__uuid__in",
        "designation_uuids": "member__designation__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)



def filter_attendance(qs: Attendance, request) -> Attendance:

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "member_uuids": "member__uuid__in",
        "designation_uuids": "member__designation__uuid__in",
        "org_location_uuids": "member__org_location__uuid__in",
        "department_uuids": "member__department__uuid__in",
        "start_date": "date__gte",
        "end_date": "date__lte",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)




def filter_report_for_attendance(qs: Attendance, request) -> Attendance:

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        # "member_uuids": "member__uuid__in",
        "designation_uuids": "member__designation__uuid__in",
        "org_location_uuids": "member__org_location__uuid__in",
        "department_uuids": "member__department__uuid__in",
        "start_date": "date__gte",
        "end_date": "date__lte",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)

def filter_ot_request(qs: Attendance, request) -> Attendance:

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "member_uuids": "member__uuid__in",
        "start_date": "date__gte",
        "end_date": "date__lte",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)



def filter_my_attendance(qs: Attendance, request) -> Attendance:

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "ot_status": "ot_status",
        "start_date": "date__gte",
        "end_date": "date__lte",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)

