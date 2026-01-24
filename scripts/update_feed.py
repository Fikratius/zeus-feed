#!/usr/bin/env python3
import json
import os
import re
import textwrap
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional

import feedparser
import requests

FEEDS = [
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source": "BBC World",
        "lang": "en",
        "bias_score": 42,
        "left_right_index": -5,
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "source": "NYTimes World",
        "lang": "en",
        "bias_score": 55,
        "left_right_index": -18,
    },
    {
        "url": "https://www.theguardian.com/world/rss",
        "source": "The Guardian",
        "lang": "en",
        "bias_score": 60,
        "left_right_index": -28,
    },
    {
        "url": "https://meduza.io/rss/all",
        "source": "Meduza",
        "lang": "ru",
        "bias_score": 58,
        "left_right_index": -22,
    },
    {
        "url": "https://tass.ru/rss/v2.xml",
        "source": "ТАСС",
        "lang": "ru",
        "bias_score": 62,
        "left_right_index": 12,
    },
]

TAG_KEYWORDS = {
    "politics": ["election", "president", "government", "парламент", "выбор", "президент", "правительство"],
    "economy": ["economy", "inflation", "market", "bank", "эконом", "инфля", "рынок", "банк"],
    "conflict": ["war", "strike", "attack", "conflict", "войн", "удар", "атак", "конфликт"],
    "tech": ["tech", "ai", "software", "кибер", "техн", "ии"],
    "climate": ["climate", "weather", "storm", "климат", "погод", "шторм"],
    "health": ["health", "hospital", "disease", "здоров", "болезн"],
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4o-mini"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def shorten(text: str, max_len: int = 280) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def extract_tags(text: str) -> List[str]:
    text_l = text.lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(k in text_l for k in keywords):
            tags.append(tag)
    return tags[:4]


def heuristic_summary(title: str, excerpt: str, lang: str) -> Dict[str, str]:
    if excerpt:
        first_sentence = excerpt.split(".")[0].strip()
    else:
        first_sentence = title
    recap = shorten(first_sentence or title, 220)
    if lang == "en":
        main_idea = shorten(title, 140)
    else:
        main_idea = shorten(title, 140)
    return {
        "recap": recap,
        "main_idea": main_idea,
    }


def llm_summary(title: str, excerpt: str, lang: str, api_key: str) -> Optional[Dict[str, Any]]:
    system = (
        "You are a neutral summarizer. Produce a concise, neutral recap and a main idea. "
        "Return JSON with keys: recap, main_idea, tags (array of 1-4 short tags). "
        "Do not add opinions."
    )
    prompt = textwrap.dedent(
        f"""
        Language: {lang}
        Title: {title}
        Excerpt: {excerpt}
        """
    ).strip()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not parsed.get("recap"):
            return None
        return parsed
    except Exception:
        return None


def score_bias(text: str, base_bias: int) -> int:
    text_l = text.lower()
    bump = 0
    if any(k in text_l for k in ["outrage", "shocking", "controvers", "скандал", "шок", "крах"]):
        bump += 10
    if any(k in text_l for k in ["analysis", "report", "официаль", "доклад", "statement", "заявлен"]):
        bump -= 6
    return max(0, min(100, base_bias + bump))


def parse_feed(feed_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed = feedparser.parse(feed_cfg["url"])
    items = []
    for entry in parsed.entries[:15]:
        title = clean_html(entry.get("title", ""))
        summary = clean_html(entry.get("summary", ""))
        excerpt = shorten(summary, 300)
        url = entry.get("link") or ""
        published = entry.get("published") or entry.get("updated") or ""
        items.append({
            "title": title,
            "excerpt": excerpt,
            "url": url,
            "published_at": published,
        })
    return items


def build_items() -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    all_items: List[Dict[str, Any]] = []
    seen = set()

    for feed in FEEDS:
        entries = parse_feed(feed)
        for entry in entries:
            if not entry["title"]:
                continue
            key = entry["url"] or entry["title"]
            if key in seen:
                continue
            seen.add(key)

            lang = feed["lang"]
            if api_key:
                llm = llm_summary(entry["title"], entry["excerpt"], lang, api_key)
            else:
                llm = None

            if llm:
                recap = llm.get("recap") or entry["excerpt"] or entry["title"]
                main_idea = llm.get("main_idea") or entry["title"]
                tags = llm.get("tags") or extract_tags(f"{entry['title']} {entry['excerpt']}")
                confidence = "llm"
            else:
                summary = heuristic_summary(entry["title"], entry["excerpt"], lang)
                recap = summary["recap"]
                main_idea = summary["main_idea"]
                tags = extract_tags(f"{entry['title']} {entry['excerpt']}")
                confidence = "heuristic"

            bias_score = score_bias(entry["title"], feed["bias_score"])
            all_items.append({
                "title_original": entry["title"],
                "title_neutral": entry["title"],
                "excerpt": entry["excerpt"],
                "recap_neutral": recap,
                "main_idea": main_idea,
                "tags": tags,
                "source": feed["source"],
                "published_at": entry["published_at"],
                "url": entry["url"],
                "lang": lang,
                "bias_score": bias_score,
                "left_right_index": feed["left_right_index"],
                "confidence": confidence,
            })

    all_items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return all_items


def main() -> None:
    feed = {
        "last_updated": now_iso(),
        "items": build_items(),
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/feed.json", "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
