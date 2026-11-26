"""Shared pagination class for every list endpoint."""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a client-adjustable page size.

    ?page=2            -> second page
    ?page_size=20      -> 20 items per page (capped at `max_page_size`)
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
