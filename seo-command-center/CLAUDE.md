# CLAUDE.md — project memory for the SEO Command Center build

This file is your **context / memory for the AI**. Claude Code loads it automatically every
session. Strong builders engineer this file instead of re-explaining everything in chat — it
is one of the clearest signals of good practice, and it is graded (see the challenge brief
section 08). Keep it short, specific, and update it as you learn.

Replace the prompts below with your own. This is YOUR file.

## What we are building
A Claude Code plugin that ingests a Screaming Frog SEO export (`internal_all.csv` + issue
CSVs), audits it against the rulebook, prioritizes issues, writes fixes, serves a live
dashboard at localhost:7700, and outputs `outputs/report.json` + `outputs/report.html`.

## Hard rules (the agent must follow these)
- Detect issues in **plain Python** (csv/pandas). Use the model only for judgment
  (rewriting titles/metas, choosing redirect targets). Never feed raw crawl rows to the model.
- `outputs/report.json` MUST match `report.schema.json`. Validate before declaring done.
- Filter to `text/html` + indexable pages before title/meta checks (see `rulebook.md`).
- Do not hard-code anything to the sample export — it must work on an unseen export.
- Keep model calls small and few (free-tier quota). One page per fix call.

## Architecture (keep it real)
- `skills/seo-audit/SKILL.md` orchestrates. Sub-agents: ingest, auditor, fixer, reporter.
- `seo/detector.py` = deterministic detectors (extend to the full rulebook — biggest score).
- `mcp/server.py` = MCP tools + the live dashboard.

## Conventions
- Commit after each working step with a real message.
- Run `python run.py sample-export/` to test end to end.

## Things I have learned during the build (update this as you go)
- (e.g. "SF leaves Title 1 blank on redirected URLs — must filter Status Code 200 first")
- ...
* Redirect chain detection can be implemented by building a redirect map and checking whether a redirect target is itself a redirecting URL.
* Non-indexable pages with internal inlinks should be flagged separately because crawl architecture may still be directing users and bots toward them.
* Thin content detection currently uses a word-count threshold and may require rulebook validation before final submission.
* Slow page detection currently uses response-time thresholds and should be verified against the official rulebook before finalizing.
* The detector expansion increased issue coverage from 4 detected issue types in the starter implementation to 12 issue types on the sample export.
* Successful detector changes should always be verified using `python run.py ../sample-export` before committing.
* Rulebook compliance verification should be performed after each detector batch to ensure no required checks remain unimplemented.
* Current focus is validating detector completeness against the rulebook before investing time in dashboard, reporting, or fixer enhancements.
* Rulebook coverage review confirmed that all required detector rules are implemented and verified.
* Detector development is considered functionally complete unless new rulebook discrepancies are discovered.
* Current priority has shifted from issue detection to fix generation and recommendation quality.
* Champion-tier scoring depends on generating useful title rewrites, meta description rewrites and redirect recommendations.
* Future implementation work should focus on fixer architecture, export quality and report usability rather than adding more detector types.
* Before modifying fixer logic, identify the exact files responsible for recommendations, rewrites and export generation.
* Every major implementation phase should follow: architecture review → implementation → validation → commit → documentation update.
