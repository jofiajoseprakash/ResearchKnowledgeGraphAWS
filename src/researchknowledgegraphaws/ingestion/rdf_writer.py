"""RDF/Turtle writer for normalized OpenAlex works."""

from __future__ import annotations

import re

from researchknowledgegraphaws.ingestion.models import Work


BASE = "https://example.org/research-kg/resource/"
KG = "https://example.org/research-kg/ontology/"


def openalex_key(openalex_id: str) -> str:
    return openalex_id.rstrip("/").split("/")[-1]


def slug(openalex_id: str) -> str:
    key = openalex_key(openalex_id)
    return re.sub(r"[^A-Za-z0-9_-]+", "_", key)


def iri(kind: str, openalex_id: str) -> str:
    return f"<{BASE}{kind}/{slug(openalex_id)}>"


def literal(value: object) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def work_to_turtle(work: Work) -> str:
    lines = [
        f"{iri('work', work.id)} a kg:Work ;",
        f"    rdfs:label {literal(work.title)} ;",
        f"    kg:hasOpenAlexId {literal(openalex_key(work.id))} .",
    ]
    if work.publication_year:
        lines.append(
            f"{iri('work', work.id)} kg:publicationYear {work.publication_year} ."
        )

    if work.source:
        source_iri = iri("source", work.source.id)
        lines.extend(
            [
                f"{source_iri} a kg:Source ;",
                f"    rdfs:label {literal(work.source.display_name)} ;",
                f"    kg:hasOpenAlexId {literal(openalex_key(work.source.id))} .",
                f"{iri('work', work.id)} kg:publishedIn {source_iri} .",
            ]
        )
        if work.source.publisher:
            publisher_id = slug(work.source.publisher)
            publisher_iri = f"<{BASE}publisher/{publisher_id}>"
            lines.extend(
                [
                    f"{publisher_iri} a kg:Publisher ;",
                    f"    rdfs:label {literal(work.source.publisher)} .",
                    f"{source_iri} kg:publishedBy {publisher_iri} .",
                ]
            )

    for author in work.authors:
        author_iri = iri("author", author.id)
        lines.extend(
            [
                f"{author_iri} a kg:Author ;",
                f"    rdfs:label {literal(author.display_name)} ;",
                f"    kg:hasOpenAlexId {literal(openalex_key(author.id))} .",
                f"{iri('work', work.id)} kg:authoredBy {author_iri} .",
            ]
        )
        for institution in author.institutions:
            institution_iri = iri("institution", institution.id)
            lines.extend(
                [
                    f"{institution_iri} a kg:Institution ;",
                    f"    rdfs:label {literal(institution.display_name)} ;",
                    f"    kg:hasOpenAlexId {literal(openalex_key(institution.id))} .",
                    f"{author_iri} kg:affiliatedWith {institution_iri} .",
                ]
            )

    for topic in work.topics:
        topic_iri = iri("topic", topic.id)
        lines.extend(
            [
                f"{topic_iri} a kg:Topic ;",
                f"    rdfs:label {literal(topic.display_name)} ;",
                f"    kg:hasOpenAlexId {literal(openalex_key(topic.id))} .",
                f"{iri('work', work.id)} kg:hasTopic {topic_iri} .",
            ]
        )

    for referenced_work_id in work.referenced_work_ids:
        lines.append(f"{iri('work', work.id)} kg:cites {iri('work', referenced_work_id)} .")

    return "\n".join(lines)


def works_to_turtle(works: list[Work]) -> str:
    header = "\n".join(
        [
            f"@prefix kg: <{KG}> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
        ]
    )
    return header + "\n\n".join(work_to_turtle(work) for work in works) + "\n"
