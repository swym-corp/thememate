# Common failure patterns

Check this table first in `inspect` before writing a novel diagnosis -- most
post-theme-update Swym breakage is one of these nine.

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | All Swym UI disappears (buttons, launcher, header icon, card hearts) after a theme update or duplication | Shopify resets App Embed block settings on theme duplication/update/switch | Shopify Admin > Online Store > Themes > Customize > App Embeds > App Control Centre (Wishlist Plus) > toggle "Show Swym UI" back on. Theme-level, separate from the global Swym Dashboard setting. |
| 2 | Swym elements render with wrong colors/layout after a theme update | New theme CSS targets the same selectors as the Swym override stylesheet | Add `!important` to the override rules, or raise selector specificity. |
| 3 | Custom Swym behavior (a snippet-driven feature) stops working after a theme update | The update removed the `<link>`/`<script>` include from the layout file | `grep` the layout file for the expected asset tag; re-inject if missing. |
| 4 | Scripts injected in a `page.wishlist.liquid`-style template never run | A `.json` template exists for the same page and takes priority over the `.liquid` one | Inject the script in `layout/theme.liquid` instead, guarded with `{% if page.handle contains 'wishlist' %}`. |
| 5 | Custom `SwymCallbacks` hooks never fire | A third-party script mutates/replaces `window.SwymCallbacks` before Swym loads | Ensure Swym loads first, or use the `SwymCallbacks.push` pattern so the hook runs after Swym initializes regardless of load order. |
| 6 | Card heart icons are visible but not clickable | A z-index/stacking context in the theme (common on Dawn-based themes) sits above the heart's click target | `.card__inner { position: relative; z-index: 2; }` (adjust selector to the theme's actual card wrapper). |
| 7 | A file was pushed and committed but changes don't show in `shopify theme dev`'s preview | Hot-reload's file watcher lost track of a newly added asset file | Restart `shopify theme dev`. |
| 8 | A script/style injected in `theme.liquid` has no effect on a specific template | That template declares a different layout file (multi-vertical theme, e.g. `apparel.liquid`/`cafe.liquid`) | `grep -rn '"layout"' templates/` to find every distinct layout file in use; inject into each one that needs it, not just `theme.liquid`. |
| 9 | A direct JS style write (`element.style.property = value`) runs with no error but the style never visibly changes, even after retrying with different timing/ordering | Swym's own injected stylesheet already has `!important` on that property -- not a timing/observer-ordering issue at all | Before trying a second timing hypothesis, check `getComputedStyle` and the live Swym CSS for `!important` on the target property. If present, override via a CSS asset file with matching or higher specificity instead of a JS write. |

## Live-confirmed gotcha: Back In Stock subscribe silently unreachable

On at least one live store, submitting a custom Back In Stock "Email me" form
fired a request to a merchant-side webhook (a `trycloudflare.com` tunnel)
instead of any Swym endpoint -- and the tunnel was dead
(`ERR_NAME_NOT_RESOLVED`). The shopper saw a generic error, but the real
problem was structural: the implementation routed the subscribe action
through a custom webhook instead of Swym's native endpoint, and that webhook
was a dev tunnel that had already gone offline. The form rendering correctly
proves nothing -- when auditing a Back In Stock implementation, submit a real
test alert and check the Network tab for exactly which endpoint receives the
call before declaring it working.
