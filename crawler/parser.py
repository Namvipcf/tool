"""Parser HTML cho MQL5 Code Base.

Selector duoc xac dinh tu HTML thuc te cua mql5.com (thang 8/2026):

- Trang danh sach `https://www.mql5.com/en/code/mt5/experts[/best][/pageN]`
  moi item la `div.code-tile`, ten + link o `div.title > a[href="/en/code/<id>"]`,
  loai o `span.codeIcon[title]`, mo ta o the `p`.
- Trang chi tiet `https://www.mql5.com/en/code/<id>`
  tac gia o `div.author-line a[href*="/users/"]`, bang thong tin o `dl.code-table`
  (Views / Rating / Published), file dinh kem o `#codeAttachments a.attach-item__link`,
  link ZIP o `a[href$=".zip"][href*="/code/download/"]`.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from models.source import Attachment, SourceRecord, SourceType

BASE = "https://www.mql5.com"
SOURCE_EXTENSIONS = {"mq5", "mq4", "mqh"}
_ID_RE = re.compile(r"/code/(\d+)")


def _abs(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE + href


def parse_listing(html: str, platform: str = "mt5") -> list[SourceRecord]:
    """Parse mot trang danh sach Code Base thanh danh sach SourceRecord."""
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceRecord] = []
    for tile in soup.select("div.code-tile"):
        link = tile.select_one("div.title a[href]")
        if not link:
            continue
        match = _ID_RE.search(link.get("href", ""))
        if not match:
            continue
        icon = tile.select_one("span.codeIcon")
        desc = tile.find("p")
        records.append(
            SourceRecord(
                source_id=match.group(1),
                name=link.get_text(strip=True),
                source_url=_abs(link["href"]),
                type=SourceType.from_site_label(icon.get("title", "") if icon else ""),
                description=desc.get_text(" ", strip=True) if desc else "",
                platform=platform,
            )
        )
    return records


def has_next_page(html: str) -> bool:
    """Con trang tiep theo hay khong (dua vao paginator)."""
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select("div.paginatorEx a[href*='/page'], span.paginatorEx a[href*='/page']"))


def parse_detail(html: str, record: SourceRecord) -> SourceRecord:
    """Bo sung metadata + attachment tu trang chi tiet vao `record`."""
    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("h1")
    if title and not record.name:
        record.name = re.sub(
            r"\s+-\s+(expert|indicator|script|library).*$",
            "",
            title.get_text(strip=True),
            flags=re.IGNORECASE,
        )

    author = soup.select_one("div.author-line a[href*='/users/']")
    if author:
        record.author = author.get_text(strip=True)

    table = soup.select_one("dl.code-table")
    if table:
        keys = [dt.get_text(strip=True).rstrip(":").lower() for dt in table.find_all("dt")]
        values = table.find_all("dd")
        for key, value in zip(keys, values):
            if key == "views":
                digits = re.sub(r"\D", "", value.get_text())
                record.views = int(digits) if digits else None
        rating = table.select_one("div.g-rating")
        if rating:
            m = re.search(r"g-rating_v(\d+)", " ".join(rating.get("class", [])))
            if m:
                record.rating = int(m.group(1)) / 10.0
        votes = table.select_one("span.g-rating__info")
        if votes:
            digits = re.sub(r"\D", "", votes.get_text())
            record.votes = int(digits) if digits else None
        published = table.select_one("time[datetime]")
        if published:
            record.published = published["datetime"]

    if not record.description:
        og = soup.find("meta", attrs={"property": "og:description"})
        if og:
            record.description = og.get("content", "")

    if record.type is SourceType.UNKNOWN:
        tag = soup.find("meta", attrs={"property": "article:tag"})
        if tag:
            record.type = SourceType.from_site_label(tag.get("content", ""))

    attachments: list[Attachment] = []
    for link in soup.select("#codeAttachments a.attach-item__link[href]"):
        size_el = link.find_next("span", class_="attachSize")
        attachments.append(
            Attachment(
                name=link.get("title") or link.get_text(strip=True),
                url=_abs(link["href"]),
                size=(size_el.get_text(strip=True).strip("()") if size_el else ""),
            )
        )
    record.attachments = attachments

    zip_link = soup.select_one("a[href*='/code/download/'][href$='.zip']")
    if zip_link:
        record.file_url = _abs(zip_link["href"])
    elif attachments:
        record.file_url = attachments[0].url

    source_att = next((a for a in attachments if a.extension in SOURCE_EXTENSIONS), None)
    if source_att:
        record.filename = source_att.name
        record.extension = source_att.extension
    return record


def matches_keywords(record: SourceRecord, keywords: list[str]) -> bool:
    """Loc theo keyword (khong phan biet hoa thuong, OR giua cac keyword)."""
    if not keywords:
        return True
    haystack = f"{record.name} {record.description} {record.author}".lower()
    return any(k.strip().lower() in haystack for k in keywords if k.strip())
