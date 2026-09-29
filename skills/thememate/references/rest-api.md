# Swym REST API (headless storefronts)

For merchants with no Shopify/BigCommerce theme -- their own frontend calls
Swym directly. Facts below are cross-checked against Swym's own vetted,
production-tested reference for accuracy. Entries marked `NEEDS
VERIFICATION` (including "path TBD" in the source material) are not
confirmed -- say so to the user and check `developers.getswym.com` (Swym
Developer Docs MCP if connected, else web search) before relying on them.
See [js-api.md](js-api.md) for the feature support-level index -- it applies
here too.

**Requires Premium plan or above.** Credentials come from Swym Admin
Settings: `pid` (store identifier) and an API key.

## Conventions

- All shopper-facing endpoints take `pid` as a query param, and `regid` +
  `sessionid` as form data.
- `Content-Type: application/x-www-form-urlencoded` for all POST/PATCH requests.
- Admin-authenticated endpoints use HTTP Basic Auth: `pid:APIKey`.
- `{{Swym API Endpoint}}` below is the merchant's actual Swym API host --
  confirm it, don't hardcode a guessed domain.

## Authentication

| HTTP | Endpoint | Purpose |
|---|---|---|
| `GET` | `{{Swym API Endpoint}}/storeadmin/me` | Verify credentials (Basic Auth). Call once to confirm setup. |
| `POST` | `{{Swym API Endpoint}}/storeadmin/v3/user/generate-regid` | Generate `regid` + `sessionid` for a shopper. Required before any other shopper-scoped endpoint. |
| `POST` | *(NEEDS VERIFICATION -- exact REST path not confirmed)* | Merge a guest session into a logged-in session after the shopper authenticates. The JS SDK's equivalent is a `guest-validate-sync` call (invoked via `callValidateSyncRegidAPI()`), which updates a guest `regid` on signup/login -- the REST path likely mirrors that name, but don't ship against a guessed path. Confirm via `developers.getswym.com` or the Swym Developer Docs MCP first. |

## List management (Wishlist)

| HTTP | Endpoint | Purpose |
|---|---|---|
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/create` | Create a list. Form: `lname` (required, 3-50 chars), `regid`, `sessionid`. Optional: `lnote`, `lty`, `lprops`, `fromlid`, `ldesc`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/delete-list` | Permanently delete a list. Form: `lid`, `regid`, `sessionid`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/update?pid={{pid}}` | Update list attributes. Form: `regid`, `sessionid`, `lid` (required). Optional: `lnote`, `lprops`, `ldesc`. Does not touch list contents. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/fetch-user-lists` | Fetch all lists for a shopper (metadata only). Form: `regid`, `sessionid`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/fetch-list-with-contents` | Fetch a list with its items. Form: `lid`, `regid`, `sessionid`. Optional: `excludeArchived`, `country`, `locale`, `currency`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/update-ctx` | Add/update/delete products in one call. Form: `lid`, `regid`, `sessionid`, `a` (add array), `u` (update array), `d` (delete array); each product needs `epi`, `empi`, `du`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/markPublic` | Mark a list publicly readable. Form: `lid`, `regid`, `sessionid`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/emailList` | Email a wishlist. Form: `lid`, `regid`, `sessionid`, `fromname`, `toemail`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/product/wishlist/social-count?pid={{pid}}` | Fetch wishlist social count for one product. Form: `empi`, `regid`, `sessionid`. Unknown product returns `count: 0` with a 200, not an error. |
| n/a | *(NEEDS VERIFICATION -- no distinct REST endpoint found in Swym's docs)* | Batch social count. The JS SDK's `swat.wishlist.getSocialCountBatch()` is documented, but its docs page only covers the JS wrapper, not a raw HTTP path -- it may simply loop the single-product endpoint above client-side rather than call a dedicated batch route. Confirm before building a headless integration around a batch REST call. |

## Save For Later (Beta -- dedicated `lists/sfl/*` namespace)

| HTTP | Endpoint | Purpose |
|---|---|---|
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/sfl/create` | Create an SFL list (`lty: "sfl"`). |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/sfl/fetch` | Fetch the SFL list + items. Form: `pid`, `regid`, `sessionid`, `user-agent`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/sfl/remove` | Delete items from the SFL list. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/sfl/update` | Update item attributes in the SFL list. |
| `POST` | `{{Swym API Endpoint}}/api/v3/lists/sfl/moved-to-cart` | Move item(s) back to cart. Returns `itemsmoved`/`itemsfailed`. |
| `POST` | *(NEEDS VERIFICATION -- listed in docs nav as "Add Items [Beta]", path not confirmed)* | Add items to the SFL list directly (as opposed to via the generic `update-ctx`-style add). |

## Back In Stock / Subscriptions (Beta)

| HTTP | Endpoint | Purpose |
|---|---|---|
| `POST` | `{{Swym API Endpoint}}/storeadmin/bispa/subscriptions/create` | Admin-authenticated (Basic Auth): create a BIS/coming-soon subscription. Form: `medium`, `mediumvalue`, `products` (stringified array of `{epi, empi, du}`), `topics`. Optional: `addtomailinglist`, `extras`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/subscriptions/fetch-subs?pid={{pid}}` | Fetch a shopper's subscriptions. Form: `regid`, `sessionid`, `topic` (e.g. `backinstock`). Optional: `medium`, `limit` (default 10), `offset` (default 0). Unauthenticated shoppers get redacted (`XXXXXX`) `mediumvalue`/`cby`/`uby` fields. |

Plan gating (from Swym's pricing page, not the developer docs): basic
manual-trigger Back In Stock is on the Free plan; Swym-managed alert emails
need Starter+; JavaScript/REST API customization needs Premium+ (same rule
as the Wishlist Lists API).

## Shopper data (Beta)

| HTTP | Endpoint | Purpose |
|---|---|---|
| `POST` | `{{Swym API Endpoint}}/api/v3/shopper/fetch-recently-viewed-products` | Query: `pid`. Form: `regid`, `sessionid`. Logged-in shoppers get full history; guests get session-scoped views only. Response: `recentlyViewed[]` with `productId`, `variantId`, `lastViewedTime`, `productURL`, `lastOrderTimestamp`, `lastOrderId`, `lastOrderedVariantId`, `count`. |
| `POST` | `{{Swym API Endpoint}}/api/v3/shopper/fetch-saved-cart-products` | Form: `regid`, `sessionid`. Products saved to cart by the shopper, up to 12 by default. |

## Feature config

| HTTP | Endpoint | Purpose |
|---|---|---|
| `POST` | `{{Swym API Endpoint}}/api/v3/config/metafields/enabled-features` | Query: `pid`. Requires a logged-in shopper. Retrieve enabled feature flags (headless only) -- check this before rendering UI for a feature. |

## B2B List pattern

No dedicated REST namespace -- it's implemented on top of the Wishlist list
endpoints above, plus the merchant's own storefront endpoints for cart
actions (e.g. Shopify's `/cart/add.js`, `/products/{handle}.js`). There is no
Swym-hosted B2B-specific endpoint.
