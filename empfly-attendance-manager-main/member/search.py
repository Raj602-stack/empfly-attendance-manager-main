from django.contrib.postgres.search import SearchVector
from utils.utils import create_search_filter


MEMBER_SEARCH_FIELDS = [
    "user__first_name",
    "user__last_name",
    "user__email",
    "user__phone"
]


MEMBER_IMAGES_SEARCH_FIELDS = [
    "member__user__email",
    "member__user__first_name",
    "member__user__last_name",
]

def search_members(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(MEMBER_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_member_images(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(MEMBER_IMAGES_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
