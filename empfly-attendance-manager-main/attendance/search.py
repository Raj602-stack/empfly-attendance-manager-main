

from django.contrib.postgres.search import SearchVector
from utils.utils import create_search_filter

MEMBER_SCAN_SEARCH_FIELDS = [
    "member__user__email",
    "member__user__first_name",
    "member__user__last_name",
]

ATTENDANCE_SEARCH_FIELDS = [
    "member__user__email",
    "member__user__first_name",
    "member__user__last_name",
]

def search_member_scan(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(MEMBER_SCAN_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_attendance(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(ATTENDANCE_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
