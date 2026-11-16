"""Shared test constants and helpers of the server suite."""

SECRET = "A" * 43
OTHER_SECRET = "B" * 43
KEY_ID = "AAAAAAAAAAA"


def authorization(key: str) -> dict[str, str]:
    """The Authorization header carrying this key."""
    return {"Authorization": f"Bearer {key}"}
