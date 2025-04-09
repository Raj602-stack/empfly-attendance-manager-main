from django.contrib.postgres.search import SearchVector
from utils.utils import create_search_filter


SEARCH_FIELDS = ["name", "description"]
LOCATION_SEARCH_FIELDS = ["name", "description"]
SHIFT_SEARCH_FIELDS = ["name", "description", "latitude", "longitude"]
SYSTEM_LOCATION_SEARCH_FIELDS = ["name"]
DEPARTMENT_SEARCH_FIELDS = ["name", "description"]
DESIGNATION_SEARCH_FIELDS = ["name", "description"]
HOLIDAYS_SEARCH_FIELDS = ["name", "description"]


def search_org_locations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(LOCATION_SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_system_locations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SYSTEM_LOCATION_SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_department(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(DEPARTMENT_SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_designation(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(DESIGNATION_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_holidays(qs: "Queryset", search_query: str) -> "Queryset":

    if not search_query:
        return qs

    filters = create_search_filter(HOLIDAYS_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
