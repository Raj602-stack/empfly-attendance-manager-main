from django.contrib.postgres.search import SearchVector


LEAVE_REQUEST_FIELDS = [
    "member_uuid",
    "member__user__first_name",
    "member__user__last_name",
    "member__user__email",
    "member__user__phone",
    "member__role__name",
    "member__designation__name",
    "member__department__name",
    "leave_type__name",
    "leave_type__description",
]


def search_leave_requests(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    return qs.annotate(search=SearchVector(*LEAVE_REQUEST_FIELDS)).filter(
        search__contains=search_query
    )
