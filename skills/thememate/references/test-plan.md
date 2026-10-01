# Test plan

Every Shopify edit plan carries a test plan (SKILL.md Section 4), and every
edit runs it to the end (SKILL.md Section 5). This file says how to write the
test plan, which scenarios it must cover, and how to probe them so a `PASS`
means the storefront actually works.

## What the plan contains

Put these two parts in the plan you present for confirmation, after the file
list and the approach.

**Test plan.** One row per scenario:

| ID | What it proves | Setup | Steps | Expected | Evidence |
|---|---|---|---|---|---|
| T1 | A guest sees the new element with the right data | Guest; 2 test items seeded | Load the page | The element shows both items | `evaluate()` output of the element's text and item count |

Write each row so another agent can run it without reading the others. Name
the environment the plan runs on (see "Where to test" below).

**What I need from you.** Every input you cannot get yourself, asked up front:

| Need | Why | What the user does |
|---|---|---|
| Logged-in customer | The feature shows only to logged-in shoppers | Log in in ThemeMate's Chrome when asked |
| A Swym setting on | The new code reads a setting that is off on this store | Turn it on in the Swym app |

If nothing is needed, say so. Check every setting the new code reads on the
live storefront before the plan (for example `_swat.retailerSettings`), so a
setting that is off shows up here, not halfway through the build.

## Scenario matrix

Go through every row. Add scenarios for each row that applies to the change,
and say in one line why a row does not apply. Do not stop at the happy path.

| Dimension | Scenarios to add |
|---|---|
| Shopper | Guest and logged in, for every state the code branches on |
| Data | Empty, one item, many items, and past any page or batch limit the code uses |
| Settings the code reads | Each Swym or theme setting on, off, and absent |
| Each action | It works once, it works twice in a row, and the result is still there after a reload (read it back from the Swym API, not only the DOM) |
| Sequences | Quick repeated input, back and forth between views, and an action while a load is still running |
| Time | Cold load from first paint to settled, and a throttled network. Record state over time, not one snapshot |
| Screen size | Each breakpoint the theme uses (read them from the CSS), at least one phone width |
| Regression | Each existing feature on the same page still works |
| Negative case | The old wrong behaviour is gone |
| Reference UI | When the ask copies Swym's default UI, the same data gives the same result on both pages |
| Console | No new errors compared with a baseline taken before the edit |
| Cleanup | Every test item, cart line, and list entry you created is removed at the end |

## Where to test

1. Local preview (`shopify theme dev`) first, when Swym runs there.
2. Swym does not always run on `127.0.0.1:9292`. Before you trust a local
   result, check that the Swym API calls the change uses return real data
   there, not empty results or errors.
3. When Swym cannot run locally, ask the user before pushing, and let them
   pick an unpublished theme or create a new one (see "Local preview and
   verify loop" in [shopify-workflow.md](shopify-workflow.md)). Then test on
   `https://<store-domain>/<path>?preview_theme_id=<id>`. Say in the result
   table that the results came from the preview theme. Pushing an unpublished
   theme to test is not the same as calling the work done.

## How to probe

- **Use real interactions.** Click with the browser tool (`page.click`), not
  by calling the page's functions. A direct call skips the event path that
  breaks.
- **Record state over time.** For anything async (load, view change, add,
  remove), poll the relevant state every 20 to 100 ms from the action until
  it settles, and keep only the changes. One snapshot misses a flash of the
  wrong state.
- **Use a fresh tab for each run.** Init scripts and wrapped functions from
  an earlier probe stay on a tab and change what you measure.
- **Check persistence through the API.** After an add, remove, move or
  clear, reload and read the list back with the Swym JS API.
- **Wait for images before a screenshot.** A screenshot taken while cards
  load looks like a layout bug.
- **Seed test data with the Swym JS API**, and keep a list of every item, list
  entry and cart line you create. Remove them at the end and report what you
  removed.
- **Say how test data was made.** When you seed data directly instead of
  through the shopper flow that normally creates it, say so in the result
  table.

## Help from the user

Ask with AskUserQuestion, and name the exact action. Use this for:

- **Logins.** Open the store's login page in ThemeMate's Chrome and ask the
  user to log in there with a test customer account. Never ask for a
  password or a login code in chat. The login stays for the rest of the
  session on that store.
- **Store and app settings** that only the merchant can change (App Embeds,
  Swym dashboard settings).
- **Design decisions** the request does not settle.

Mark the scenarios that wait on the user as `BLOCKED` and run them as soon as
the user confirms.

## Result table

Report after each full run (SKILL.md Section 5):

| ID | Result | Evidence |
|---|---|---|
| T1 | PASS | Probe output: the element shows 2 items |
| T4 | FAIL | Probe output: the empty state shows before the items load |
| T6 | BLOCKED | Needs a Swym setting turned on by the merchant |

`PASS` needs probe output from the running storefront. A unit test, a clean
`shopify theme check`, or an HTTP 200 alone is not a pass.
