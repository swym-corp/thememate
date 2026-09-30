# thememate

A Claude Code plugin bundling **ThemeMate**, a Swym API-aware assistant for
implementing and debugging Swym features (Wishlist Plus, Save For Later,
Back In Stock, Recently Viewed, B2B List). Full pull/edit/local-preview/
push/GitHub workflow on Shopify storefronts. Knowledge-only suggestions on
other platforms (headless via the Swym REST API, BigCommerce, WooCommerce,
Wix) -- no theme pull, edit, or push there.

Who this is for: Agency Partners, Merchants, and Swym Internal staff
(Success, Support, ACQ).

> **Privacy notice: this plugin tracks skill usage with your email and name.**
> Every ThemeMate session sends usage events to Swym that include your email
> address and name. Telemetry is on by default, and the first ThemeMate
> session on a machine shows this notice once. See [Telemetry](#telemetry)
> for exactly what is sent, how to go anonymous, and how to opt out.

## Install

Marketplace: `swym-corp/thememate`. Plugin name: `swym`.

### From the Claude Code CLI (terminal)

In an interactive session:
```
/plugin marketplace add swym-corp/thememate
/plugin install swym@thememate
```

Non-interactive (scripting/CI) -- installs to user scope by default:
```bash
claude plugin marketplace add swym-corp/thememate
claude plugin install swym@thememate
```

### From the Claude Desktop app

The desktop app's Code tab has its own plugin browser -- no terminal needed:
1. Click the **+** button next to the prompt box.
2. Select **Plugins > Add plugin** to open the plugin browser.
3. Add the marketplace `swym-corp/thememate`.
4. Find **swym** in the list and install it, choosing a scope (user, project, or local).

### By asking Claude directly in chat

In any Claude Code chat (terminal or desktop), you can just ask Claude to do
the steps above for you instead of typing the commands yourself, e.g.:

> Add & install plugin swym-corp/thememate

This isn't a special command -- Claude reads the request and runs the same
marketplace-add and install steps on your behalf.

### Cloud sessions (claude.ai/code)

The plugin browser and `/plugin` aren't available in cloud sessions. Add this
to the repository's `.claude/settings.json` instead:
```json
{
  "extraKnownMarketplaces": {
    "thememate": {
      "source": { "source": "github", "repo": "swym-corp/thememate" }
    }
  },
  "enabledPlugins": { "swym@thememate": true }
}
```

## Usage

Just talk to Claude Code once the plugin is installed -- ThemeMate's
description-based trigger picks it up for Swym feature work. Ask a knowledge
question, describe a bug, or describe something to build; ThemeMate
classifies the mode and platform itself (see
`skills/thememate/SKILL.md`).

Alternatively, activate it directly with the slash command `/swym:thememate`
(plugin skills are namespaced by the plugin name, `swym`). You don't need to
type the full thing -- start typing `/thememate` and the autocomplete
dropdown will surface `/swym:thememate` to select.

For Shopify implementation and debug-with-a-fix work, ThemeMate always
presents a plan and waits for your explicit confirmation before writing or
pushing anything -- see SKILL.md Section 4.

## Structure

```
.claude-plugin/
  plugin.json       # plugin manifest
  marketplace.json  # self-referencing marketplace so this repo is installable on its own
hooks/
  hooks.json          # lifecycle hook registration
  telemetry-hook.py   # non-blocking lifecycle event emitter
  telemetry_state.py  # per-session state recorder, read by telemetry-hook.py at session end
  telemetry_common.py # shared opt-out, anonymous mode, identity and send helpers
skills/thememate/
  SKILL.md          # entry point: roles, modes, platform routing, the plan-before-edit gate
  references/
    roles.md              # agency / merchant / swym_internal detection
    tools-and-testing.md  # tool choice per mode, local-preview validation order
    shopify-workflow.md   # prerequisites -> pull -> plan -> edit -> preview -> push -> GitHub
    failure-patterns.md   # 9 common post-theme-update Swym failure patterns
    rest-api.md           # Swym REST API (headless)
    js-api.md             # Swym JS API (Shopify/BigCommerce)
    other-platforms.md    # knowledge-only support matrix
```

## Prerequisites

**1. Claude Code**
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

**2. Node.js 18+**
```bash
node --version   # must be >= 18.0.0
```

**3. Shopify CLI** (Shopify storefront work only)
```bash
npm install -g @shopify/cli@latest
shopify auth login
```

**4. `gh` CLI** (only if you want GitHub version control on your changes)
```bash
gh auth login
```

**5. A browser-automation MCP server**, for local-preview validation --
either the Playwright MCP or the `chrome-devtools` MCP, whichever your
Claude Code setup already has connected.

If that MCP expects Chrome on port 9222 and nothing is running there,
ThemeMate starts a separate Chrome for it (macOS, Windows or Linux) and tells
you it did. That Chrome uses its own profile in
`~/.claude/thememate-chrome-profile`, apart from your normal browser, and
ThemeMate empties it on every launch, including when it moves to a different
store, so nothing (cookies, logins, Swym's cached data) carries from one store
or session to the next. ThemeMate only ever closes that Chrome, never yours.

## Telemetry

**We track ThemeMate skill usage, and every event is tied to your email
address and name.** Telemetry is enabled by default.

**Who you are.** Every event (session start, each heartbeat, session end)
carries:
- your email address and name, taken from your Claude account
  (`~/.claude.json`), or from your git `user.email` / `user.name` if the
  Claude account has none
- a random install ID generated once per machine
- for agency sessions, your Claude account's organization name as the agency
  name
- for Swym staff, your team (ACQ, Success, Support or Other), asked once and
  saved in `~/.claude/.thememate/profile.json` (delete that file to be asked
  again)

**What you did.** Alongside your identity, events carry:
- the mode, Swym feature, outcome, and the use case and summary of the task.
  The use case and summary are free-text paraphrases of your request, so they
  can include whatever details you gave
- the merchant store and any demo store the session works on, for any
  session that names one
- turn and token counts for the session (token counts leave out cache reads)
- for each theme change ThemeMate pushes or hands over: the store, one page it
  renders on, the files it touched and its change id, plus the pushed theme id
  for pushed changes

**What ThemeMate leaves in your theme.** Files, classes and ids ThemeMate
creates start with `swymtm-`, and each change carries an opaque id such as
`data-swymtm="c1a2b3c4d"` (or an HTML comment `<!-- swymtm:c1a2b3c4d -->`). The id
holds no personal data. Once a day Swym's telemetry service loads that one page
of your public storefront, as any visitor would, to see whether the change is
live. Removing the marker is harmless; it only hides the change from that check.
With telemetry off, only the `swymtm-` naming is added.

**When it is sent.** Only in sessions that invoke ThemeMate: once when it
starts, after every assistant turn, and when the session ends.

**Where it goes.** `https://swym-thememate-telemetry.internalswym.com/v1/telemetry/events`,
a Swym internal service. See `hooks/telemetry-hook.py`,
`hooks/telemetry_state.py` and `hooks/telemetry_common.py` for exactly what
is collected and sent.

**Going anonymous.** Set `THEMEMATE_TELEMETRY_ANONYMOUS` to any non-empty
value and your email address and name are left out of every event. Everything
else is still sent, including the agency name. Anonymous events use a separate
install ID, so they can't be linked to sessions you sent before with your
identity.

**Opting out.** Set `THEMEMATE_TELEMETRY_DISABLED` to any non-empty value and
nothing is sent or kept on disk, apart from your saved team. It overrides
anonymous mode.

To keep either setting across sessions, add it to `~/.claude/settings.json`:

```json
{ "env": { "THEMEMATE_TELEMETRY_ANONYMOUS": "1" } }
```

## Known gaps

Most `NEEDS VERIFICATION` markers in `rest-api.md` have been resolved against
Swym's public developer docs (update-list-attributes and single-product
social-count now have confirmed paths and parameters). Still unconfirmed:

- The exact REST path for merging a guest session into a logged-in one (the
  JS SDK's equivalent, `guest-validate-sync`, is confirmed by name, but the
  raw HTTP path isn't documented).
- Whether a dedicated batch social-count REST endpoint exists at all, versus
  the JS SDK's batch method simply looping the single-product endpoint.
- The Save For Later `remove` method signature and its "Add Items [Beta]"
  REST path.
- The Back In Stock (SBiSA) App Embed block's exact handle -- verify per
  store via the grep in `js-api.md` rather than assuming a name.

Check `developers.getswym.com` (or the Swym Developer Docs MCP, if connected)
before relying on any entry still marked `NEEDS VERIFICATION`.
