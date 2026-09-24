# Shopify workflow

The full sequence for `inspect` (once a fix is requested) and `edit`
on Shopify, per SKILL.md Section 3's platform gate. Every step's concrete
tooling is in [tools-and-testing.md](tools-and-testing.md); this file is the
order and the reasoning for it.

## 0. Prerequisites (first session on a store, before Pull)

Confirm these before reasoning about anything else. If any fails, stop and
wait for the user to fix it -- don't work around a missing prerequisite.

**Store identification (custom domain given instead of `<store>.myshopify.com`):**
Every command below needs the real `.myshopify.com` handle -- `--store` does
not accept a custom domain. If the user gives a custom domain (e.g.
`acme.com`) instead of the handle, don't guess it from the domain name. With
a browser-automation MCP connected, eval `window.Shopify.shop` on the
storefront -- it returns the `<handle>.myshopify.com` string directly and, in
the same step, confirms the site is actually Shopify (the object won't exist
otherwise), which also settles SKILL.md Section 3's platform gate. If no
browser MCP is connected yet, ask the user for the handle directly (Shopify
Admin > Settings > Domains shows it as "myshopify.com domain") rather than
adding a separate detection mechanism.

Once resolved, record it silently (no output shown to the user) via
`--store` -- see [telemetry.md](telemetry.md). This overwrites whatever raw
domain/URL SKILL.md Section 2's first-turn call already recorded with the
authoritative resolved handle -- it isn't the first place `--store` gets
set, just the most trustworthy.

| Check | How | If it fails |
|---|---|---|
| Swym installed | Eval `window.__SWYM__VERSION__` on the storefront | Guide through: install Wishlist Plus from the Shopify App Store, enable App Embed, create a wishlist page, assign it in Swym Dashboard > Settings |
| App Embed enabled | `grep -i "swym\|wishlist" ./<slug>/config/settings_data.json` (after Pull) | No entry -> instruct: Shopify Admin > Online Store > Themes > Customize > App Embeds > App Control Centre (Wishlist Plus) > toggle on |
| Wishlist page exists | Don't assume the handle is `swym-wishlist` -- read the header's wishlist/heart icon link (DOM `href` with a browser; else `grep -rn "wishlist" ./<slug>/sections/header*.liquid ./<slug>/snippets/*header*.liquid`) and navigate to that URL. Only fall back to `/pages/swym-wishlist` if no header link exists. The default page can still exist and render even when it's not what the header links to, so don't treat it as confirmation on its own. | No link and 404 -> instruct: create a wishlist page (any handle), link it from the header, assign it in Swym Dashboard |

Skip this on a return session for the same store (already confirmed once).

**No browser-automation MCP connected yet:** the "Swym installed" and
"Wishlist page exists" checks (and the `window.Shopify.shop` resolution
above) both need a live DOM eval and can't run until Section 3 of
`tools-and-testing.md` gets a browser attached. Don't skip this step
outright -- substitute browser-free proxies instead: for "Swym installed",
the same App Embed grep against `./<slug>/config/settings_data.json` used
below for "App Embed enabled" (see "Enumerating App Embed blocks" in
[js-api.md](js-api.md)), checking the block's `"disabled"` flag; for
"Wishlist page exists", the header-snippet grep above instead of navigating
straight to `/pages/swym-wishlist`. Both are lower-confidence than the live
DOM check -- state that plainly and re-confirm once a browser connects.

## 1. Pull

Before pulling anything, confirm the workspace is safe to write into:

```bash
git rev-parse --show-toplevel
```

If that resolves to an existing repo unrelated to this store (e.g. a tooling
or skills repo you happen to be running from), pull into a fresh sibling
directory instead of nesting theme files inside it -- theme code doesn't
belong mixed into an unrelated repo's history.

Get the real theme files before reasoning about anything:

```bash
shopify theme list --store <store>.myshopify.com
shopify theme pull --store <store>.myshopify.com --theme <id> --path ./<slug>
```

Never assume a theme's structure from a generic Shopify theme's conventions
-- read what this merchant's theme actually has. Check which layout file each
template in scope declares (`grep -rn '"layout"' ./<slug>/templates/`) --
themes with more than one vertical (e.g. `theme.liquid` plus `apparel.liquid`)
can have more than one, and a change applied to only one won't reach
templates that declare the other.

**First pull, no git history yet:** `git init`, commit the pulled state as a
baseline (e.g. "Baseline pull: `<theme name>` from `<store>`"), then create
the feature branch -- all before any edit touches a file.

**Return session:** if `./<slug>/.git` already exists from a prior session on
this store, don't re-initialize it -- the pull above still refreshes the
files to the store's current state, but keep the existing git history and
branch from it instead of starting over.

### If Pull fails (no file access)

**First, rule out the Partner staff-access provisioning gap** -- ask whether
the user has Partner Portal access to this store's org before assuming
genuine no-access. Shopify doesn't auto-create a staff account on a store
just from Partner org membership: CLI auth to a store the user hasn't opened
in a browser yet can fail with a "no staff access" error even though Partner
access exists. Opening the store's admin once lazily provisions that staff
session, after which `shopify theme pull` succeeds with no other change.

If they have Partner access, give them a direct link to log in and retry:

- Partner Portal (find the store from the org's store list):
  https://partners.shopify.com/organizations
- Direct to the store's admin, if the store handle is known:
  https://admin.shopify.com/store/<store-handle>

Have them open one of these, confirm the store admin loads, then retry Pull.
Only fall back to the role branches below if the user has no Partner access
at all, or the retry after logging in still fails.

- **`agency` / `swym_internal`:** offer to build on a demo store instead --
  the user provides a demo store they control. Extract brand identity from
  the live storefront's computed styles (button color/radius, fonts) since
  there's no theme file to read values from, build the change there, push
  `--unpublished`, and share the preview URL. Iterate (edit -> push -> share)
  until the user is satisfied. This never touches the merchant's real store,
  so it's out of the plan-before-edit gate's Shopify-theme concern, but still
  narrate the plan before writing anything. Once the demo store's handle is
  known, record it separately from `--store` above via `--demo-store` (see
  [telemetry.md](telemetry.md)).
- **`merchant`:** don't build on a substitute store. For CSS-only asks,
  offer the no-code Additional CSS path instead (see `roles.md`). For
  anything structural, stop: "I need access to your theme files for this.
  Ask your Shopify developer, or add `<user's email>` as staff in Shopify
  Admin > Settings > Users, or contact Swym support."

## 2. Plan (hard gate -- SKILL.md Section 4)

Narrate before writing anything:

1. New files to create (name, type, purpose).
2. Existing files to modify (name, the anchor you'll edit at, what changes).
3. The styling approach if this is a visual change -- see Path A / Path B below.
4. Actual values extracted from the pulled theme (brand colors/fonts from
   `config/settings_data.json` or `--color-*`/`--font-*` CSS variables) --
   never a placeholder or an eyeballed guess when the real value is one grep
   away.
5. For custom JS/API work: which Swym API this uses (REST or JS API) and why.

If Discovery/Analysis turned up an unrelated live bug sitting in or near the
anchor you're about to edit -- code already broken on the currently published
theme, independent of what was asked -- surface it plainly and let the user
choose whether to fix it as part of this change or leave it alone, rather
than folding it into the plan silently either way.

**Stop here and wait for explicit confirmation.** Revise and re-present if
the user asks for changes. Do not proceed to Edit on an assumption that a
plan this small "obviously" doesn't need confirmation.

### Path A -- style Swym's existing element

Keep Swym's own injected element; target it with a dedicated CSS asset file
(specific selector, not an inline `<style>` block -- many themes don't render
inline styles reliably). Use for color/size/border/icon-level changes. Lower
risk, prefer this when it satisfies the ask.

### Path B -- replace with a custom implementation

Disable Swym's default UI (the user does this via App Embeds -- ThemeMate
cannot toggle App Embeds itself; wait for their confirmation it's off) and
build a theme-level replacement: a layout-file include plus a custom Liquid
snippet, wired to the Swym API directly. Use when the ask needs a
placement, markup, or behavior Path A's CSS override can't reach.

## 3. Edit

Only after the plan is confirmed:

- grep for the anchor, Read the surrounding lines, Edit to patch. Write only
  for genuinely new files.
- Every new asset needs its include wired in the same session it's created
  (a CSS/JS file with no `<link>`/`<script>` tag, or a snippet with no
  `render` call, is not a finished change) -- across every distinct layout
  file found in step 1, not just the first one you touched.
- One commit per logical unit (asset file, layout injection, snippet each
  reasonably separable) on a feature branch, never on `main` directly.

### Marking ThemeMate work

Every change ThemeMate makes carries a marker, so the telemetry server's daily
crawler can see on the public storefront whether it went live. This is part of
the edit, not optional polish.

**Naming.** Every file, class, id, CSS custom property and JS global that
ThemeMate *creates* starts with `swymtm-` (e.g.
`snippets/swymtm-wishlist-grid-button.liquid`, `.swymtm-wl-grid-btn`). Never
rename Swym's own `swym-*` code or ACQ's `swymcs-*` custom code -- Path A keeps
targeting `.swym-*` selectors; only the new CSS file is `swymtm-`. Naming
applies even when telemetry is off.

**Change id.** One id per logical change (the same unit as one commit), from:

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" change-id
```

Never make one up. If it prints nothing, telemetry is off: stamp no id, keep
the naming. A later session editing a change that already carries a
`data-swymtm` id keeps that id rather than taking a new one.

**Placement** -- the marker must reach the rendered HTML:

| Change | Put `data-swymtm="<id>"` on |
|---|---|
| New CSS/JS asset | its `<link>` / `<script>` include tag, in every layout file it is wired into |
| New snippet | the snippet's root element (a `{% render %}` tag can't carry attributes) |
| Edit to existing theme markup | the edited element |
| Edit with no single element (Liquid logic) | wrap it: `<!-- swymtm:<id> -->` ... `<!-- /swymtm:<id> -->` |
| Only `settings_data.json` or a section schema | nothing can be marked; report it with `--unmarkable` |

Never use `{% comment %}` as a marker: Shopify strips Liquid comments before
the page is served, so the crawler can never see it.

**Page.** Note one real storefront path where each change renders (e.g.
`/products/<handle>` for a PDP change, `/` for a layout-wide one) -- the path
you checked in local preview. The crawler fetches exactly that page.

## 4. Local preview

Run the validation order in [tools-and-testing.md](tools-and-testing.md). Do
not skip straight to "looks done" -- confirm against the live dev server, not
against the diff.

## 5. Push to a duplicate theme

**First push of a session:** list themes (`shopify theme list --store
<store>.myshopify.com --json`), exclude `live`, and ask the user (up to 3
recent unpublished themes plus "Create new", 4 choices max) whether to
reuse one or create a new one.

- **Create new:** name defaults to `ThemeMate x <live theme name> x Swym`
  (editable), then `shopify theme push --unpublished --theme "<name>"`.
- **Reuse:** `shopify theme push --theme <id>` (no `--unpublished`).

Record the chosen theme id and reuse it for later pushes in the same
session without re-asking, unless the user starts a new task or requests a
different theme.

After every push, report each change id it carried, one call per id:

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" change --id <id> --store <handle>.myshopify.com --page <path> --delivery push --theme-id <pushed theme id> --files <comma-separated theme paths> [--unmarkable]
```

Run it silently, like every telemetry call. It sends nothing when telemetry
is off.

Never `--allow-live` or touch the `live`-role theme. The merchant/agency
reviews on the unpublished duplicate theme's preview link before deciding
to make it live themselves.

## 6. GitHub (optional, user opts in)

If the user wants version control on the changes:

```bash
gh repo create <org>/<name> --private   # confirm with the user first
git remote add origin <repo-url>
git push -u origin <feature-branch>
gh pr create
```

Skip entirely if the user doesn't ask for it -- local git history from step 3
is sufficient for rollback on its own.

If the user declines GitHub (or has no repo-create access) but still needs
to apply the change themselves -- or this was a demo-store session (step 1's
"If Pull fails" path) and they want it applied to their real store -- give
them a handoff package instead of a PR:

1. **Extracted values used** -- the brand colors/fonts/etc. actually pulled
   from the theme (or, for a demo-store session, from the live storefront)
   and used in the edit, so they're not re-guessing them.
2. **One code block per new or changed file** -- full contents for a new
   file, or the specific lines changed for an existing one.
3. **Where to paste each one** -- a short numbered list: which file, which
   anchor (e.g. "after `{{ content_for_header }}` in `layout/theme.liquid`"),
   and to preview as an unpublished theme copy before publishing.

The code blocks carry the same `swymtm-` naming and `data-swymtm` markers as a
pushed change (see "Marking ThemeMate work" in step 3), and each change id is
reported once with `--delivery handoff` and no `--theme-id`.
