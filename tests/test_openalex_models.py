from researchknowledgegraphaws.ingestion.models import parse_work


def test_parse_work_normalizes_openalex_payload():
    work = parse_work(
        {
            "id": "https://openalex.org/W123",
            "title": "A Graph Approach to AI",
            "publication_year": 2025,
            "authorships": [
                {
                    "author": {
                        "id": "https://openalex.org/A1",
                        "display_name": "Ada Lovelace",
                    },
                    "institutions": [
                        {
                            "id": "https://openalex.org/I1",
                            "display_name": "Example University",
                        }
                    ],
                }
            ],
            "primary_location": {
                "source": {
                    "id": "https://openalex.org/S1",
                    "display_name": "Journal of Graphs",
                    "publisher": "Example Publisher",
                }
            },
            "topics": [{"id": "https://openalex.org/T1", "display_name": "Artificial Intelligence"}],
            "referenced_works": ["https://openalex.org/W99"],
        }
    )

    assert work.id == "https://openalex.org/W123"
    assert work.authors[0].display_name == "Ada Lovelace"
    assert work.authors[0].institutions[0].display_name == "Example University"
    assert work.source and work.source.publisher == "Example Publisher"
    assert work.topics[0].display_name == "Artificial Intelligence"
    assert work.referenced_work_ids == ("https://openalex.org/W99",)
