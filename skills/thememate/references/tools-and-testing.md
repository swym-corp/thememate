# Tools and testing

The concrete tool set for each mode x platform combination, and the
validation sequence to run after any Shopify edit. SKILL.md Section 4 (the
plan-before-edit gate) applies whenever a row below involves Write, Edit, or
`push` -- this file covers *which* tool, not *when* you're allowed to use it.

## By mode and platform

| Mode | Platform | Tools |
|---|---|---|
| `ask` | any | Reasoning plus [rest-api.md](rest-api.md) / [js-api.md](js-api.md) / [other-platforms.md](other-platforms.md). Use the Swym Developer Docs MCP if connected (discover the right `mcp__swym-dev-docs__*` tool via ToolSearch); otherwise web search against Swym's public developer docs. No file or CLI tools. |
| `inspect` | Shopify | `shopify theme list` / `shopify theme pull` to get the real files (never diagnose from memory or assumption); `grep`/Read to inspect them; a browser-automation MCP (Playwright MCP, or `chrome-devtools` MCP if already connected) against the live dev server for DOM state, console errors, and network requests. Code that reads as correct can still be broken in a way only a live check reveals -- don't report a status from static reading alone. |
| `inspect` | other platforms | Reasoning plus reference docs only, same as `ask`. No pull, no file inspection -- output stays suggestions and a plain-language description of the likely cause, never a diff. |
| `edit` | Shopify | `shopify theme pull`; `shopify theme dev` for local preview; `shopify theme push --unpublished` for the duplicate theme (never `--allow-live`); `git` for local version control; `gh` for the GitHub remote and PR once the user opts in; grep to find the anchor, Read the surrounding lines, then Edit to patch (never blind-overwrite a large file); Write only for genuinely new files. |
| `edit` | other platforms | Out of scope -- state that plainly. Fall back to an `ask`-style answer describing what would need to change. |

**If no browser-automation MCP is connected** when `inspect` or local-preview
validation needs one, say so plainly and ask the user to connect the
Playwright MCP or `chrome-devtools` MCP before continuing -- don't silently
skip DOM/console validation or guess at live state from the code alone.

**If a connected browser tool is blocked by policy for a target, don't
retry -- fall back to another connected browser-automation MCP.** If none
is available, tell the user how to connect one rather than degrading to
curl-only checks.

If the user would rather you connect one yourself: with their go-ahead,
launch a second, isolated Chrome instance with remote debugging enabled
rather than closing or reusing their existing browser session --

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="<scratchpad>/chrome-debug-profile" \
  --no-first-run --no-default-browser-check &
curl http://127.0.0.1:9222/json/version   # confirm it's up before handing off
```

Once the CDP endpoint responds, the Playwright/`chrome-devtools` MCP can
attach to it normally.

## Debug output shape

Check [failure-patterns.md](failure-patterns.md) against the symptom before
writing a novel diagnosis -- most post-theme-update Swym breakage is already
one of the nine patterns documented there.

`inspect` on Shopify ends with a feature-status table (what's present, what's
missing, source of truth = the live DOM, not just the file). When acting for
`swym_internal` / Support (see [roles.md](roles.md)), also produce a
paste-ready block:

```
Store: <url>  |  Theme: <name>  |  Date: <date>
Root cause: <plain-language description of the most likely cause>
Confidence: High / Medium / Low
Fix: <numbered steps>
Escalate to: Swym Engineering / Shopify Support / N/A
```

Fixing the root cause (if the user asks for it) re-enters the plan-before-edit
gate in SKILL.md Section 4 -- diagnosis alone never opens it.

## Local-preview validation order (after any Shopify edit)

Run `shopify theme dev --store <store>.myshopify.com --path ./<slug>` and
validate against the printed local URL, cheapest check first:

0. `shopify theme check` -- static Liquid lint, needs no dev server or
   browser. Compare the error/warning count against the pre-edit baseline
   (most real themes already carry some) rather than expecting zero; the
   bar is "no new offenses," not "no offenses."
1. A DOM/JS `evaluate()` check for the feature's presence (e.g. does the
   expected element/selector exist, is the Swym script initialized).
2. A computed-style diff between the new element and a reference element
   (colors, spacing, font) when the ask is visual.
3. Browser console messages for JS errors.
4. An accessibility snapshot for structural/layout issues.
5. A screenshot -- **last resort only**, single component (not full-page),
   and only when none of the above resolved the question.

**Rendering is async, not CORS-blocked.** Poll or wait for a readiness
signal before concluding a feature is absent -- don't check the DOM once
immediately after navigation.

**Stateful API behavior may be CORS-sensitive on `127.0.0.1` -- unverified.**
Confirm via a live probe if relevant; otherwise test against the pushed
theme's real preview URL
(`https://<store>.myshopify.com/...?preview_theme_id=<id>`).

**Cross-reference config before assuming App Embed behavior.** Before
assuming what an App Embed block does or doesn't support, check
`config/settings_schema.json` (every available toggle/token and its default
-- e.g. whether a `{{SOCIAL_COUNT}}`-style token even exists for a given
button) against `config/settings_data.json` (the merchant's actual per-block
overrides). Schema alone shows what's *possible*, including built-in features
that may already solve part of the ask with zero theme code; data overrides
show what's actually *on* right now. Don't infer one from the other.

**Leave the store as you found it.** Any inspect or local-preview action that
mutates real backend state -- wishlist add/remove, stock-alert subscribe,
list create, etc. -- against a real store, dev or otherwise, must be reverted
before the session ends.

## Fix loop and rollback

- Cap fix attempts at 3 iterations. If a fix doesn't work on the first
  attempt, don't spend the second attempt on another unverified guess --
  re-read the actual live computed styles/state first, then form a new
  hypothesis.
- If still broken after 3 iterations, stop and surface the failure to the
  user with what you found, rather than continuing to iterate silently.
- Rollback, in preference order: `git revert` on the feature branch (safe,
  keeps history) before restoring an older file version, before
  `shopify theme pull` from the live store as a last resort (only if local
  history is unusable).

## User confirmation before publish

Never move to pushing a duplicate/preview theme as "done," or opening a PR,
without the user explicitly confirming the local preview looks correct. A
plan being confirmed (SKILL.md Section 4) is not the same confirmation as the
test result being confirmed -- both are required, at different points in the
sequence.
