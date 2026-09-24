# Swym JS API (Shopify and BigCommerce storefronts)

Facts below are cross-checked against Swym's own vetted, production-tested
reference (Wishlist Plus JS SDK v3.x) for accuracy -- endpoint/method names
and parameters are not invented. Anything that reference marked as
unconfirmed or "path TBD" is marked `NEEDS VERIFICATION` here too: state that
plainly to the user rather than presenting it as settled, and check
`developers.getswym.com` (via the Swym Developer Docs MCP if connected, else
web search) before relying on it in a real implementation.

**Only use a method listed below.** If a request needs something not listed
here, look it up first -- do not guess a method name by analogy to an
existing one (e.g. don't assume a `swat.registry.*` namespace exists just
because `swat.SaveForLater.*` does).

## Supported features

| Feature | Support level | JS namespace |
|---|---|---|
| Wishlist Plus | Full | `swat.*` |
| Save For Later | Full (requires an admin toggle -- see its section) | `swat.SaveForLater.*` |
| Back In Stock (SBiSA) | Full | `swat.*` (shares the Wishlist namespace, no separate one) |
| Recently Viewed | Full, but data-fetch only -- there is no default rendered widget, you build the display UI | `swat.shopper.*` |
| B2B List | Full, but it's a custom build on Wishlist Plus, not a separately-licensed product -- confirm that framing with whoever asked before quoting it as packaged | `swat.*` (generic list API) |
| Gift Registry | Knowledge only -- standalone Shopify app, no public JS/REST/App-Embed surface | n/a |
| Recommendations ("See Similar") | Knowledge only -- support-assisted widget inside Back In Stock, not self-serve | n/a |
| Smart Save | Knowledge only -- a Dashboard behavioral toggle, not a theme customization | n/a |

For the three "Knowledge only" rows: say so plainly rather than improvising
an implementation, and point at `support@swymcorp.com` / the Swym Dashboard
as appropriate.

## Initialization

All calls are on the global `swat` object. Wrap calls needing it inside:

```javascript
window.SwymCallbacks = window.SwymCallbacks || [];
window.SwymCallbacks.push(function (swat) {
  // swat is ready here
});
```

**Never call `swat.api.*`** -- that namespace is Swym's internal product
namespace, not for custom solutions.

## Product object (used in list item operations)

```javascript
{
  epi:    /* required, variant id */,
  empi:   /* required, product id */,
  du:     /* required, canonical product URL */,
  qty:    /* optional, default 1 */,
  note:   /* optional */,
  cprops: /* optional, custom metadata, frontend-only, not synced to backend */,
  lbls:   /* optional, labels/room designations */,
  _av:    /* optional, true if the variant was auto-selected with no picker shown */,
  source: /* optional: "pdp" | "collections-grid" | "quick-view" | "featured-grid" |
            "recommendations" | "search-results" | "plp" */
}
```

## Wishlist Plus -- list management

| Method | Purpose |
|---|---|
| `swat.createList(listConfig, onSuccess, onError)` | Create or duplicate a list. `listConfig`: `{lname, lnote?, lprops?, fromlid?, lty?}`. `lname` 3-50 chars, unique per user. `lty`: `"wl"` (default) or `"sfl"`. |
| `swat.deleteList(lid, onSuccess, onError)` | Permanently delete a list. |
| `swat.updateList(listUpdateConfig, onSuccess, onError)` | Update list metadata only (`{lid, lnote?, lprops?}`) -- does not touch contents. |
| `swat.fetchLists({callbackFn, errorFn, lty?})` | Fetch all lists for the current user. Response cached 5 minutes. |
| `swat.fetchListDetails({lid}, onSuccess, onError)` | Fetch list metadata plus all items. |
| `swat.fetchListCtx({lid}, onSuccess, onError)` | Fetch list items only. |
| `swat.addToList(lid, product, onSuccess, onError)` | Add one product. |
| `swat.deleteFromList(lid, product, onSuccess, onError)` | Remove one product -- `product` needs `epi`, `empi`, `du`. |
| `swat.updateListItem(lid, product, onSuccess, onError)` | Update `qty`/`note`/`cprops`/`lbls` on an item already in a list. |
| `swat.addProductsToList(lid, products, onSuccess, onError)` | Batch add, max 10 per call. |
| `swat.removeProductsFromList(lid, products, onSuccess, onError)` | Batch remove, max 10 per call. |

## Wishlist Plus -- social count

| Method | Purpose |
|---|---|
| `swat.wishlist.getSocialCount(product, onSuccess, onError)` | `product`: `{empi}`. Returns `{count, empi}`. An unknown product returns `count: 0`, not an error -- validate `empi` before calling. |
| `swat.wishlist.getSocialCountBatch(products, onSuccess, onError)` | Batch version, array of `{empi}`. |

## Wishlist Plus -- sharing

| Method | Purpose |
|---|---|
| `swat.markListPublic(lid, successFn, errorFn)` | Enable sharing on a list. |
| `swat.generateSharedListURL(lid, callbackFn)` | Get a shareable URL. |
| `swat.sendListViaEmail({toEmailId, note, fromName, lid}, successFn, errorFn)` | Email a list. |
| `swat.shareListSocial(...)` | Social share. |

## Wishlist Plus -- misc

| Method | Purpose |
|---|---|
| `swat.platform.isLoggedIn()` | Auth check. |
| `swat.isCollectionsEnabled()` | Whether multi-list support is on. |

## Save For Later

**Prerequisite -- check before implementing, not after:** must be enabled in
Shopify Admin under Wishlist Plus > Features > Cart > "Allow shoppers to save
items before removing them from the cart." If off, `init()` silently fails to
create a usable list -- there is no error to catch.

| Method | Purpose |
|---|---|
| `swat.SaveForLater.init(onSuccess, onError)` | Call first. Creates/retrieves the `sfl`-type list. Returns `{list, items, userinfo, pagination}` -- cache the returned `lid`. |
| `swat.SaveForLater.fetch(lid, onSuccess, onError)` | Fetch all items in an existing SFL list. |
| `swat.SaveForLater.add(lid, product(s), onSuccess, onError)` | Add product(s). |
| `swat.SaveForLater.remove(...)` | Remove product(s). `NEEDS VERIFICATION` -- exact signature unconfirmed in Swym's own docs; likely `remove(lid, products, onSuccess, onError)` by analogy to `add`, but do not ship this against a real implementation without confirming it first. |

The generic `swat.updateListItem` above also works on SFL items, since both
list types share the same underlying item model.

## Back In Stock (SBiSA)

Shares the Wishlist `swat` object -- no separate namespace.

| Method | Purpose |
|---|---|
| `swat.sendWatchlist(mediumValue, medium, product, onSuccess, onError, addToMailingList?)` | Subscribe a shopper to an OOS alert. `product`: `{epi, empi, du, pr, iu}` (variant id, product id, canonical URL, price, image URL without protocol). |
| `swat.subscribeForProductAlert(mediumValue, medium, product, onSuccess, onError, addToMailingList, topic)` | Generalized version. `topic` is the fixed string `"backinstock"` or `"comingsoon"` (`"comingsoon"` fires regardless of current stock). |
| `swat.initializeActionButtons(containerSelector?)` | (Re-)binds click listeners to `[data-swaction]` elements. Call after any dynamic re-render (filtering, pagination, custom variant selectors) or new buttons won't respond. |
| `swat.ui.showSuccessNotification({message})` / `swat.ui.showErrorNotification({message})` | Generic toast helpers. |

**Enumerating App Embed blocks:** Wishlist Plus ships multiple
independently-toggled App Embed blocks in the same theme. List them before
assuming a block name or toggling one:
```bash
grep -o '"shopify://apps/[^"]*"' ./<slug>/config/settings_data.json | sort -u
```
Each block has its own `"disabled"` flag. Toggling the wrong one either does
nothing or silently enables a feature outside the current ask.

`NEEDS VERIFICATION`: the exact DOM binding shape varies by SBiSA version --
some render `[data-swaction="addToWatchlist"]` + `data-product-id` +
`product_{{ id }}` and rely on Swym's click binding; others (SBiSA "v2") render
a fully inline widget with no separate trigger, where
`initializeActionButtons()` has nothing to rebind. Confirm which shape a
given store/theme actually renders via a live DOM check before writing
selectors against it -- do not assume one shape from a single store.

## Recently Viewed (Beta)

No default rendered widget exists for this feature -- it is a pure data-fetch
API. If a merchant wants a visible carousel, that display UI is a custom
build on top of this call.

| Method | Purpose |
|---|---|
| `swat.shopper.fetchRecentlyViewedProducts(onSuccess, onError)` | Callback-based fetch of the shopper's recently viewed products, up to 12 by default. |

## B2B List (custom pattern, not a distinct SDK namespace)

All methods used are the standard Wishlist Plus methods above
(`fetchLists`, `updateListItem`, `deleteFromList`, `markListPublic`,
`generateSharedListURL`, `sendListViaEmail`, `shareListSocial`,
`platform.isLoggedIn`, `isCollectionsEnabled`). Bulk-add-to-cart and
grid/table rendering are theme-side code you write, not published SDK
methods -- there is no `swat.b2b.*` namespace.

## Platform note

**Shopify:** always get current pricing/availability from the Shopify
Storefront API before display, cart add, or checkout -- do not rely on
Swym-cached product metadata for those operations.
**BigCommerce:** use the BigCommerce REST API or Stencil context object for
the same purpose.
