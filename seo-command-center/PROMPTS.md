# PROMPTS.md — my key prompts log

Keep the handful of prompts that actually moved the build. Not every message — the ones that
mattered: the system/sub-agent prompts, the ones you iterated on, the "this finally worked"
moment. This shows how you direct an AI, which is graded (challenge brief section 08).

Format per entry:
- **Prompt** (paste it)
- **For:** what you were trying to do
- **Revised?** did you have to change it, and why

---

## Example (replace with your own)

- **Prompt:** "Extend seo/detector.py to detect redirect chains: build a map of {Address ->
  Redirect URL} for all 3xx rows, then a chain exists when a Redirect URL is itself a key in
  that map. Add a redirect_chain issue (High). Run python seo/detector.py and show counts."
- **For:** adding the redirect-chain detector
- **Revised?** Yes — first version flagged single redirects as chains; added the "target is
  also a redirecting URL" condition.

---

## My prompts
1. **Prompt:** "Analyze this starter bundle. Read: README.md, ../rulebook.md, ../report.schema.json, run.py, seo/detector.py. Explain: 1. Which rulebook detectors are already implemented. 2. Which detectors are missing. 3. Which detectors should be implemented first for maximum score."
   - **For:** Performing a gap analysis to identify missing SEO detectors.
   - **Revised?** No.

2. **Prompt:** "Read seo/detector.py only. List: 1. Implemented detectors 2. Missing detectors. Do not modify files."

   * **For:** Quickly identifying completed and missing SEO detectors without analyzing the whole project.
   * **Revised?** Yes. Replaced a full-project analysis prompt because it was taking too long.

