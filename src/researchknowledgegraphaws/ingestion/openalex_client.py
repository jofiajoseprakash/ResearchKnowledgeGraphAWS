"""OpenAlex API client."""

from __future__ import annotations

import json
from urllib import parse, request


OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def fetch_works(
    search: str,
    limit: int = 500,
    per_page: int = 100,
    from_publication_date: str | None = None,
    to_publication_date: str | None = None,
    extra_filters: str | None = None,
) -> list[dict]:
    """Fetch a bounded set of OpenAlex works for a search phrase.

    Args:
        search: Keyword search string.
        limit: Maximum number of works to return.
        per_page: Page size for each API request (max 200).
        from_publication_date: ISO date string (YYYY-MM-DD) for the earliest publication date.
        to_publication_date: ISO date string (YYYY-MM-DD) for the latest publication date.
        extra_filters: Additional OpenAlex filter string (comma-separated key:value pairs).
    """
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    filters: list[str] = []
    if from_publication_date:
        filters.append(f"from_publication_date:{from_publication_date}")
    if to_publication_date:
        filters.append(f"to_publication_date:{to_publication_date}")
    if extra_filters:
        filters.append(extra_filters)

    works: list[dict] = []
    cursor = "*"
    while len(works) < limit:
        page_size = min(per_page, limit - len(works))
        params: dict[str, str] = {
            "search": search,
            "per-page": str(page_size),
            "cursor": cursor,
            "select": ",".join(
                [
                    "id",
                    "title",
                    "display_name",
                    "publication_year",
                    "authorships",
                    "primary_location",
                    "topics",
                    "referenced_works",
                ]
            ),
        }
        if filters:
            params["filter"] = ",".join(filters)
        url = f"{OPENALEX_WORKS_URL}?{parse.urlencode(params)}"
        req = request.Request(url, headers={"user-agent": "ResearchKnowledgeGraphAWS/0.1"})
        with request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        works.extend(payload.get("results") or [])
        next_cursor = (payload.get("meta") or {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return works[:limit]
