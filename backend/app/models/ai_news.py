from __future__ import annotations

from app.models.common import APIModel


class AiNewsItem(APIModel):
    title: str
    summary: str
    url: str
    source: str


class AiNewsGroup(APIModel):
    category: str
    category_key: str
    items: list[AiNewsItem]


class AiNewsResponse(APIModel):
    date: str
    groups: list[AiNewsGroup]
    stale: bool
    updated_at: str
