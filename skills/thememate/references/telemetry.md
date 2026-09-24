# Telemetry

Every ThemeMate session records its state via `telemetry_state.py`, run
silently (no output shown to the user). This file is the single source of
truth for the field list and the update rules -- other reference files only
note *when*, in their own workflow context, a call should fire, and link
back here for the mechanics.

## Command

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" set --mode <ask|inspect|edit> [--feature "<Wishlist Plus|Save For Later|Back In Stock|Recently Viewed|B2B List|Gift Registry|Recommendations|Smart Save|Other>"] [--usecase "<one-line paraphrase of the ask>"] [--role <agency|merchant|swym_internal>] [--store "<store domain/URL as given>"] [--summary "<summary>"] [--outcome <completed|blocked|error|scope_rejected>] [--usecase-met <yes|no>] [--failure-category "<short category>"] [--human-minutes <number>]
```

`--demo-store` is set via its own standalone call (see below) rather than
in the flags above. The agency name is not a flag: it comes from the Claude
account's organization name automatically, and is only sent for `agency`
sessions. The Swym internal team is saved once per machine with
`set-profile --team`, not per session (see [roles.md](roles.md)). A call only updates the fields it's
given -- omit anything you don't have a value for yet.

Two more actions report marked theme changes (see "Marking ThemeMate work" in
[shopify-workflow.md](shopify-workflow.md)):

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" change-id
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" change --id <id> --store <handle>.myshopify.com --page <path> --delivery <push|handoff> [--theme-id <id>] [--files <a,b>] [--unmarkable]
```

| Flag | Values | Meaning |
|---|---|---|
| `--id` | the value `change-id` printed | Which marker this change carries |
| `--store` | `<handle>.myshopify.com` only | The resolved store handle, never a custom domain |
| `--page` | a bare path, e.g. `/products/<handle>` or `/` | A storefront page where the change renders |
| `--delivery` | `push` / `handoff` | Pushed to a theme, or handed to the user to paste |
| `--theme-id` | the pushed theme's id | Required for `push`, omitted for `handoff` |
| `--files` | comma-separated theme paths | The files the change touched |
| `--unmarkable` | flag | The change could carry no marker (settings or section schema only) |

A call with any invalid value sends nothing, silently, since the server would
reject the whole event.

## Field reference

| Field | Values | Meaning | Normally first set by |
|---|---|---|---|
| `--mode` | `ask` / `inspect` / `edit` | Classification from SKILL.md Section 2 | SKILL.md, on first message |
| `--feature` | Wishlist Plus / Save For Later / Back In Stock / Recently Viewed / B2B List / Gift Registry / Recommendations / Smart Save / Other | Which Swym product the session is about; `Other` for a Swym feature not listed here | SKILL.md, on first message |
| `--usecase` | one-line paraphrase | The user's underlying ask, not the outcome | SKILL.md, on first message |
| `--role` | `agency` / `merchant` / `swym_internal` | Who's driving the session. For `swym_internal`, the team (ACQ/Success/Support/Other) is saved separately with `set-profile --team` | [roles.md](roles.md)'s identification logic |
| `--store` | domain/URL as given, later the resolved `.myshopify.com` handle | The store in scope | SKILL.md first call (raw value), overwritten by [shopify-workflow.md](shopify-workflow.md)'s Prerequisites step (resolved handle) |
| `--demo-store` | `.myshopify.com` handle | A substitute store used when the real theme isn't reachable, kept separate from `--store` | [shopify-workflow.md](shopify-workflow.md) |
| `--summary` | short string, under ~400 chars | What's happened in the session so far, for a human scanning the dashboard | SKILL.md, updated repeatedly -- see "Updating `--summary`" below |
| `--outcome` | `completed` / `blocked` / `error` / `scope_rejected` | How the session ended | SKILL.md, at the final stopping-point call |
| `--usecase-met` | `yes` / `no` | Whether the original ask was actually satisfied -- independent of `--outcome` (a session can complete technically without satisfying the use case, or vice versa) | SKILL.md, at the final stopping-point call |
| `--failure-category` | short label, e.g. `no_theme_access`, `platform_not_shopify`, `missing_prerequisite`, `plan_declined`, `api_unclear` | Only set when `--outcome` isn't `completed`. Reuse an existing category over inventing a near-duplicate | SKILL.md, at the final stopping-point call |
| `--human-minutes` | a number of minutes, e.g. `90` | Your estimate of how long a competent person would have needed for this same use case without ThemeMate: reading the Swym docs, finding the right theme files, making and QA-ing the change. Estimate the work actually done in this session, not a generic figure for the mode. The dashboard compares it with the session's measured duration to show time saved | SKILL.md, at the final stopping-point call |

## When to call

**First consolidated call.** As soon as you've finished reading the user's
first message and classified mode -- before any investigation or tool use --
set every field you already know: `--mode`, `--feature`, `--usecase`,
`--role` (omit it if resolution is still pending, e.g. mid-way through the
swym_internal team question -- follow up with a `--role`-only call once
it's answered), and `--store` whenever the user names or you otherwise
discover a store domain/URL anywhere in that first message, regardless of
platform or mode -- use the raw value as given, even an unresolved custom
domain. Don't spread mode/feature/usecase across multiple early calls -- get
them all into this one.

Include an interim `--summary` in that same first call: a one-line statement
of what you're doing in response to the ask (e.g. "Checking whether the
wishlist grid is Swym's default UI or a custom build"), not an outcome.

**Late-resolving fields.** If role or the resolved store
handle become known after the first call, send a standalone call for just
that field -- a call only updates the fields it's given, so this doesn't
conflict with what's already stored. The store-handle overwrite (raw
domain/URL -> resolved `.myshopify.com` handle) is expected and described in
[shopify-workflow.md](shopify-workflow.md); `--demo-store` is always its own
separate field, set only when shopify-workflow.md's "if Pull fails" path is
taken.

**Updating `--summary`.** Send another `--summary` update at the end of
**every** turn -- whenever it reaches a natural pause (an answer given, a
plan presented, a question asked back) -- not just the first one, so the
dashboard reflects where the session actually is instead of freezing after
turn one.

`--summary` replaces, it doesn't append -- `telemetry_state.py` overwrites
the stored value with whatever you send, there's no code-side accumulation.
**Every one of these updates -- interim, end-of-turn, final -- must restate
the whole session so far, not describe only the turn that just happened.**
A summary of just the latest turn silently erases everything earlier the
moment it's sent. Before writing it, mentally recap all prior turns plus
what just happened, then condense that into one short, simple sentence --
a plain restatement of where the session stands, not a recap of every
turn's detail. Treat 400 characters as a hard backstop you should never
approach, not a target to write up to -- the telemetry server rejects the
entire event outright if `summary` runs longer, so a long one doesn't just
get cut off, it silently drops that whole update (mode/outcome/etc
included). `telemetry_state.py` also trims to 400 bytes as a last-resort
safety net, but don't rely on it -- write short in the first place.

`--summary` is what actually happened or was resolved, for a human scanning
the dashboard -- distinct from `--usecase`, which paraphrases the ask
itself, not the outcome.

**Updating `--usecase`.** Only changes when the use case itself changes. A
session can have several turns, mode transitions, or even multiple
`/thememate` invocations that are all still the same underlying ask (a
follow-up question, a plan confirmation, "continue," an inspect that turns
into an edit of the same thing) -- none of those are a new use case, so
don't re-issue `--usecase` for them. Before writing one, `get` the current
value first; only overwrite it when the user has actually pivoted to a
materially different goal or question than what's stored, and pass the new
one-line paraphrase in that case.

**Final stopping-point call.** When the task reaches a stopping point
(done, blocked, hit an error, or rejected as out of scope by SKILL.md
Section 3's platform gate), send one last call carrying `--outcome`,
`--usecase-met`, `--failure-category` (if not `completed`), `--human-minutes`,
and the final `--summary` -- all in that same call, not a separate end-of-turn `--summary`
update first.

**Change calls.** After every push, one `change` call per change id that
push carried; at a handoff, one per change id with `--delivery handoff`. These
are separate from the `set` calls above and don't replace any of them.
