#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from xml.sax.saxutils import escape

BASE = "https://www.services.rcmp-grc.gc.ca/missing-disparus/results-resultats.jsf"
LANG = "fr"

# Flux combiné
Q_LIST = ["MPA", "MPC", "UR"]

# Ajustables
MAX_LINKS_PER_LIST = 120      # liens candidats par catégorie
MAX_RSS_ITEMS_TOTAL = 60      # items max dans le RSS final
SLEEP_SECONDS = 1.0           # pause entre requêtes (politesse)

OUT_PATH = "docs/feed.xml"    # GitHub Pages servira le contenu de /docs

def fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (RSS generator)",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def extract_case_links(results_html: str, results_url: str):
    soup = BeautifulSoup(results_html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        abs_url = urljoin(results_url, href)

        # Heuristique: liens .jsf dans /missing-disparus/ autres que results-resultats.jsf
        if "services.rcmp-grc.gc.ca" not in abs_url:
            continue
        if "/missing-disparus/" not in abs_url:
            continue
        if "results-resultats.jsf" in abs_url:
            continue
        if ".jsf" not in abs_url:
            continue

        title = a.get_text(" ", strip=True)
        if len(title) < 3:
            continue

        links.append((abs_url, title))

    # dédup
    seen = set()
    uniq = []
    for u, t in links:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, t))

    return uniq[:MAX_LINKS_PER_LIST]

def is_quebec_case(case_html: str) -> bool:
    # Filtre simple: chercher Québec / Quebec / QC dans le texte
    txt = BeautifulSoup(case_html, "html.parser").get_text(" ", strip=True).lower()
    return ("québec" in txt) or ("quebec" in txt) or (" qc " in f" {txt} ")

def build_rss(items, source_home: str) -> str:
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape('Disparus-Canada — Québec (FR) — Flux combiné')}</title>",
        f"<link>{escape(source_home)}</link>",
        f"<description>{escape('Flux RSS combiné (MPA + MPC + UR), filtré sur le Québec, généré depuis les pages de résultats')}</description>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]

    for it in items:
        parts.append("<item>")
        parts.append(f"<title>{escape(it['title'])}</title>")
        parts.append(f"<link>{escape(it['link'])}</link>")
        parts.append(f"<guid isPermaLink=\"false\">{it['guid']}</guid>")
        parts.append(f"<category>{escape(it['category'])}</category>")
        parts.append("</item>")

    parts += ["</channel>", "</rss>"]
    return "\n".join(parts)

def main():
    all_items = []
    seen_links = set()

    source_home = f"{BASE}?lang={LANG}"

    for q in Q_LIST:
        results_url = f"{BASE}?q={q}&lang={LANG}"
        results_html = fetch(results_url)
        candidates = extract_case_links(results_html, results_url)

        for url, title in candidates:
            if len(all_items) >= MAX_RSS_ITEMS_TOTAL:
                break
            if url in seen_links:
                continue

            time.sleep(SLEEP_SECONDS)

            try:
                case_html = fetch(url)
            except Exception:
                continue

            if is_quebec_case(case_html):
                guid = hashlib.sha1(url.encode("utf-8")).hexdigest()
                all_items.append({
                    "title": f"[{q}] {title}",
                    "link": url,
                    "guid": guid,
                    "category": q
                })
                seen_links.add(url)

    rss = build_rss(all_items, source_home)

    # écrire le fichier dans /docs
    import os
    os.makedirs("docs", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"OK: {len(all_items)} items -> {OUT_PATH}")

if __name__ == "__main__":
    main()
