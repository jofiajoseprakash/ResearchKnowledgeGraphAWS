"""Auth endpoint — exchanges email/password for a Cognito IdToken."""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from researchknowledgegraphaws.shared.http import json_response, parse_json_body


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    client_id = os.environ.get("COGNITO_CLIENT_ID", "")
    if not client_id:
        return json_response(500, {"error": "COGNITO_CLIENT_ID is not configured"})

    try:
        body = parse_json_body(event)
    except ValueError as exc:
        return json_response(400, {"error": str(exc)})

    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        return json_response(400, {"error": "email and password are required"})

    try:
        result = boto3.client("cognito-idp").initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=client_id,
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            return json_response(401, {"error": "Incorrect email or password"})
        return json_response(500, {"error": str(exc)})

    tokens = result["AuthenticationResult"]
    return json_response(200, {
        "id_token": tokens["IdToken"],
        "refresh_token": tokens.get("RefreshToken"),
        "expires_in": tokens.get("ExpiresIn", 3600),
    })
