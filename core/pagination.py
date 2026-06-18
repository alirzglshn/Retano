# core/pagination.py

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Default pagination for all list endpoints.

    Query parameters:
        page      — page number (1-based)
        page_size — items per page (default 20, max 100)

    Response shape:
        {
            "count":    <total items>,
            "next":     <next page URL or null>,
            "previous": <previous page URL or null>,
            "total_pages": <total page count>,
            "current_page": <current page number>,
            "results":  [...]
        }
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": [
                "count",
                "next",
                "previous",
                "total_pages",
                "current_page",
                "results",
            ],
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of items across all pages.",
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL of the next page, or null.",
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL of the previous page, or null.",
                },
                "total_pages": {
                    "type": "integer",
                    "description": "Total number of pages.",
                },
                "current_page": {
                    "type": "integer",
                    "description": "Current page number.",
                },
                "results": schema,
            },
        }
