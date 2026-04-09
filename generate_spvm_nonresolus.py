#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://spvm.qc.ca/fr/PersonnesRecherchees/NonResolus"
OUT_FILE = "docs/spvm-nonresolus.xml"
MAX_ITEMS = 50

def fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (RSS generator)",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def extract_cases(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Heuristique: les fiches individuelles semblent être sous /NonResolus/<id> (ex: /NonResolus/16) [3](https://spvm.qc.ca/fr/PersonnesRecherchees/NonResolus/16)
    # On récupère tous les liens qui matchent ce pattern.
    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        abs_url = urljoin(SOURCE_URL, href)

        if "spvm.qc.ca" not in abs_url:
            continue

        if not re.search(r"/fr/PersonnesRecherchees/NonResolus/\d+$", abs_url):
            continue

        title = a.get_text(" ", strip=True)
        if not title:
            title = "Meurtre non résolu (SPVM)"

        if abs_url in seen:
            continue
        seen.add(abs_url)

        guid = hashlib.sha1(abs_url.encode("utf-8")).hexdigest()
        items.append({"title": title, "link": abs_url, "guid": guid})

    return items[:MAX_ITEMS]

def build_rss(items):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape('SPVM — Meurtres non résolus (cas récemment publiés)')}</title>",
        f"<link>{escape(SOURCE_URL)}</link>",
        f"<description>{escape('Flux RSS généré à partir de la page Meurtres non résolus du SPVM (titres + liens).')}</description>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]

    for it in items:
        parts.append("<item>")
        parts.append(f"<title>{escape(it['title'])}</title>")
        parts.append(f"<link>{escape(it['link'])}</link>")
        parts.append(f"<guid isPermaLink=\"false\">{it['guid']}</guid>")
        parts.append("</item>")

    parts += ["</channel>", "</rss>"]
    return "\n".join(parts)

def main():
    os.makedirs("docs", exist_ok=True)

    html = fetch(SOURCE_URL)
    items = extract_cases(html)

    rss = build_rss(items)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"OK: {len(items)} items -> {OUT_FILE}")

if __name__ == "__main__":
    main()
