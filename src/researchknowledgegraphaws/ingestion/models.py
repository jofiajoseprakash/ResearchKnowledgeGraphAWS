"""Domain models for normalized OpenAlex records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Institution:
    id: str
    display_name: str


@dataclass(frozen=True)
class Author:
    id: str
    display_name: str
    institutions: tuple[Institution, ...] = ()


@dataclass(frozen=True)
class Source:
    id: str
    display_name: str
    publisher: str | None = None


@dataclass(frozen=True)
class Topic:
    id: str
    display_name: str


@dataclass(frozen=True)
class Work:
    id: str
    title: str
    publication_year: int | None = None
    authors: tuple[Author, ...] = ()
    source: Source | None = None
    topics: tuple[Topic, ...] = ()
    referenced_work_ids: tuple[str, ...] = field(default_factory=tuple)


def parse_work(payload: dict[str, Any]) -> Work:
    authors: list[Author] = []
    for authorship in payload.get("authorships") or []:
        raw_author = authorship.get("author") or {}
        author_id = raw_author.get("id")
        if not author_id:
            continue
        institutions = tuple(
            Institution(id=inst["id"], display_name=inst.get("display_name") or inst["id"])
            for inst in authorship.get("institutions") or []
            if inst.get("id")
        )
        authors.append(
            Author(
                id=author_id,
                display_name=raw_author.get("display_name") or author_id,
                institutions=institutions,
            )
        )

    raw_location = payload.get("primary_location") or {}
    raw_source = raw_location.get("source") or {}
    source = None
    if raw_source.get("id"):
        source = Source(
            id=raw_source["id"],
            display_name=raw_source.get("display_name") or raw_source["id"],
            publisher=raw_source.get("publisher"),
        )

    topics = tuple(
        Topic(id=topic["id"], display_name=topic.get("display_name") or topic["id"])
        for topic in payload.get("topics") or []
        if topic.get("id")
    )

    return Work(
        id=payload["id"],
        title=payload.get("title") or payload.get("display_name") or payload["id"],
        publication_year=payload.get("publication_year"),
        authors=tuple(authors),
        source=source,
        topics=topics,
        referenced_work_ids=tuple(payload.get("referenced_works") or ()),
    )
