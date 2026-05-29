from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from typing import NotRequired, TypedDict

import httpx
from markdown_it import MarkdownIt

HEX2077_SEARCH_INDEX_URL = "https://hex2077.dev/search-index-zh-CN.json"
_INDEX_TTL = timedelta(hours=24)

_CATEGORY_KEY_MAP = [
    ("产品", "product"),
    ("研究", "research"),
    ("行业", "industry"),
    ("开源", "opensource"),
    ("社媒", "social"),
]

_IGNORED_SECTION_KEYWORDS = ["收听", "语音", "摘要", "自荐", "今日"]

_IMAGE_DOMAINS = (
    "raw.githubusercontent.com",
    "source.hubtoday",
    "source.hex2077",
    ".avif",
    ".png",
    ".jpg",
    ".webp",
    ".mp4",
    ".gif",
)


class SearchIndexEntry(TypedDict):
    slug: str
    title: str
    description: NotRequired[str]
    content: str
    type: NotRequired[str]


def _category_key(category: str) -> str:
    for keyword, key in _CATEGORY_KEY_MAP:
        if keyword in category:
            return key
    return "other"


def _is_ignored_section(heading: str) -> bool:
    return any(kw in heading for kw in _IGNORED_SECTION_KEYWORDS)


def _is_image_url(url: str) -> bool:
    return any(s in url for s in _IMAGE_DOMAINS)


def _extract_inline_links(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)


def _extract_best_url(text: str) -> str:
    for _, url in _extract_inline_links(text):
        if not _is_image_url(url):
            return url.strip()
    return ""


def _strip_markup(text: str) -> str:
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_item(raw: str) -> dict[str, str] | None:
    url = _extract_best_url(raw)
    if not url:
        return None

    title_m = re.search(r"\*\*([^*]{4,80})\*\*", raw)
    if title_m:
        title = _strip_markup(title_m.group(1)).strip("·— \t")
    else:
        title = _strip_markup(raw)[:50]

    summary = _strip_markup(raw)
    if len(summary) > 200:
        summary = summary[:200].rstrip() + "…"

    source = ""
    for link_text, link_url in _extract_inline_links(raw):
        if _is_image_url(link_url):
            continue
        if link_text in ("更多详情", "跳转链接", "项目地址", "论文地址", "访问网页版"):
            dm = re.search(r"https?://(?:www\.)?([^/]+)", link_url)
            source = dm.group(1).split(".")[0] if dm else ""
        else:
            # Strip trailing "(AI资讯)" style annotations
            source = re.sub(r"\s*[\(（][^)）]*[\)）]\s*$", "", link_text).strip()
        break

    return {"title": title, "summary": summary, "url": url, "source": source}


def parse_markdown(content: str) -> list[dict]:
    content = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, flags=re.DOTALL)

    md = MarkdownIt()
    tokens = md.parse(content)

    groups: list[dict] = []
    in_h3 = False
    collect = False
    in_item = False
    item_parts: list[str] = []

    for t in tokens:
        if t.type == "heading_open":
            in_h3 = t.tag == "h3"
            if t.tag != "h3":
                collect = False
            continue

        if t.type == "inline" and in_h3:
            in_h3 = False
            heading = _strip_markup(t.content)
            if not _is_ignored_section(heading):
                collect = True
                groups.append(
                    {"category": heading, "category_key": _category_key(heading), "items": []}
                )
            else:
                collect = False
            continue

        if not collect:
            continue

        if t.type == "list_item_open":
            item_parts = []
            in_item = True
        elif t.type == "list_item_close":
            in_item = False
            if item_parts and groups:
                item = _parse_item("\n".join(item_parts))
                if item:
                    groups[-1]["items"].append(item)
            item_parts = []
        elif in_item and t.type == "inline":
            item_parts.append(t.content)

    return [g for g in groups if g["items"]]


class AiNewsFetchError(Exception):
    pass


class AiNewsFetcher:
    def __init__(self) -> None:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "moyu-hotlist/1.0",
        }
        self._client = httpx.AsyncClient(headers=headers, timeout=15.0)
        self._index_cache: list[SearchIndexEntry] | None = None
        self._index_fetched_at: datetime | None = None

    async def _fetch_index(self, *, force_refresh: bool = False) -> list[SearchIndexEntry]:
        now = datetime.now(UTC)
        if (
            not force_refresh
            and self._index_cache is not None
            and self._index_fetched_at is not None
            and now - self._index_fetched_at < _INDEX_TTL
        ):
            return self._index_cache

        try:
            resp = await self._client.get(HEX2077_SEARCH_INDEX_URL)
        except httpx.RequestError as exc:
            raise AiNewsFetchError(f"network error: {exc}") from exc

        if resp.status_code != 200:
            raise AiNewsFetchError(f"hex2077 search index returned {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise AiNewsFetchError("invalid search index json") from exc

        if not isinstance(data, list):
            raise AiNewsFetchError("search index payload is not a list")

        entries: list[SearchIndexEntry] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            slug = item.get("slug")
            title = item.get("title")
            content = item.get("content")
            if (
                not isinstance(slug, str)
                or not isinstance(title, str)
                or not isinstance(content, str)
            ):
                continue
            entries.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": item.get("description", ""),
                    "content": content,
                    "type": item.get("type", ""),
                }
            )

        self._index_cache = entries
        self._index_fetched_at = now
        return entries

    async def _find_entry(
        self, date: str, *, force_refresh: bool = False
    ) -> SearchIndexEntry | None:
        slug = f"{date[:7]}/{date}"
        for item in await self._fetch_index(force_refresh=force_refresh):
            if item["slug"] == slug and item.get("type", "") == "docs":
                return item
        return None

    async def fetch_date(self, date: str) -> list[dict]:
        """Fetch and parse AI news for a given date (YYYY-MM-DD).

        Returns empty list when the date has no data.
        Raises AiNewsFetchError on network/API errors.
        """
        entry = await self._find_entry(date)
        if entry is None and date >= date_type.today().isoformat():
            entry = await self._find_entry(date, force_refresh=True)

        if entry is None:
            return []

        return parse_markdown(entry["content"])

    async def aclose(self) -> None:
        await self._client.aclose()
