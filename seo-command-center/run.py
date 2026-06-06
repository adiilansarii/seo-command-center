#!/usr/bin/env python3
"""
run.py — headless runner for the SEO Command Center (also the grader's entry point).

Runs the full pipeline on a Screaming Frog export with no Claude Code:
  load -> detect -> fix -> recommend -> write report.json + report.html

Usage:
  python run.py sample-export/
  python run.py sample-export/ --no-dashboard
"""
from __future__ import annotations
import argparse, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mcp"))
sys.path.insert(0, HERE)
import server  # the MCP server module exposes every tool as a function


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--no-dashboard", action="store_true")
    args = ap.parse_args()

    export_dir = os.path.abspath(args.export_dir)
    if not os.path.isdir(export_dir):
        print(f"[seo] ERROR: export directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)
    internal_csv = os.path.join(export_dir, "internal_all.csv")
    if not os.path.isfile(internal_csv):
        print(f"[seo] ERROR: internal_all.csv not found in {export_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.no_dashboard:
        server.start_dashboard()
        print(f"[seo] dashboard: http://localhost:{server.PORT}", flush=True)
        time.sleep(0.5)  # let the server bind

    t0 = time.time()

    print("[seo] Stage 1/4 — loading crawl data …", flush=True)
    load_result = server.seo_load(export_dir)
    print(f"[seo]   Loaded {load_result['urls']} URLs from {load_result['site']}", flush=True)

    print("[seo] Stage 2/4 — detecting issues …", flush=True)
    detect_result = server.seo_detect()
    print(f"[seo]   Detected {detect_result['detected']} issue types", flush=True)

    print("[seo] Stage 3/4 — generating fixes …", flush=True)
    fix_result = server.seo_fix()
    print(f"[seo]   Fixes: {fix_result['fixed_count']} title/meta, "
          f"{fix_result['redirects']} redirects", flush=True)

    print("[seo] Stage 4/4 — writing reports …", flush=True)
    issues = sorted(
        server.RUN["issues"],
        key=lambda x: {"High": 0, "Medium": 1, "Low": 2}.get(x["severity"], 3),
    )
    recs = server._build_recommendations(issues)
    server.seo_recommend(recs)

    duration = round(time.time() - t0, 1)
    server.RUN["model_calls"] = 0   # headless runner does no model calls
    server.RUN["duration_sec"] = duration

    server.seo_report()
    server.seo_export()

    # Also write fix CSVs for champion-tier scoring
    _write_fix_csvs()

    s = server.RUN["summary"]
    print("\n=== SEO AUDIT RESULT ===")
    print(f"Site         : {server.RUN['site']}  ({server.RUN['urls']} URLs)")
    print(f"Total issues : {s['total_issues']}  "
          f"(High {s['by_severity'].get('High', 0)} / "
          f"Medium {s['by_severity'].get('Medium', 0)} / "
          f"Low {s['by_severity'].get('Low', 0)})")
    print(f"Duration     : {duration}s")
    print("Outputs      : outputs/report.json  outputs/report.html")
    print("Fix files    : outputs/fix_titles.csv  outputs/redirect_map.csv")


def _write_fix_csvs():
    """Write champion-tier fix CSV files."""
    import csv
    os.makedirs(server.OUT_DIR, exist_ok=True)
    fixes = server.RUN.get("fixes", {})

    # Title / meta CSV
    titles_path = os.path.join(server.OUT_DIR, "fix_titles.csv")
    with open(titles_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["url", "old", "new"])
        w.writeheader()
        w.writerows(fixes.get("titles", []))

    # Redirect map CSV
    redirects_path = os.path.join(server.OUT_DIR, "redirect_map.csv")
    with open(redirects_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["from", "to", "reason"])
        w.writeheader()
        w.writerows(fixes.get("redirect_map", []))


if __name__ == "__main__":
    main()
