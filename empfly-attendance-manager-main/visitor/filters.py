
def convert_query_params_to_dict(query_params: dict) -> dict:

    new_dict = {}
    for key in query_params.keys():
        if query_params.get(key) == "":
            continue
        if "uuid" in key:
            new_dict[key] = query_params.getlist(key)
        else:
            new_dict[key] = query_params.get(key)
    return new_dict


def set_if_not_none(mapping: dict, key: str, value: str, new_key: str):
    if key:
        mapping[new_key] = value


def filter_visitor_scan(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs

    # Convert query parameters to ORM filters
    name_mapping = {
        "visitor_uuid": "visitor__uuid__in",
        "start_date": "date__gte",
        "end_date": "date__lte",
        "visitation_uuid": "visitation__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)




def filter_visitations(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs

    # Convert query parameters to ORM filters
    name_mapping = {
        "visitor_uuid": "visitor__uuid__in",
        "host_uuid": "host__uuid__in",
        "start_date": "visitation_date__gte",
        "end_date": "visitation_date__lte",
        "visitation_status": "visitation_status",
        "created_by_uuid": "created_by__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)





def filter_visitations_for_report(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs

    # Convert query parameters to ORM filters
    name_mapping = {
        "visitor_uuids": "visitor__uuid__in",
        "host_uuids": "host__uuid__in",
        "start_date": "visitation_date__gte",
        "end_date": "visitation_date__lte",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)

