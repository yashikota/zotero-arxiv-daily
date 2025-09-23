from __future__ import annotations

from typing import Iterable

import requests
from loguru import logger

from paper import ArxivPaper

_MAX_EMBEDS_PER_REQUEST = 10
_MAX_TITLE = 256
_MAX_DESCRIPTION = 2048
_MAX_FIELD_VALUE = 1024
_DEFAULT_COLOR = 0x5865F2


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def _author_string(paper: ArxivPaper) -> str:
    names = [getattr(author, "name", str(author)) for author in paper.authors]
    author_line = ", ".join(names) if names else "Unknown"
    return _truncate(author_line, _MAX_FIELD_VALUE)


def _relevance_string(paper: ArxivPaper) -> str:
    score = paper.score
    if score is None:
        return "Not ranked"
    return f"{score:.2f}/10"


def _link_block(paper: ArxivPaper) -> str:
    links: list[str] = [
        f"[Abstract](https://arxiv.org/abs/{paper.arxiv_id})", 
        f"[PDF]({paper.pdf_url})",
        f"[AlphaXiv](https://www.alphaxiv.org/overview/{paper.arxiv_id_with_version})"
    ]
    if paper.code_url:
        links.append(f"[Code]({paper.code_url})")
    return " | ".join(links)


def _affiliations_block(paper: ArxivPaper) -> str | None:
    if not paper.affiliations:
        return None
    values = ", ".join(paper.affiliations[:5])
    if len(paper.affiliations) > 5:
        values += ", ..."
    return _truncate(values, _MAX_FIELD_VALUE)


def _paper_to_embed(paper: ArxivPaper) -> dict:
    summary = paper.tldr if paper.tldr else paper.summary
    embed = {
        "title": _truncate(paper.title, _MAX_TITLE),
        "url": f"https://arxiv.org/abs/{paper.arxiv_id}",
        "description": _truncate(summary, _MAX_DESCRIPTION),
        "color": _DEFAULT_COLOR,
        "fields": [
            {
                "name": "Authors",
                "value": _author_string(paper),
                "inline": False,
            },
            {
                "name": "Relevance",
                "value": _relevance_string(paper),
                "inline": True,
            },
            {
                "name": "Links",
                "value": _link_block(paper),
                "inline": True,
            },
        ],
    }
    affiliations = _affiliations_block(paper)
    if affiliations:
        embed["fields"].append(
            {
                "name": "Affiliations",
                "value": affiliations,
                "inline": False,
            }
        )
    return embed


def _batched(seq: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(seq), size):
        yield seq[start : start + size]


def notify_discord(papers: list[ArxivPaper], webhook_url: str) -> None:
    if not webhook_url:
        return

    def _post(payload: dict) -> None:
        data = {"allowed_mentions": {"parse": []}}
        data.update(payload)
        try:
            response = requests.post(
                webhook_url,
                json=data,
                timeout=10,
            )
        except requests.RequestException as exc:
            logger.warning("Failed to reach Discord webhook: {}", exc)
            return
        if response.status_code >= 400:
            logger.warning(
                "Discord webhook returned {}: {}",
                response.status_code,
                response.text[:300],
            )

    if not papers:
        _post({"content": "No new arXiv papers today.\nSee you tomorrow!"})
        return

    embeds = [_paper_to_embed(paper) for paper in papers]
    for chunk in _batched(embeds, _MAX_EMBEDS_PER_REQUEST):
        _post({"embeds": chunk})

    logger.info("Sent {} paper(s) to Discord webhook.", len(papers))
