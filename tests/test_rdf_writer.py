from researchknowledgegraphaws.ingestion.models import Author, Institution, Topic, Work
from researchknowledgegraphaws.ingestion.rdf_writer import openalex_key, works_to_turtle


def test_openalex_key_extracts_final_id_segment():
    assert openalex_key("https://openalex.org/W123") == "W123"


def test_works_to_turtle_emits_core_triples():
    work = Work(
        id="https://openalex.org/W123",
        title='Graph "AI" Paper',
        publication_year=2025,
        authors=(
            Author(
                id="https://openalex.org/A1",
                display_name="Ada Lovelace",
                institutions=(
                    Institution(
                        id="https://openalex.org/I1",
                        display_name="Example University",
                    ),
                ),
            ),
        ),
        topics=(Topic(id="https://openalex.org/T1", display_name="Artificial Intelligence"),),
        referenced_work_ids=("https://openalex.org/W99",),
    )

    turtle = works_to_turtle([work])

    assert "@prefix kg:" in turtle
    assert "<https://example.org/research-kg/resource/work/W123> a kg:Work" in turtle
    assert 'rdfs:label "Graph \\"AI\\" Paper"' in turtle
    assert "kg:authoredBy <https://example.org/research-kg/resource/author/A1>" in turtle
    assert "kg:affiliatedWith <https://example.org/research-kg/resource/institution/I1>" in turtle
    assert "kg:hasTopic <https://example.org/research-kg/resource/topic/T1>" in turtle
    assert "kg:cites <https://example.org/research-kg/resource/work/W99>" in turtle
