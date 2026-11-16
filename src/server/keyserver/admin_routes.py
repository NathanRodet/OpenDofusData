"""The administration route: revoke a key, and delete its readings when asked."""

import logging

from fastapi import FastAPI

from keyserver.readings_store import ReadingStore
from keyserver.revocations import RevocationStore
from keyserver.schemas import KeyIdRequest

logger = logging.getLogger(__name__)

REVOKE_PATH = "/admin/revoke"


def register_admin_routes(app: FastAPI, revocations: RevocationStore, readings: ReadingStore) -> None:
    """Add `POST /admin/revoke`: idempotent, answers 200 even for an identifier that was never issued.

    The key is revoked first (it stops working at once), then its readings are deleted if `purge` is true.
    """

    @app.post(REVOKE_PATH)
    def revoke(request: KeyIdRequest) -> dict[str, object]:
        revocations.revoke(request.key_id)
        purged = readings.purge_key(request.key_id) if request.purge else 0
        logger.info("clé révoquée : %s (relevés supprimés : %d)", request.key_id, purged)
        return {"revoked": True, "purged": purged}
