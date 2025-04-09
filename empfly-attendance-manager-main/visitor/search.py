from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Q
from django.db.models.functions import Concat
from django.db.models import Value as V
from utils.utils import create_search_filter


SEARCH_VISITOR_FIELDS = ["full_name", "user__email"]
SEARCH_VISITOR_IMAGES_FIELDS = [
    "visitor__user__first_name",
    "visitor__user__last_name",
    "visitor__user__email",
]
# SEARCH_VISITOR_SCAN_FIELDS = [
#     "visitor__user__first_name",
#     "visitor__user__last_name",
#     "visitor__user__email",
# ]
SEARCH_VISITATIONS = ["visitor__user__email", "name"]

SEARCH_VISITOR_SCAN_FIELDS = [
    "full_name",
    "visitor__user__email",
    "visitation__name",
]

VISITOR_SEARCH_FIELDS = [
    "user__username",
    "full_name"
]

VISITOR_SCAN_SEARCH_FIELDS = [
    "visitor__user__email",
    "full_name",
    "visitation__name",
]

def search_visitors(qs: "Queryset", search_query: str) -> "Queryset":

    if not search_query:
        return qs

    filters = create_search_filter(VISITOR_SEARCH_FIELDS, search_query)

    return qs.annotate(
        full_name=Concat(
            "user__first_name", V(" "), "user__last_name"
        )
    ).filter(filters)

def search_visitor_images(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_VISITOR_IMAGES_FIELDS, search_query)
    return qs.filter(filters)


def search_visitor_scan(qs: "Queryset", search_query: str) -> "Queryset":

    if not search_query:
        return qs

    filters = create_search_filter(VISITOR_SCAN_SEARCH_FIELDS, search_query)
    return qs.annotate(
        full_name=Concat(
            "visitor__user__first_name", V(" "), "visitor__user__last_name"
        )
    ).filter(filters)


def search_visitations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_VISITATIONS, search_query)
    return qs.filter(filters)
