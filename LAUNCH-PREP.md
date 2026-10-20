# zemaris.com launch prep (branch `launch-prep`, not published)

Prepared 20 October 2026. This branch exists only on this PC. **Nothing here is on zemaris.com yet.**
Pushing it (or merging it into `main` and pushing) changes the live site at once, so that is the owner's call.
This file and `README.md` are kept off the live site by `_config.yml`.

## What changed

| Area | What | Where |
|---|---|---|
| Launch switches | One settings file. `checkout.open` and `downloads.open` are both **false**: every Buy button and the Windows download say "Coming soon". The build refuses to switch either on until its settings are complete and valid. | `_launch.json`, `_build.py` |
| Checkout | Paddle.js v2 overlay on the pricing page for Monthly, Yearly, Lifetime (Business stays "Contact us"). Paddle's script is only fetched when someone points at or clicks a Buy button, and never while checkout is off. A friendly message shows if it cannot load. | `_pages/pricing.html`, `assets/checkout.js` |
| Thank-you page | "Check your email for your key", how to activate, what to do if no email arrives. Not indexed by search engines. Paddle sends buyers here after paying. | `_pages/thank-you.html` |
| Terms | Rewritten for both apps: seller name and address (placeholders), Paddle as reseller and Merchant of Record, subscriptions and cancelling through Paddle's customer portal / paddle.net, Microsoft Store for Velocity PDF, AI features, governing law (placeholder). | `_pages/terms.html` |
| Refund policy | 14 days, full refund, how to ask, what happens to the key, Store purchases refunded by Microsoft. | `_pages/refunds.html` |
| Legal notice | Seller, address, emails, Paddle as Merchant of Record, links to all legal pages. | `_pages/legal.html` |
| Licence agreement | The installer's `legal\EULA.txt`, word for word (placeholders filled from `_launch.json` once set). | `_pages/eula.html`, `_legal/EULA.txt` |
| Open-source notices | The installer's `THIRD-PARTY-NOTICES.txt` word for word, plus a short Velocity PDF list. | `_pages/third-party.html`, `_legal/` |
| Privacy | Rewritten for both apps: activation server on Cloudflare (key + anonymous PC code), update checks, the email sender (placeholder), Paddle, Zoho mailbox, GitHub Pages, everything Velocity PDF can send (AI with your own key, OCR languages, voice model, timestamp and revocation servers, web pages), Microsoft Store, retention, rights, contact. | `_pages/privacy.html` |
| Honest text | SmartScreen help true for unsigned and signed builds, and a "check your download" (SHA-256) guide; FFmpeg described as an optional tick box (footer now "Nothing installed without asking"); "Windows · Mac & Linux in testing"; Android and iPhone "Planned"; offline-licence text matches the activation server; what's new for 1.7.1 and 1.7.2; PDF/UA claim removed ("tags and reading order for screen readers" instead). | support, features, about, index, download, whats-new, compare |
| Download page | Windows card ready behind `downloads.open`: version, date, file, size, SHA-256 with a Copy button, signed / not signed, system requirements, Download button. Filled from the release files by `_release.py`. While closed it shows "Coming soon" and no file details. | `_pages/download.html`, `_release.py` |
| Velocity PDF page | "Coming soon" product page with features checked against the code, privacy summary, Microsoft Store, price "announced at launch". Linked from the footer, the download page and About. | `_pages/velocity-pdf.html` |
| Tooltips | Every button and button-style link has a tooltip; the build stops if one is missing. | `_build.py` |
| Tests | `python _tests\test_site.py` (27 checks) and `node --test _tests\checkout.test.mjs` (7 checks). | `_tests/` |

## What the owner fills in (in `_launch.json`, then `python _build.py`)

Nothing in `_launch.json` is secret. Never put a Paddle API key, webhook secret or any password there: those go only
into the server with `wrangler secret put` (see `..\server\README.md`).

| Setting | What to put | Needed before |
|---|---|---|
| `seller.legal_name` | The seller's exact legal name, e.g. "Muhammad Asif" (the EULA in the installer must say the same) | Checkout opens |
| `seller.address` | A postal address for the legal notice and terms | Checkout opens |
| `seller.governing_law` | e.g. "the Sultanate of Oman" (same as the EULA) | Checkout opens |
| `seller.email_sender` | "ZeptoMail (by Zoho)" or "Resend", whichever sends the key emails | Checkout opens |
| `seller.privacy_email` | `admin@zemaris.com` now. Change to `privacy@zemaris.com` once that alias exists in Zoho | Any time |
| `seller.data_kept_after_licence_ends` | Suggested "2 years". Your decision | Checkout opens |
| `licence.activation_server` | `true` if the public build has ACTIVATE_URL set (planned). `false` changes the licence text to "works offline" | Downloads open |
| `checkout.environment` | `"sandbox"` to test, `"production"` for real sales | Checkout opens |
| `checkout.client_token` | Paddle > Developer Tools > Authentication > **Client-side tokens** (starts `test_` in sandbox, `live_` in live). It is meant to be public | Checkout opens |
| `checkout.prices.monthly/yearly/lifetime` | The `pri_...` ids of the three prices (the same ids as `PRICES` in the server's `wrangler.toml`) | Checkout opens |
| `checkout.open` | `true` when all of the above are set | Launch |
| `downloads.*` | Filled by Claude with `python _release.py` from the final signed build (`--stage` copies the installer and `velocity/update.json` into this repo) | Launch |
| `downloads.windows.signed/publisher` | Set by `_release.py --signed --publisher "Name on the certificate"` once builds are signed | After signing |
| `downloads.open` | `true` when you say the packages are final | Launch |

The build prints "still to fill in: ..." for every placeholder that is still visible, and stops if checkout or downloads
are switched on with something missing or wrong (bad token, an API key pasted by mistake, a wrong price id, the
installer missing from the repo or not matching its SHA-256).

## Owner steps in Paddle and elsewhere

1. Paddle > Checkout > Checkout settings: set the **default payment link** to `https://zemaris.com/pricing.html`
   (Paddle needs it before an overlay checkout opens on the site) and get `zemaris.com` approved in Paddle's website
   approval.
2. Make a client-side token (sandbox first) and send Claude the token and the three price ids, or paste them into
   `_launch.json` yourself.
3. Decide: the seller name, address and governing law (the same go into the installer's EULA, so tell Claude both);
   the retention period; whether `privacy@zemaris.com` will exist.
4. Policy points to confirm (change them if you disagree): refunds within 14 days of **each** payment, renewals
   included (the EULA says "of your purchase"); a promise to email subscribers before a price change; Yearly to
   Lifetime upgrade credit by email (already on the old pricing page).
5. Check the link to Paddle's buyer terms in the Terms (`https://www.paddle.com/legal/checkout-buyer-terms`) still
   opens, and have a lawyer read the legal pages if you want.
6. Test in the sandbox: open checkout on a local copy, buy with Paddle's test card, and check you land on the
   thank-you page and get the key email.
7. Approve the push: `git push origin launch-prep:main` (or merge into `main` and push). That publishes the site.
   Do it when the packages are final, and only after `python _tests\test_site.py` passes.

## Releasing a download manager update (from the first public build on)

1. In the Velocity code: bump the version, `build.bat`. It signs `dist\update.json` with the owner's update key
   (`private\velocity_update_key.json`, made once by the owner with `python tools\sign_update.py --new-key`). If the
   build says "update.json is NOT signed" or "app updates are OFF", stop: that build must not go public.
2. Here: `python _release.py --stage`. It refuses an update.json that is not signed with the key built into Velocity,
   and puts the installer (`velocity/download/`) and `velocity/update.json` into the same commit.
3. `python _build.py`: with downloads open it stops when the installer or a signed `velocity/update.json` for the same
   version is missing, or when the download address is not on zemaris.com, a subdomain, or github.com/zemaris/...
   (the only hosts the app accepts).
4. Owner approves the push. If the installer is hosted elsewhere (a GitHub release), upload it and check it downloads
   BEFORE update.json goes out: copies that see update.json first would fail to download the update.
5. After the push: open https://zemaris.com/velocity/update.json and the installer address in a browser.

Hosting limits: GitHub Pages allows about 1 GB per site and about 100 GB of traffic a month, and it is not meant as a
file host. Every installer committed here (about 24 MB) stays in this public repo's history for good. When downloads
grow, use GitHub releases under `zemaris` or `downloads.zemaris.com` for the installer and keep only update.json here.

Protect this repo before launch (owner): two-step sign-in on the GitHub account and branch protection on `main`.
A signed update.json means a changed file here can no longer make installed copies install anything, but the site
itself (download page, checkout) still depends on this repo.

## Not done here
- Nothing is published, no account was touched, no token or price id is real.
- The live Paddle overlay was not opened (it needs a real client token): `checkout.js` was tested with a fake Paddle
  in Node and in the built-in browser.
- Velocity PDF has no price, trial or licence agreement yet, so its page says "Coming soon" and "announced at launch",
  and the EULA page says its agreement will follow.
- Launch-list buttons are still `mailto:` links; there is no mailing-list system.
- `velocity/update.json` and the installer are not in the repo yet (`_release.py --stage` does that at launch).
