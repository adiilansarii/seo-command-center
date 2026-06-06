"""
server.py — local MCP server + live dashboard host (one process, two faces).

  1. MCP tools over stdio  -> Claude Code calls: seo_load, seo_detect, seo_fix, seo_report, seo_export
  2. HTTP + SSE on localhost:7700 -> the live cockpit that fills as issues are found.

Needs the MCP SDK: `pip install mcp`. Without it the dashboard still runs so run.py works.
"""
from __future__ import annotations
import json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASH_DIR = os.path.join(ROOT, "dashboard")
OUT_DIR = os.path.join(ROOT, "outputs")
PORT = int(os.environ.get("SEO_PORT", "7700"))
MODEL = os.environ.get("RADAR_MODEL", "qwen3.5:9b")

import sys
sys.path.insert(0, ROOT)
from seo import detector  # noqa: E402

RUN: dict = {"site": None, "urls": 0, "issues": [], "summary": None, "status": "idle"}
_subs: list[queue.Queue] = []
_lock = threading.Lock()


def _emit(event, data):
    payload = json.dumps({"event": event, "data": data})
    with _lock:
        for q in list(_subs):
            try: q.put_nowait(payload)
            except Exception: pass


# ── pipeline tools (importable by run.py without MCP) ──────────────────────

def seo_load(export_dir: str) -> dict:
    rows = detector.load_rows(export_dir)
    RUN.update({
        "rows": rows, "urls": len(rows), "issues": [], "summary": None,
        "site": _guess_site(rows), "status": "running",
        "export_dir": export_dir,
    })
    _emit("loaded", {"site": RUN["site"], "urls": len(rows)})
    return {"urls": len(rows), "site": RUN["site"]}


def _guess_site(rows):
    if not rows: return "unknown"
    addr = rows[0].get("Address", "")
    try:
        return urlparse(addr).netloc or "unknown"
    except Exception:
        return "unknown"


def seo_detect() -> dict:
    issues = detector.detect(RUN.get("rows", []))
    RUN["issues"] = issues
    RUN["summary"] = detector.summarize(issues)
    for i in issues:
        _emit("issue", i)
    _emit("summary", RUN["summary"])
    return {"detected": len(issues), "summary": RUN["summary"]}


def _report_obj() -> dict:
    return {
        "site": RUN["site"],
        "urls_crawled": RUN["urls"],
        "summary": RUN["summary"] or {"total_issues": 0, "by_severity": {}},
        "issues": RUN["issues"],
        "fixes": RUN.get("fixes", {"titles": [], "redirect_map": []}),
        "recommendations": RUN.get("recommendations", []),
        "run_meta": {
            "model": MODEL,
            "model_calls": RUN.get("model_calls", 0),
            "duration_sec": RUN.get("duration_sec", 0),
        },
    }


def seo_set_fixes(titles=None, redirect_map=None) -> dict:
    RUN["fixes"] = {"titles": titles or [], "redirect_map": redirect_map or []}
    _emit("fixes", RUN["fixes"])
    return {"titles": len(titles or []), "redirects": len(redirect_map or [])}


def seo_fix() -> dict:
    """Generate title/meta rewrites and a redirect map for broken links.
    Rules:
    - Title must be 30–60 chars. Re-truncate / expand if outside range.
    - Meta must be ≤ 155 chars.
    - For each 4xx URL, point to the site homepage as a safe fallback redirect target.
    """
    rows_map = {r["Address"]: r for r in RUN.get("rows", [])}
    site = RUN.get("site") or "Website"
    site_home = f"https://{site}/"

    # ── Title / meta fixes ──────────────────────────────────────────────────
    title_fixes = []
    seen_urls: set = set()

    for issue in RUN.get("issues", []):
        itype = issue["type"]

        if itype in ("missing_title", "title_too_short", "title_too_long"):
            for url in issue["affected_urls"]:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                r = rows_map.get(url, {})
                old = (r.get("Title 1", "") or "").strip()
                h1  = (r.get("H1-1", "") or "").strip()
                h2  = (r.get("H2-1", "") or "").strip()

                if itype == "missing_title":
                    base = h1 or h2 or url.rstrip("/").split("/")[-1].replace("-", " ").title() or site
                    new = f"{base} | {site}"[:60]
                elif itype == "title_too_short":
                    new = f"{old} | {site}"
                    if len(new) > 60:
                        new = new[:57] + "..."
                else:  # title_too_long
                    # Hard truncate to 57 chars + ellipsis
                    new = old[:57] + "..." if len(old) > 60 else old

                # Final validation: enforce 30–60 char bounds
                if len(new) > 60:
                    new = new[:57] + "..."
                if len(new) < 30:
                    new = f"{new} | {site}"[:60]

                title_fixes.append({"url": url, "old": old, "new": new})

        elif itype in ("missing_meta_description", "meta_description_too_long"):
            for url in issue["affected_urls"]:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                r = rows_map.get(url, {})
                old = (r.get("Meta Description 1", "") or "").strip()
                h1  = (r.get("H1-1", "") or "").strip()

                if itype == "missing_meta_description":
                    base = h1 or url.rstrip("/").split("/")[-1].replace("-", " ").title() or site
                    new = f"Learn about {base} on {site}. Explore our services, insights, and more."
                else:
                    new = old[:152] + "..." if len(old) > 155 else old

                if len(new) > 155:
                    new = new[:152] + "..."

                title_fixes.append({"url": url, "old": old, "new": new})

    # ── Redirect map for broken links ────────────────────────────────────────
    redirect_map_out = []
    for issue in RUN.get("issues", []):
        if issue["type"] == "broken_link":
            for url in issue["affected_urls"]:
                # Try to find a live page with a similar path; fall back to homepage
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.strip("/").split("/") if p]
                # Walk up the path tree to find a live 200 page
                best_target = site_home
                for depth in range(len(path_parts), 0, -1):
                    candidate = f"https://{parsed.netloc}/" + "/".join(path_parts[:depth]) + "/"
                    if candidate in rows_map and rows_map[candidate].get("Status Code", "") == "200":
                        best_target = candidate
                        break

                redirect_map_out.append({
                    "from": url,
                    "to": best_target,
                    "reason": f"404 response → nearest live ancestor or homepage",
                })

    RUN["fixes"] = {"titles": title_fixes, "redirect_map": redirect_map_out}
    _emit("fixes", RUN["fixes"])
    return {"fixed_count": len(title_fixes), "redirects": len(redirect_map_out)}


def seo_recommend(recommendations: list) -> dict:
    RUN["recommendations"] = recommendations
    _emit("recommendations", {"recommendations": recommendations})
    return {"count": len(recommendations)}


def seo_report() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(_report_obj(), f, indent=2)
    RUN["status"] = "done"
    _emit("saved", {"path": p})
    return {"path": p}


def seo_export() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(_render_html(_report_obj()))
    _emit("exported", {"path": p})
    return {"path": p}


def _render_html(o: dict) -> str:
    """Render a full client-ready HTML report."""
    sev_counts = (o.get("summary") or {}).get("by_severity", {})
    total = (o.get("summary") or {}).get("total_issues", 0)

    # Issue rows sorted High → Medium → Low
    sev_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_issues = sorted(o.get("issues", []),
                           key=lambda x: (sev_order.get(x["severity"], 3), x["type"]))

    issue_rows = ""
    for i in sorted_issues:
        sev_cls = i["severity"].lower()
        # Show first 5 affected URLs as links, then a count
        urls = i.get("affected_urls", [])
        url_snippet = ", ".join(
            f'<a href="{u}" target="_blank" rel="noopener" style="color:#7ca4d4;word-break:break-all">{u}</a>'
            for u in urls[:5]
        )
        if len(urls) > 5:
            url_snippet += f' <span style="color:#c8c5be">… and {len(urls)-5} more</span>'
        expl = i.get("explanation", "")
        issue_rows += f"""
        <tr>
          <td><span class="sev {sev_cls}">{i["severity"]}</span></td>
          <td style="font-weight:600">{i["type"]}</td>
          <td style="text-align:center">{i["count"]}</td>
          <td style="color:#c8c5be;font-size:12px">{expl}</td>
        </tr>
        <tr class="url-row">
          <td colspan="4" style="padding:4px 10px 12px 22px;font-size:12px;color:#9a9a9a">
            {url_snippet}
          </td>
        </tr>"""

    rec_items = "".join(f"<li>{r}</li>" for r in o.get("recommendations", []))
    if not rec_items:
        rec_items = "<li style='color:#c8c5be'>No recommendations generated.</li>"

    # Fix tables
    title_fix_rows = ""
    for f in (o.get("fixes") or {}).get("titles", [])[:50]:
        old_val = f.get("old") or "<em style='color:#888'>empty</em>"
        title_fix_rows += f"""<tr>
          <td style="word-break:break-all;font-size:11px">{f["url"]}</td>
          <td style="color:#c8c5be;font-size:12px">{old_val}</td>
          <td style="color:#7ec47e;font-size:12px">{f.get("new","")}</td>
        </tr>"""
    if not title_fix_rows:
        title_fix_rows = '<tr><td colspan="3" style="color:#888">No title/meta fixes generated.</td></tr>'

    redirect_rows = ""
    for r in (o.get("fixes") or {}).get("redirect_map", [])[:50]:
        redirect_rows += f"""<tr>
          <td style="word-break:break-all;font-size:11px">{r["from"]}</td>
          <td style="word-break:break-all;font-size:11px">{r["to"]}</td>
          <td style="color:#c8c5be;font-size:12px">{r.get("reason","")}</td>
        </tr>"""
    if not redirect_rows:
        redirect_rows = '<tr><td colspan="3" style="color:#888">No redirects needed.</td></tr>'

    model = (o.get("run_meta") or {}).get("model", "local")
    model_calls = (o.get("run_meta") or {}).get("model_calls", 0)
    duration = (o.get("run_meta") or {}).get("duration_sec", 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO Audit Report — {o['site']}</title>
<style>
  :root{{--ink:#1a1a1f;--card:#242428;--line:#3a3a42;--paper:#f8f7f4;--mute:#c8c5be;--red:#e05252;--yellow:#e2b53e;--green:#7ec47e}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:Inter,system-ui,sans-serif;background:var(--ink);color:var(--paper);line-height:1.55;padding:40px 20px}}
  .wrap{{max-width:960px;margin:0 auto}}
  h1{{font-size:26px;font-weight:700;margin-bottom:4px}}
  .sub{{color:var(--mute);font-size:14px;margin-bottom:32px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:20px}}
  h2{{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--mute);margin-bottom:14px;font-weight:600}}
  h3{{font-size:16px;font-weight:600;margin-bottom:12px}}
  .kpis{{display:flex;gap:28px;flex-wrap:wrap}}
  .kpi{{min-width:80px}}.kpi .val{{font-size:36px;font-weight:700;line-height:1}}
  .kpi .lbl{{font-size:12px;color:var(--mute);margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);padding:8px 10px;border-bottom:2px solid var(--line);text-align:left}}
  td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
  .url-row td{{background:rgba(0,0,0,.15)}}
  .sev{{font-size:10px;font-weight:700;padding:3px 8px;border-radius:999px;white-space:nowrap}}
  .sev.high{{background:var(--red);color:#fff}}
  .sev.medium{{background:var(--yellow);color:#1a1a1f}}
  .sev.low{{background:var(--line);color:var(--mute)}}
  ul{{padding-left:18px}}li{{margin:6px 0;font-size:14px}}
  .muted{{color:var(--mute)}}
  .footer{{text-align:center;color:var(--mute);font-size:12px;margin-top:32px}}
  @media(max-width:600px){{body{{padding:20px 12px}}.kpis{{gap:16px}}.kpi .val{{font-size:28px}}}}
</style>
</head>
<body>
<div class="wrap">

  <h1>SEO Audit Report</h1>
  <div class="sub">{o['site']} &nbsp;·&nbsp; {o['urls_crawled']} URLs crawled</div>

  <!-- KPI summary -->
  <div class="card">
    <h2>Summary</h2>
    <div class="kpis">
      <div class="kpi"><div class="val">{total}</div><div class="lbl">Total Issues</div></div>
      <div class="kpi"><div class="val" style="color:var(--red)">{sev_counts.get('High',0)}</div><div class="lbl">High</div></div>
      <div class="kpi"><div class="val" style="color:var(--yellow)">{sev_counts.get('Medium',0)}</div><div class="lbl">Medium</div></div>
      <div class="kpi"><div class="val">{sev_counts.get('Low',0)}</div><div class="lbl">Low</div></div>
      <div class="kpi"><div class="val">{o['urls_crawled']}</div><div class="lbl">URLs</div></div>
    </div>
  </div>

  <!-- Recommendations -->
  <div class="card">
    <h3>Recommendations</h3>
    <ul>{rec_items}</ul>
  </div>

  <!-- Issues table -->
  <div class="card">
    <h3>All Issues (prioritized by severity)</h3>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th style="width:80px">Severity</th>
            <th>Issue Type</th>
            <th style="width:60px;text-align:center">URLs</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {issue_rows or '<tr><td colspan="4" class="muted">No issues detected.</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Title / meta fixes -->
  <div class="card">
    <h3>Title &amp; Meta Fixes</h3>
    <p style="color:var(--mute);font-size:13px;margin-bottom:14px">Suggested rewrites for missing, too-short, or too-long titles and meta descriptions (showing first 50).</p>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>URL</th><th>Current</th><th>Suggested</th></tr></thead>
        <tbody>{title_fix_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Redirect map -->
  <div class="card">
    <h3>Redirect Map</h3>
    <p style="color:var(--mute);font-size:13px;margin-bottom:14px">Suggested redirects for 4xx broken links (showing first 50).</p>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>From (broken)</th><th>To (target)</th><th>Reason</th></tr></thead>
        <tbody>{redirect_rows}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Generated by SEO Command Center &nbsp;·&nbsp;
    Model: {model} &nbsp;·&nbsp;
    Model calls: {model_calls} &nbsp;·&nbsp;
    Duration: {duration}s
  </p>

</div>
</body>
</html>"""


# ── dashboard HTTP host ──────────────────────────────────────────────────────

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            p = os.path.join(DASH_DIR, "index.html")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "no dashboard")

        elif path == "/app.js":
            p = os.path.join(DASH_DIR, "app.js")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "",
                       "application/javascript")

        elif path == "/state":
            self._send(200, json.dumps({k: v for k, v in RUN.items() if k != "rows"}),
                       "application/json")

        elif path == "/run":
            # Trigger a full audit; export_dir comes from query string or falls back to RUN state
            qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            export_dir = (qs.get("dir", [None])[0]
                          or RUN.get("export_dir")
                          or os.path.join(ROOT, "..", "sample-export"))
            seo_load(export_dir)
            seo_detect()
            seo_fix()
            issues = RUN["issues"]
            sorted_issues = sorted(issues, key=lambda x: {"High":0,"Medium":1,"Low":2}.get(x["severity"],3))
            recs = _build_recommendations(sorted_issues)
            seo_recommend(recs)
            seo_report()
            seo_export()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

        elif path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q: queue.Queue = queue.Queue()
            with _lock:
                _subs.append(q)
            try:
                snap = {k: v for k, v in RUN.items() if k != "rows"}
                self.wfile.write(
                    f"data: {json.dumps({'event':'snapshot','data':snap})}\n\n".encode()
                )
                self.wfile.flush()
                while True:
                    try:
                        self.wfile.write(f"data: {q.get(timeout=15)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with _lock:
                    if q in _subs:
                        _subs.remove(q)
        else:
            self._send(404, "not found")


def _build_recommendations(sorted_issues: list) -> list:
    """Build prioritized, actionable recommendations from detected issues."""
    recs = []
    high = [i for i in sorted_issues if i["severity"] == "High"]
    med  = [i for i in sorted_issues if i["severity"] == "Medium"]
    low  = [i for i in sorted_issues if i["severity"] == "Low"]

    if high:
        top = high[0]
        recs.append(
            f"PRIORITY: Fix {top['count']} {top['type'].replace('_',' ')} issue(s) immediately — "
            f"these directly harm crawlability and rankings."
        )
    for i in high[1:3]:
        recs.append(f"High: Resolve {i['count']} {i['type'].replace('_',' ')} URL(s).")
    for i in med[:3]:
        recs.append(f"Medium: Address {i['count']} {i['type'].replace('_',' ')} URL(s) to improve SERP appearance.")
    if low:
        total_low = sum(i["count"] for i in low)
        recs.append(f"Low: {total_low} low-severity issues across {len(low)} issue type(s) — tackle after High/Medium.")
    if not recs:
        recs.append("No issues detected on this crawl — site looks healthy.")
    return recs


def start_dashboard(port=PORT):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _run_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print(f"[seo] MCP SDK not found. Dashboard only at http://localhost:{PORT}", flush=True)
        while True:
            time.sleep(3600)

    mcp = FastMCP("seo-command-center")

    @mcp.tool()
    def load(export_dir: str) -> dict:
        """Load a Screaming Frog export directory (expects internal_all.csv)."""
        return seo_load(export_dir)

    @mcp.tool()
    def detect_issues() -> dict:
        """Run all SEO rulebook detectors over the loaded crawl."""
        return seo_detect()

    @mcp.tool()
    def fix() -> dict:
        """Generate title/meta rewrites and a redirect map for broken links."""
        return seo_fix()

    @mcp.tool()
    def set_fixes(titles: list = None, redirect_map: list = None) -> dict:
        """Attach model-written title rewrites and the redirect map."""
        return seo_set_fixes(titles, redirect_map)

    @mcp.tool()
    def recommend(recommendations: list) -> dict:
        """Attach prioritized recommendations."""
        return seo_recommend(recommendations)

    @mcp.tool()
    def write_report() -> dict:
        """Write outputs/report.json."""
        return seo_report()

    @mcp.tool()
    def export_report() -> dict:
        """Write outputs/report.html (the client deliverable)."""
        return seo_export()

    mcp.run()


if __name__ == "__main__":
    start_dashboard()
    print(f"[seo] dashboard live at http://localhost:{PORT}", flush=True)
    _run_mcp()
