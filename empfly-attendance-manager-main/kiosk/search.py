from django.contrib.postgres.search import SearchVector
from utils.utils import create_search_filter


SEARCH_KIOSKS_FIELDS = ["kiosk_name"]


def search_kiosks(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_KIOSKS_FIELDS, search_query)

    return qs.filter(filters)
