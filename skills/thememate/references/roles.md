# Roles

Three roles use ThemeMate. Role changes tone and which internal detail you
surface -- it never changes what platforms or modes are available (that's
the platform gate in SKILL.md Section 3).

## How to identify

Ask directly if it isn't obvious from context ("Are you a Swym team member,
an agency working on a merchant's behalf, or the merchant yourself?"). Signals
that suggest an answer without asking:

- An `@swymcorp.com` (or other confirmed Swym-internal) email domain in
  context -> likely `swym_internal`.
- The person's email domain differs from the store's own domain, and they
  describe managing the store for someone else -> likely `agency`.
- The person's email domain matches the store's domain, or they refer to the
  store as "my store" -> likely `merchant`.

Don't guess silently when signals conflict -- ask.

Once identified, record it silently (no output shown to the user) via
`--role` -- see [telemetry.md](telemetry.md) for the call mechanics and
timing (fold into SKILL.md's first-turn call if resolved by then, otherwise
a standalone follow-up call), as `agency`, `merchant` or `swym_internal`.
The Swym team is not part of the role: it's saved separately, see
`swym_internal` below.

For `agency`, the agency name is taken automatically from the Claude account's
organization name. Don't ask for it and don't record it yourself.

## agency

An agency partner implementing or maintaining Swym features on a merchant's
Shopify store on the merchant's behalf. Full access to the Shopify workflow.
Assume working knowledge of Shopify theme development; skip beginner
explanations of Liquid/theme structure unless asked.

## merchant

The store owner or their staff. Full access to the Shopify workflow. Do not
assume theme-development background -- explain what a change does in plain
terms alongside the technical detail, and prefer the lowest-risk implementation
path (Section on Path A/B in
[shopify-workflow.md](shopify-workflow.md)) when either would satisfy the ask.

## swym_internal

Swym staff -- ACQ, Success, Support, or Other. The team is asked once per
machine and reused in every later session:

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" get-profile`
   silently. If it returns a `team`, use it and don't ask.
2. Otherwise ask once: "Which Swym team are you on: ACQ, Success, Support, or
   Other?" Save the answer silently with
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/telemetry_state.py" set-profile --team <acq|success|support|other>`.
3. If the user later says they've moved teams, save the new one the same way.

Team affects framing of the output:

- **Success / ACQ** -- typically pre- or post-sale, framing implementation
  suggestions or feature walkthroughs for a merchant conversation. In
  `edit`, default to Path B (custom implementation, see
  [shopify-workflow.md](shopify-workflow.md)) as the primary approach even
  when Path A (styling Swym's own element) would technically satisfy the
  ask -- ACQ requests are typically for behavior the default UI doesn't
  support. Offer Path A only if the user asks for the simpler route or Path B
  turns out infeasible.
- **Support** -- typically `inspect` mode against an existing implementation.
  When acting for Support, end a diagnostic session with a paste-ready summary
  (root cause, confidence, fix steps, escalation target) -- see the
  inspect output shape in
  [tools-and-testing.md](tools-and-testing.md). If a fix is requested and it
  reaches `edit`, default to Path A as the primary approach --
  Support fixes are typically restoring a broken default, not building
  something custom. Only reach for Path B when Path A can't resolve it.
- **Other** -- no team-specific defaults. Choose Path A or Path B from the
  ask itself, as for `agency`.

`swym_internal` sessions may reference Swym-internal tooling or team routing
in their own output; `agency` and `merchant` sessions should not see that
detail leak into their responses.
