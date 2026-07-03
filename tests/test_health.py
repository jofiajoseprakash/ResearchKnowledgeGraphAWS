import json

from researchknowledgegraphaws.api.health import handler


def test_health_handler_returns_ok():
    response = handler({}, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "ok"
