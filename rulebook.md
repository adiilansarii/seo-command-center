# Forge Sprint 01 — SEO Detection Rulebook

Detect these issues from `internal_all.csv`. Each is a deterministic rule over the
columns, so you need no SEO background. The grader's ground truth uses these same
rules — match them precisely.

## Pre-filters (apply before title/meta/H1 checks)
- Only consider rows where `Content Type` contains `text/html`.
- For "duplicate" checks, only compare **Indexable** 200 pages.
- A page is "indexable" when `Indexability` = `Indexable`.

## Rules

| type (use this exact string) | Rule | Severity |
|---|---|---|
| `missing_title` | `Title 1` empty, indexable 200 page | High |
| `duplicate_title` | same `Title 1` on 2+ indexable URLs | High |
| `title_too_long` | `Title 1 Pixel Width` > 561 OR `Title 1 Length` > 60 | Medium |
| `title_too_short` | `Title 1 Length` < 30 (and not empty) | Low |
| `missing_meta_description` | `Meta Description 1` empty, indexable 200 page | Medium |
| `duplicate_meta_description` | same `Meta Description 1` on 2+ indexable URLs | Medium |
| `meta_description_too_long` | `Meta Description 1 Length` > 155 | Low |
| `missing_h1` | `H1-1` empty on a 200 page | Medium |
| `duplicate_h1` | same `H1-1` on 2+ indexable URLs | Low |
| `broken_link` | `Status Code` in 400–499 | High |
| `server_error` | `Status Code` in 500–599 | High |
| `redirect` | `Status Code` in 300–399 | Medium |
| `redirect_chain` | a redirect whose `Redirect URL` is itself a redirecting URL | High |
| `thin_content` | `Word Count` < 200 on an indexable page | Low |
| `orphan_page` | `Inlinks` = 0 on an indexable 200 page | Medium |
| `non_indexable_but_linked` | `Indexability` = Non-Indexable AND `Inlinks` > 0 | Medium |
| `slow_page` | `Response Time` > 1.0 | Low |

## Notes
- `redirect_chain`: build a map of {Address -> Redirect URL} for all 3xx rows, then a
  chain exists when a Redirect URL target is also a key in that map. A loop is a chain
  that returns to an earlier URL.
- Count = number of affected URLs. `affected_urls` = the list of those URLs.
- Severity strings must be exactly `High`, `Medium`, or `Low`.
- The hidden test export uses the SAME rules on a different site. Do not hard-code URLs.
