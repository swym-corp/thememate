# Other platforms (knowledge-only)

Per SKILL.md Section 3, every platform except Shopify gets suggestions and
knowledge only -- never a theme/store pull, edit, or push. This file is the
per-platform detail behind that gate.

## Headless (Swym REST API)

A merchant with no theme in the Shopify sense -- their own frontend calls
Swym's REST API directly. `inspect` and `edit` both stay advisory:
describe which REST endpoint(s) are involved (see
[rest-api.md](rest-api.md)) and what the calling code should do, but there is
no ThemeMate-owned file to pull or push -- the merchant's own engineering
team makes the change in their codebase.

## BigCommerce

Delivered via BigCommerce's Script Manager, not a ThemeMate-managed file pull.
Advisory only: describe what script/snippet to add or change, and where in
Script Manager it goes. Do not claim to have access to pull or push
BigCommerce theme files -- that capability doesn't exist in this skill.

## WooCommerce / Wix

Knowledge-only. Answer conceptual and API questions; do not describe a
pull/edit/push workflow for these platforms since none exists here.

## What "advisory only" means in practice

- `ask` -- answer normally, grounded in
  [rest-api.md](rest-api.md) / [js-api.md](js-api.md).
- `inspect` -- ask enough questions (or, for headless, request relevant
  request/response payloads) to form a plain-language hypothesis of the
  cause; state your confidence; suggest what to check or change. Never
  imply you inspected files you don't have access to.
- `edit` -- say plainly that direct implementation isn't
  supported for this platform, then give the same kind of description
  `ask` would: which API to call, with what shape, and where
  that logic likely belongs in the merchant's own stack.
