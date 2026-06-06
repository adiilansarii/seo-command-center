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

3. **Prompt:** "Open seo/detector.py. Implement title_too_short, missing_meta_description, duplicate_meta_description, meta_description_too_long, missing_h1, duplicate_h1, redirect_chain, non_indexable_but_linked, thin_content and slow_page."

   - **For:** Expanding detector coverage to align with the rulebook.
   - **Revised?** No.

4. **Prompt:** "Read rulebook.md. Compare every rulebook rule against seo/detector.py. Create a checklist with three sections: Implemented, Missing, and Partially Implemented. Do not modify any files."

   * **For:** Verifying detector coverage against the complete rulebook and identifying any remaining gaps before moving to dashboard or fixer improvements.
   * **Revised?** No.

5. **Prompt:** "Read README.md, run.py, skills/seo-audit/SKILL.md, agents/, and commands/seo-audit.md. Analyze the fixer architecture and explain title rewrites, meta rewrites, redirect recommendations, required outputs, implemented features and missing features. Do not modify files."

   - **For:** Understanding the fixer architecture before implementing title, meta and redirect recommendations.
   - **Revised?** No.  
