"""
detector.py — deterministic SEO issue detection from a Screaming Frog internal_all.csv.

Implements every rule in rulebook.md. Detection is plain Python on purpose — the model
is for judgment (rewriting titles, choosing redirect targets), not for counting rows.
"""

from __future__ import annotations
import csv
import os
from collections import defaultdict


def load_rows(export_dir: str) -> list[dict]:
    path = os.path.join(export_dir, "internal_all.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def _float(v, default=0.0):
    try:
        return float(str(v).strip())
    except Exception:
        return default


def is_html(r):   return "text/html" in (r.get("Content Type", "") or "").lower()
def is_200(r):    return _int(r.get("Status Code")) == 200
def indexable(r): return (r.get("Indexability", "") or "").strip().lower() == "indexable"


def detect(rows: list[dict]) -> list[dict]:
    """Return a list of issue dicts: {type, severity, affected_urls, count, explanation}.
    Implements the full rulebook — all 17 issue types."""
    issues = []

    def add(t, sev, urls, explanation):
        urls = sorted(set(urls))
        if urls:
            issues.append({
                "type": t,
                "severity": sev,
                "affected_urls": urls,
                "count": len(urls),
                "explanation": explanation,
            })

    # Pre-filtered sets (per rulebook pre-filters)
    html       = [r for r in rows if is_html(r)]
    all200     = [r for r in html if is_200(r)]
    idx200     = [r for r in html if is_200(r) and indexable(r)]   # indexable 200 HTML pages

    # ── Titles ────────────────────────────────────────────────────────────────

    # missing_title: Title 1 empty, indexable 200 page
    add("missing_title", "High",
        [r["Address"] for r in idx200 if not (r.get("Title 1", "") or "").strip()],
        "Indexable pages with no title tag.")

    # duplicate_title: same Title 1 on 2+ indexable URLs
    by_title: dict[str, list] = defaultdict(list)
    for r in idx200:
        t = (r.get("Title 1", "") or "").strip()
        if t:
            by_title[t].append(r["Address"])
    dup_t = [u for urls in by_title.values() if len(urls) > 1 for u in urls]
    add("duplicate_title", "High", dup_t, "Pages sharing an identical title tag.")

    # title_too_long: Pixel Width > 561 OR Length > 60
    add("title_too_long", "Medium",
        [r["Address"] for r in idx200
         if (r.get("Title 1", "") or "").strip()
         and (_int(r.get("Title 1 Pixel Width")) > 561
              or _int(r.get("Title 1 Length")) > 60)],
        "Titles likely truncated in search results (> 60 chars or > 561px).")

    # title_too_short: Length < 30 and NOT empty
    add("title_too_short", "Low",
        [r["Address"] for r in idx200
         if (r.get("Title 1", "") or "").strip()
         and _int(r.get("Title 1 Length")) < 30],
        "Indexable pages with titles that are too short (< 30 chars).")

    # ── Meta Descriptions ─────────────────────────────────────────────────────

    # missing_meta_description: Meta Description 1 empty, indexable 200 page
    add("missing_meta_description", "Medium",
        [r["Address"] for r in idx200 if not (r.get("Meta Description 1", "") or "").strip()],
        "Indexable pages missing a meta description.")

    # duplicate_meta_description: same meta on 2+ indexable URLs
    by_meta: dict[str, list] = defaultdict(list)
    for r in idx200:
        m = (r.get("Meta Description 1", "") or "").strip()
        if m:
            by_meta[m].append(r["Address"])
    dup_m = [u for urls in by_meta.values() if len(urls) > 1 for u in urls]
    add("duplicate_meta_description", "Medium", dup_m,
        "Pages sharing an identical meta description.")

    # meta_description_too_long: Length > 155
    add("meta_description_too_long", "Low",
        [r["Address"] for r in idx200
         if (r.get("Meta Description 1", "") or "").strip()
         and _int(r.get("Meta Description 1 Length")) > 155],
        "Meta descriptions likely truncated in search results (> 155 chars).")

    # ── H1s ───────────────────────────────────────────────────────────────────

    # missing_h1: H1-1 empty on a 200 page (all 200, not just indexable)
    add("missing_h1", "Medium",
        [r["Address"] for r in all200 if not (r.get("H1-1", "") or "").strip()],
        "200 pages missing an H1 tag.")

    # duplicate_h1: same H1-1 on 2+ indexable URLs
    by_h1: dict[str, list] = defaultdict(list)
    for r in idx200:
        h = (r.get("H1-1", "") or "").strip()
        if h:
            by_h1[h].append(r["Address"])
    dup_h = [u for urls in by_h1.values() if len(urls) > 1 for u in urls]
    add("duplicate_h1", "Low", dup_h, "Indexable pages sharing an identical H1.")

    # ── Response Codes ────────────────────────────────────────────────────────

    add("broken_link", "High",
        [r["Address"] for r in rows if 400 <= _int(r.get("Status Code")) <= 499],
        "URLs returning a client error (4xx).")

    add("server_error", "High",
        [r["Address"] for r in rows if 500 <= _int(r.get("Status Code")) <= 599],
        "URLs returning a server error (5xx).")

    add("redirect", "Medium",
        [r["Address"] for r in rows if 300 <= _int(r.get("Status Code")) <= 399],
        "URLs that redirect (3xx).")

    # redirect_chain: a redirect whose Redirect URL target is also a redirecting URL
    # Build map: address -> redirect_url for all 3xx rows
    redirect_map: dict[str, str] = {}
    for r in rows:
        sc = _int(r.get("Status Code"))
        if 300 <= sc <= 399:
            target = (r.get("Redirect URL", "") or "").strip()
            if target:
                redirect_map[r["Address"]] = target

    # A chain exists when the target of a redirect is itself a key in redirect_map
    chain_urls = [addr for addr, target in redirect_map.items() if target in redirect_map]

    # Detect loops (target eventually redirects back to origin)
    loop_urls = []
    for start in redirect_map:
        visited = set()
        cur = start
        while cur in redirect_map:
            if cur in visited:
                # We're in a loop; mark the start URL
                loop_urls.append(start)
                break
            visited.add(cur)
            cur = redirect_map[cur]

    all_chain = sorted(set(chain_urls + loop_urls))
    add("redirect_chain", "High", all_chain,
        "Redirect whose target is also a redirect (chain or loop).")

    # ── Content ───────────────────────────────────────────────────────────────

    # thin_content: Word Count < 200 on an indexable page (indexable 200 HTML)
    add("thin_content", "Low",
        [r["Address"] for r in idx200 if _int(r.get("Word Count")) < 200],
        "Indexable pages with a very low word count (< 200 words).")

    # ── Links / Architecture ──────────────────────────────────────────────────

    # orphan_page: Inlinks = 0 on indexable 200 page
    add("orphan_page", "Medium",
        [r["Address"] for r in idx200 if _int(r.get("Inlinks")) == 0],
        "Indexable pages with zero internal inlinks (orphan pages).")

    # non_indexable_but_linked: Non-Indexable AND Inlinks > 0
    add("non_indexable_but_linked", "Medium",
        [r["Address"] for r in rows
         if (r.get("Indexability", "") or "").strip().lower() == "non-indexable"
         and _int(r.get("Inlinks")) > 0],
        "Non-indexable pages that still receive internal links.")

    # slow_page: Response Time > 1.0 second
    add("slow_page", "Low",
        [r["Address"] for r in rows if _float(r.get("Response Time")) > 1.0],
        "Pages with a response time greater than 1 second.")

    return issues


def summarize(issues: list[dict]) -> dict:
    """Correct summary: total_issues = sum of all affected URL counts, not number of issue types."""
    by_sev: dict[str, int] = defaultdict(int)
    total = 0
    for i in issues:
        count = i["count"]
        by_sev[i["severity"]] += count
        total += count
    return {
        "total_issues": total,
        "by_severity": {
            "High":   by_sev["High"],
            "Medium": by_sev["Medium"],
            "Low":    by_sev["Low"],
        },
    }


if __name__ == "__main__":
    import sys, json
    d = sys.argv[1] if len(sys.argv) > 1 else "../sample-export"
    rows = load_rows(d)
    iss = detect(rows)
    print(f"Loaded {len(rows)} rows, detected {len(iss)} issue types.")
    print(json.dumps(summarize(iss), indent=2))
    for i in iss:
        print(f"  [{i['severity']:<6}] {i['type']:<30} x{i['count']}")
