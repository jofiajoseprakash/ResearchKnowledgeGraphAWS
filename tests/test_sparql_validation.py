import pytest

from researchknowledgegraphaws.shared.sparql import validate_read_only_query


def test_validate_read_only_query_accepts_select():
    validate_read_only_query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 10")


def test_validate_read_only_query_rejects_update():
    with pytest.raises(ValueError):
        validate_read_only_query("DELETE WHERE { ?s ?p ?o }")
