# DECISIONS.md — decision & learnings log

A short running note of the real choices you made: what you tried, what failed and why, what
you changed. This is your engineering judgement on the record — it is what separates a builder
from a button-presser, and it is graded (challenge brief section 08).

Append a 1–2 line entry whenever you make a real decision or hit/fix a wall. Add a timestamp.

Format:
`[HH:MM] <decision or problem> → <what you did and why>`

---

## Example (replace with your own)
- `[14:25]` ... Chose plain-csv parsing over pandas → fewer deps, fast enough for 5k rows, model
  quota saved for the fixer.
- `[14:28]` ... Title detector over-counted duplicates → realized non-indexable pages were
  included; added an indexable+200 filter (per rulebook).
- `[14:30]` ... Dashboard wasn't updating live → MCP tool wasn't emitting the SSE event; added
  `_emit("issue", row)` in extract.

---

## My log

- `[14:30]` Performed gap analysis between `seo/detector.py` and `rulebook.md` → Found 4 missing detectors: `redirect_chain` (High), `non_indexable_but_linked` (Medium), `thin_content` (Low), and `slow_page` (Low). Priority for implementation: High → Medium → Low.

 `[14:25]` Initial full-project analysis was slow → Switched to focused file-level analysis (`seo/detector.py`) to reduce Claude processing time and improve iteration speed.

 `[14:28]` Chose to maintain `CLAUDE.md`, `PROMPTS.md`, and `DECISIONS.md` manually → Reserved Claude usage primarily for code generation and debugging to maximize development speed during the sprint.

 * `[15:05]` Implemented redirect_chain, non_indexable_but_linked, thin_content and slow_page detectors → Expanded detector coverage from the starter implementation and increased total detected issue types from 4 to 12 on the sample export.

* `[15:07]` Re-ran end-to-end audit after detector implementation → Confirmed `python run.py ../sample-export` completed successfully and continued generating valid `report.json` and `report.html` outputs.

* `[15:10]` Began rulebook compliance verification → Comparing implemented detector logic against every rulebook requirement to identify any remaining gaps before moving to report, dashboard or fixer enhancements.


