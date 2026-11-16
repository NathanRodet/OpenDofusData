"""The administration route: revoke a key (the only thing the server does for the administrator)."""

import logging

from fastapi import FastAPI

from keyserver.revocations import RevocationStore
from keyserver.schemas import KeyIdRequest

logger = logging.getLogger(__name__)

REVOKE_PATH = "/admin/revoke"


def register_admin_routes(app: FastAPI, revocations: RevocationStore) -> None:
    """Add `POST /admin/revoke`: idempotent, answers 200 even for an identifier that was never issued."""

    @app.post(REVOKE_PATH)
    def revoke(request: KeyIdRequest) -> dict[str, bool]:
        revocations.revoke(request.key_id)
        logger.info("clé révoquée : %s", request.key_id)
        return {"revoked": True}
