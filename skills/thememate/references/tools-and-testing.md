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

**If a browser MCP is set up but its browser isn't running** (e.g. the
Playwright MCP expects Chrome on port 9222 and nothing answers there) and you
have terminal access, start the browser yourself -- don't stop to ask. Launch a
separate, isolated Chrome with an empty profile, never the user's own browser
session, and tell the user in one line that you did.

The profile starts empty on every launch, on purpose: every store's local
preview is served from the same `127.0.0.1:9292` origin, so cookies, local
storage and Swym's cached lists from one store would otherwise still be there
when the next store loads, and a check could pass or fail on the previous
store's state. The endpoint check used below is:

```
curl -s -m 2 http://127.0.0.1:9222/json/version | grep -q webSocketDebuggerUrl
```

(in Windows PowerShell: `curl.exe -s -m 2 http://127.0.0.1:9222/json/version | Select-String -Quiet webSocketDebuggerUrl`).
It succeeds only when a real Chrome debugging endpoint answers within 2 seconds.

1. If you launched this Chrome earlier in this session and are still on the
   same store, use it and stop here.
2. Otherwise close ThemeMate's own Chrome if one is running (a leftover from an
   earlier session, or the one for the previous store). Close only processes
   that are Chrome itself and were started with exactly
   `--user-data-dir=<home>/.claude/thememate-chrome-profile`, never a
   name-only match such as `pkill -f`, which would also hit the shell running
   the command and anything else that mentions the folder. `<home>` is the
   user's home directory (`$HOME`, or `%USERPROFILE%` on Windows). These
   commands list those processes:

   ```
   # macOS, Linux: PIDs of ThemeMate's Chrome
   ps -Ao pid=,command= | awk -v p="--user-data-dir=$HOME/.claude/thememate-chrome-profile" '/^ *[0-9]+ (\/Applications\/Google Chrome\.app\/|[^ ]*\/(google-chrome|chrome|chromium)[^ \/]*( |$))/ { for (i = 2; i <= NF; i++) if ($i == p) { print $1; break } }'
   # Windows (PowerShell): ThemeMate's Chrome processes
   $p = "--user-data-dir=$env:USERPROFILE\.claude\thememate-chrome-profile"
   Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" | Where-Object { $_.CommandLine -match ([regex]::Escape($p) + '("|\s|$)') }
   ```

   Stop them (`kill <pids>` on macOS/Linux; pipe the Windows list to
   `ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`). Then run the
   list again until it comes back empty (up to 10 seconds): Chrome keeps
   writing to its profile while it shuts down. Only then delete the profile
   folder (`rm -rf` on macOS/Linux, `Remove-Item -Recurse -Force` on Windows).
3. Run the endpoint check. If it still succeeds, the browser on 9222 is one the
   user started themselves: use it as is and stop here.
4. Find Chrome for the OS you are on:

   | OS | Where Chrome is |
   |---|---|
   | macOS | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
   | Windows | `chrome.exe` under `%ProgramFiles%`, `%ProgramFiles(x86)%` or `%LocalAppData%`, in `Google\Chrome\Application\` |
   | Linux | the first of `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser` on `PATH` |

5. Start it in the background, output discarded, with exactly these flags:

   ```
   --remote-debugging-port=9222
   --user-data-dir=<home>/.claude/thememate-chrome-profile
   --no-first-run --no-default-browser-check
   ```

6. Repeat the endpoint check for up to 10 seconds before using it.

Nothing carries over between launches, so a storefront password or test
customer login has to be entered again for each store. Ask the user only if you
have no terminal access, Chrome isn't in any of the places above, or the
endpoint check still fails after the launch.

When a test needs a logged-in customer, open the store's login page in this
Chrome and ask the user to log in there (see "Help from the user" in
[test-plan.md](test-plan.md)). Never ask for a password or login code in chat.

**If no browser-automation MCP is connected at all**, say so plainly and ask
the user to connect the Playwright MCP or `chrome-devtools` MCP before
continuing -- don't silently skip DOM/console validation or guess at live state
from the code alone.

**If a connected browser tool is blocked by policy for a target, don't
retry -- fall back to another connected browser-automation MCP.** If none
is available, tell the user how to connect one rather than degrading to
curl-only checks.

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

**Swym may not run on `127.0.0.1`.** Before you trust a local result, check
that the Swym API calls the change uses return real data there, not empty
results or errors. If they do not, ask the user before pushing and let them
pick the unpublished theme or create a new one (see "Local preview and
verify loop" in [shopify-workflow.md](shopify-workflow.md)), then test on its
preview URL (`https://<store-domain>/<path>?preview_theme_id=<id>`) and say so in the
result table (see "Where to test" in [test-plan.md](test-plan.md)).

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
list create, cart lines, items on a test customer's lists, etc. -- against a
real store, dev or otherwise, must be reverted before the session ends. Keep
a list of what you created as you go, and report what you removed.

## Fix loop and rollback

The verify loop in SKILL.md Section 5 decides when a fix is needed and when
the work is done. These rules cover the attempts inside one fix.

- Cap attempts within one approved fix at 3 iterations. If a fix doesn't work on the first
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
without the user explicitly confirming the test results look correct. A
plan being confirmed (SKILL.md Section 4) is not the same confirmation as the
test result being confirmed -- both are required, at different points in the
sequence. Pushing to an unpublished theme only to run the test plan, when
Swym cannot run locally, is testing, not "done", and it still needs the
user's go-ahead first.
