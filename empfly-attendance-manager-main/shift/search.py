from django.contrib.postgres.search import SearchVector
from django.db.models import Q
from django.db.models.functions import Concat
from django.db.models import Value as V
from utils.utils import create_search_filter


SHIFT_SEARCH_FIELDS = [
    "name",
]

ESM_SEARCH_FIELDS = [
    "user__email",
    "full_name"
]

LOCATION_SETTINGS_SEARCH_FIELDS = [
    "full_name",
    "employee__user__email"
]

SSL_EMPLOYEES_SEARCH_FIELDS = [
    "user__email",
    "full_name"
]


def search_shift(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SHIFT_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_employee(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query in (None, ""):
        return qs

    filters = create_search_filter(ESM_SEARCH_FIELDS, search_query)

    return qs.annotate(
        full_name=Concat(
            "user__first_name", V(" "), "user__last_name"
        )
    ).filter(filters)


def search_location_settings(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(LOCATION_SETTINGS_SEARCH_FIELDS, search_query)
    return qs.annotate().filter(
        full_name=Concat(
            "employee__user__first_name", V(" "), "employee__user__last_name"
        )
    ).filter(filters)


def search_ssl_employees(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query in (None, ""):
        return qs

    filters = create_search_filter(SSL_EMPLOYEES_SEARCH_FIELDS, search_query)
    return qs.annotate(
        full_name=Concat(
            "user__first_name", V(" "), "user__last_name"
        )
    ).filter(filters)
