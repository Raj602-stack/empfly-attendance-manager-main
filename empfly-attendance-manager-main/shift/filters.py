
from visitor.filters import convert_query_params_to_dict, set_if_not_none


def filter_shift(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "start_date": "created_at__gte",
        "end_date": "created_at__lte",
        "org_location_uuid": "org_location__uuid__in",
        # "shift_uuid": "applicable_shift__uuid__in",
        "shift_uuid": "shift_schedule_logs__shift__uuid__in",
        
        "department_uuid": "department__uuid__in",
        "employee_uuid": "uuid__in",
        "designation_uuid": "designation__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)





def filter_shift_schedule_log(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        # "status": "status",
        "is_esm": "is_esm",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)
