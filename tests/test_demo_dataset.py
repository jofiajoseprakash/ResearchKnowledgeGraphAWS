from researchknowledgegraphaws.ingestion.demo_dataset import DEMO_WORKS, get_demo_works
from researchknowledgegraphaws.ingestion.models import parse_work
from researchknowledgegraphaws.ingestion.rdf_writer import works_to_turtle


def test_demo_dataset_has_citations():
    referenced_ids = {
        referenced_id
        for work in DEMO_WORKS
        for referenced_id in work.get("referenced_works", [])
    }
    # Real papers cite papers outside the 25-work subset; we just need citations present.
    assert referenced_ids


def test_demo_dataset_generates_valid_rdf():
    works = [parse_work(payload) for payload in get_demo_works()]
    turtle = works_to_turtle(works)

    first_title = DEMO_WORKS[0]["title"]
    assert first_title in turtle
    assert "kg:authoredBy" in turtle
    assert "kg:hasTopic" in turtle
    assert "kg:cites" in turtle


def test_demo_dataset_limit_is_bounded():
    assert len(get_demo_works(limit=3)) == 3
    assert len(get_demo_works(limit=999)) == len(DEMO_WORKS)
