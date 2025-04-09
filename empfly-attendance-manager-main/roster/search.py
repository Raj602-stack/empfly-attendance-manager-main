from django.contrib.postgres.search import SearchVector


SEARCH_FIELDS = ["name", "description"]
LOCATION_SEARCH_FIELDS = ["name", "description", "latitude", "longitude"]
SHIFT_SEARCH_FIELDS = ["name", "description", "latitude", "longitude"]
SEARCH_SHIFT = ["name", "description"]


def search_locations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    return qs.annotate(search=SearchVector(*LOCATION_SEARCH_FIELDS)).filter(
        search__contains=search_query
    )


def search_shifts(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    return qs.annotate(search=SearchVector(*SEARCH_SHIFT)).filter(
        search__contains=search_query
    )


def search_rosters(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    return qs.annotate(search=SearchVector(*SEARCH_FIELDS)).filter(
        search__contains=search_query
    )


# def search_clusters(qs: "Queryset", search_query: str) -> "Queryset":

#     if search_query is None:
#         return qs

#     return qs.annotate(search=SearchVector(*SEARCH_FIELDS)).filter(
#         search__contains=search_query
#     )
