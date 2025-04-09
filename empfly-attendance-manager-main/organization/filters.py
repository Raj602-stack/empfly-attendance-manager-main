
from visitor.filters import convert_query_params_to_dict, set_if_not_none


def filter_holidays(qs: "Queryset", request) -> "Queryset":

    filter_query = convert_query_params_to_dict(request.GET)

    if filter_query is None:
        return qs


    # Convert query parameters to ORM filters
    name_mapping = {
        "org_location_uuids": "org_location__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)

