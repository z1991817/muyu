from __future__ import annotations

from app.models.common import APIModel


class OnlineResponse(APIModel):
    visitors: int | None = None
    stale: bool = False
    updated_at: str
