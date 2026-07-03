"""Fetch real OpenAlex data across multiple KG/GNN/LLM topics and regenerate demo_dataset.py.

Tier 1 (recent): ~200 journal articles from the last 30 days across 3 topic searches
Tier 2 (foundational): top 50 most-cited older papers referenced by Tier 1

Regenerate:  python scripts/refresh_demo_data.py
"""

from __future__ import annotations

import json
import pprint
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib import parse, request

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from researchknowledgegraphaws.ingestion.openalex_client import fetch_works

DEMO_DATASET_PATH = (
    Path(__file__).parent.parent
    / "src/researchknowledgegraphaws/ingestion/demo_dataset.py"
)

SEARCHES = [
    "knowledge graph embedding completion reasoning",
    "graph neural network link prediction node classification",
    "large language model knowledge graph reasoning",
]
FILTER_EXTRA = "type:article,primary_location.source.type:journal"
RECENT_PER_SEARCH = 80   # fetch up to 80 quality papers per search
FOUNDATIONAL_LIMIT = 50  # top cited foundational works


def _fetch_by_ids(openalex_ids: list[str]) -> list[dict]:
    if not openalex_ids:
        return []
    ids_filter = "|".join(openalex_ids)
    params = {
        "filter": f"ids.openalex:{ids_filter}",
        "per-page": str(min(len(openalex_ids), 200)),
        "select": "id,title,display_name,publication_year,authorships,primary_location,topics,referenced_works",
    }
    url = f"https://api.openalex.org/works?{parse.urlencode(params)}"
    req = request.Request(url, headers={"user-agent": "ResearchKnowledgeGraphAWS/0.1"})
    with request.urlopen(req, timeout=30) as resp:
        return (json.loads(resp.read()).get("results") or [])


def _clean_work(work: dict, keep_refs: bool = True) -> dict:
    authorships = []
    for a in (work.get("authorships") or [])[:5]:
        author = a.get("author") or {}
        if not author.get("id"):
            continue
        institutions = [
            {"id": i["id"], "display_name": i.get("display_name", i["id"])}
            for i in (a.get("institutions") or [])[:2]
            if i.get("id")
        ]
        authorships.append({
            "author": {"id": author["id"], "display_name": author.get("display_name", author["id"])},
            "institutions": institutions,
        })

    raw_src = ((work.get("primary_location") or {}).get("source") or {})
    primary_location = None
    if raw_src.get("id"):
        primary_location = {"source": {
            "id": raw_src["id"],
            "display_name": raw_src.get("display_name", raw_src["id"]),
            "publisher": raw_src.get("publisher"),
        }}

    topics = [
        {"id": t["id"], "display_name": t.get("display_name", t["id"])}
        for t in (work.get("topics") or [])[:4]
        if t.get("id")
    ]

    return {
        "id": work["id"],
        "title": work.get("title") or work.get("display_name") or work["id"],
        "publication_year": work.get("publication_year"),
        "authorships": authorships,
        "primary_location": primary_location,
        "topics": topics,
        "referenced_works": (work.get("referenced_works") or [])[:15] if keep_refs else [],
    }


def _is_quality(work: dict) -> bool:
    return bool(work.get("topics")) and len(work.get("authorships") or []) >= 2


def _generate_module(works: list[dict], from_date: str, to_date: str, n_recent: int) -> str:
    indented = pprint.pformat(works, indent=4, width=100)
    searches_str = ", ".join(f'"{s}"' for s in SEARCHES)
    return f'''\
"""Real OpenAlex data: {n_recent} recent papers ({from_date}–{to_date}) + foundational cited works.

Searches: {searches_str}
Regenerate with:  python scripts/refresh_demo_data.py
"""

from __future__ import annotations

from copy import deepcopy


DEMO_WORKS: list[dict] = {indented}


def get_demo_works(limit: int | None = None) -> list[dict]:
    """Return demo works in OpenAlex-compatible shape."""
    if limit is None or limit < 1:
        selected = DEMO_WORKS
    else:
        selected = DEMO_WORKS[: min(limit, len(DEMO_WORKS))]
    return deepcopy(selected)
'''


def main() -> None:
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=30)).isoformat()

    # --- Tier 1: recent papers across all searches ---
    seen_ids: set[str] = set()
    recent_raw: list[dict] = []

    for search in SEARCHES:
        print(f"Fetching '{search[:50]}...' ({from_date} → {to_date})")
        batch = fetch_works(
            search=search,
            limit=RECENT_PER_SEARCH * 3,
            per_page=50,
            from_publication_date=from_date,
            to_publication_date=to_date,
            extra_filters=FILTER_EXTRA,
        )
        quality = [w for w in batch if _is_quality(w) and w["id"] not in seen_ids][:RECENT_PER_SEARCH]
        for w in quality:
            seen_ids.add(w["id"])
        recent_raw.extend(quality)
        print(f"  +{len(quality)} papers (total {len(recent_raw)})")

    print(f"\n{len(recent_raw)} unique recent papers total.")

    # --- Tier 2: top foundational papers ---
    ref_counter: Counter = Counter()
    for w in recent_raw:
        for ref in (w.get("referenced_works") or []):
            if ref not in seen_ids:
                ref_counter[ref] += 1

    top_refs = [ref_id for ref_id, _ in ref_counter.most_common(FOUNDATIONAL_LIMIT)]
    print(f"Fetching top {len(top_refs)} foundational papers ...")
    foundational_raw = [w for w in _fetch_by_ids(top_refs) if w.get("title") or w.get("display_name")]
    print(f"  {len(foundational_raw)} foundational papers retrieved.")

    # Filter referenced_works to only those we're actually loading
    foundational_ids = {w["id"] for w in foundational_raw}
    all_ids = seen_ids | foundational_ids

    cleaned_recent = []
    for w in recent_raw:
        c = _clean_work(w, keep_refs=True)
        c["referenced_works"] = [r for r in c["referenced_works"] if r in all_ids]
        cleaned_recent.append(c)

    cleaned_foundational = [_clean_work(w, keep_refs=False) for w in foundational_raw]
    all_works = cleaned_recent + cleaned_foundational

    module_src = _generate_module(all_works, from_date, to_date, len(cleaned_recent))
    DEMO_DATASET_PATH.write_text(module_src, encoding="utf-8")

    cites = sum(len(w["referenced_works"]) for w in cleaned_recent)
    authors = len({a["author"]["id"] for w in all_works for a in w.get("authorships", [])})
    institutions = len({i["id"] for w in all_works for a in w.get("authorships", []) for i in a.get("institutions", [])})
    topics = len({t["id"] for w in all_works for t in w.get("topics", [])})

    print(f"\n{'─'*55}")
    print(f"  Works:        {len(all_works)}  ({len(cleaned_recent)} recent + {len(cleaned_foundational)} foundational)")
    print(f"  Authors:      {authors}")
    print(f"  Institutions: {institutions}")
    print(f"  Topics:       {topics}")
    print(f"  Citation edges: {cites}")
    print(f"{'─'*55}")
    print(f"Written → {DEMO_DATASET_PATH}")


if __name__ == "__main__":
    main()
