"""Builds the zemaris.com pages: wraps each _pages/*.html body in the shared header and footer.

Each page starts with one line:  <!-- Title | meta description | active-nav-key -->
Run:  python website/_build.py      (GitHub Pages ignores files and folders starting with "_")

Launch switches and placeholders live in _launch.json (see LAUNCH-PREP.md):
  - checkout.open   false = every Buy button says "Coming soon" and no payment script is loaded.
  - downloads.open  false = the Download button says "Coming soon" and no file details are shown.
Both only turn on when the rest of their settings are filled in correctly; otherwise the build stops and says why.

Page sources may use:
  {{NAME}}                                  a value from _launch.json (HTML-escaped), see values() below
  <!--IF flag-->...<!--ELSE-->...<!--ENDIF-->  flags: checkout_live, downloads_live, signed, activation (and !flag)
The licence agreement and open-source notices are copied from the app with:  python _release.py --legal ..\\legal
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

NAV = [("features", "/features.html", "Features"), ("compare", "/compare.html", "Compare"),
       ("pricing", "/pricing.html", "Pricing"), ("support", "/support.html", "Support"),
       ("whatsnew", "/whats-new.html", "What's new"), ("download", "/download.html", "Download")]

PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js"
PRICE_RE = re.compile(r"^pri_[a-z0-9]{26}$")
TOKEN_RE = {"sandbox": re.compile(r"^test_[A-Za-z0-9]{10,}$"), "production": re.compile(r"^live_[A-Za-z0-9]{10,}$")}
PLANS = ("monthly", "yearly", "lifetime")

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0b1020">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="canonical" href="https://zemaris.com{path}">
<meta property="og:site_name" content="Zemaris">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://zemaris.com{path}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<link rel="stylesheet" href="/assets/style.css">
<script src="/assets/site.js" defer></script>
{extra}</head>
<body>
<a class="sr" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap">
    <a class="brand" href="/" title="Zemaris home page"><img src="/assets/zemaris-mark.svg" alt="" width="32" height="32">Zemaris</a>
    <nav class="links" aria-label="Main">{nav}</nav>
    <div class="hd-actions">
      <button class="iconbtn" id="themeBtn" title="Switch light / dark" aria-label="Switch light or dark theme">
        <svg class="theme-light-ic" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="theme-dark-ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
      <a class="btn small primary" href="/download.html" title="Go to the download page">Get Velocity</a>
      <button class="iconbtn" id="menuBtn" title="Show or hide the menu" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
    </div>
  </div>
</header>
<main id="main">
"""

FOOT = """</main>
<footer class="site">
  <div class="wrap">
    <div class="fcols">
      <div>
        <a class="brand" href="/" title="Zemaris home page"><img src="/assets/zemaris-mark.svg" alt="" width="30" height="30">Zemaris</a>
        <p>Fast, honest software. Velocity is our download manager for Windows, and Velocity PDF is coming soon.</p>
      </div>
      <div><h5>Product</h5><a href="/features.html">Features</a><a href="/compare.html">Compare</a><a href="/pricing.html">Pricing</a><a href="/whats-new.html">What's new</a><a href="/download.html">Download</a><a href="/velocity-pdf.html">Velocity PDF</a><a href="/languages.html">Languages</a></div>
      <div><h5>Help</h5><a href="/support.html">Help centre</a><a href="/support.html#troubleshoot">Troubleshooting</a><a href="/support.html#licence">Licence & activation</a><a href="/refunds.html">Refunds</a><a href="mailto:{{SUPPORT_EMAIL}}">Contact us</a></div>
      <div><h5>Company</h5><a href="/about.html">About Zemaris</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="/eula.html">Licence agreement</a><a href="/legal.html">Legal notice</a><a href="/third-party.html">Open-source notices</a><a href="mailto:{{SUPPORT_EMAIL}}">{{SUPPORT_EMAIL}}</a></div>
    </div>
    <div class="fbottom"><span>© 2026 Zemaris. All rights reserved.</span><span>No ads · No tracking · Nothing installed without asking</span></div>
  </div>
</footer>
</body>
</html>
"""


class BuildError(SystemExit):
    pass


def fail(msg):
    raise BuildError("build stopped: " + msg)


# ---------------------------------------------------------------- settings
def load_config(path=None):
    path = path or os.path.join(HERE, "_launch.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        fail(f"cannot read {os.path.basename(path)}: {e}")


def _size_text(n):
    return f"{n / 1048576:.1f} MB"


def check_checkout(cfg):
    """True when checkout may open. Stops the build when it is switched on but not filled in correctly."""
    c = cfg.get("checkout", {})
    if not c.get("open"):
        return False
    env = c.get("environment")
    if env not in TOKEN_RE:
        fail('checkout.environment must be "sandbox" or "production"')
    if not TOKEN_RE[env].match(c.get("client_token") or ""):
        fail(f"checkout.client_token must be a Paddle client-side token for {env} "
             f"(starts with {'test_' if env == 'sandbox' else 'live_'}). Never paste an API key here.")
    for plan in PLANS:
        if not PRICE_RE.match((c.get("prices") or {}).get(plan) or ""):
            fail(f"checkout.prices.{plan} must be a Paddle price id (pri_ and 26 letters/digits)")
    s = cfg.get("seller", {})
    for k in ("legal_name", "address", "governing_law", "email_sender"):
        if not (s.get(k) or "").strip():
            fail(f"seller.{k} must be filled in before checkout opens (terms, legal notice and privacy need it)")
    return True


def check_downloads(cfg, root=HERE):
    """True when the download button may show. Stops the build when switched on but incomplete or wrong."""
    d = cfg.get("downloads", {})
    if not d.get("open"):
        return False
    w = d.get("windows", {})
    base = d.get("base_url") or ""
    if not (base.startswith("https://") and base.endswith("/")):
        fail("downloads.base_url must start with https:// and end with /")
    if not re.match(r"^https://(zemaris\.com|[a-z0-9-]+(\.[a-z0-9-]+)*\.zemaris\.com|github\.com/zemaris)/", base.lower()):
        fail("downloads.base_url must be on zemaris.com (or a subdomain) or github.com/zemaris/...: the app refuses "
             "installers from other hosts (updater.py INSTALLER_HOSTS)")
    if not re.match(r"^\d+\.\d+\.\d+$", w.get("version") or ""):
        fail("downloads.windows.version must look like 1.7.2")
    if not re.match(r"^[A-Za-z0-9._-]+\.exe$", w.get("file") or ""):
        fail("downloads.windows.file must be the installer's file name")
    if not re.match(r"^[0-9a-f]{64}$", w.get("sha256") or ""):
        fail("downloads.windows.sha256 must be 64 lowercase hex characters")
    if not isinstance(w.get("size"), int) or w["size"] <= 0:
        fail("downloads.windows.size must be the file size in bytes")
    if w.get("signed") and not (w.get("publisher") or "").strip():
        fail("downloads.windows.publisher must be the name on the code-signing certificate when signed is true")
    if base.startswith("https://zemaris.com/"):
        # the file is served from this repo: it must be here and match exactly
        import hashlib
        local = os.path.join(root, *base[len("https://zemaris.com/"):].strip("/").split("/"), w["file"])
        if not os.path.isfile(local):
            fail(f"the installer is not in this repo at {os.path.relpath(local, root)} (python _release.py --stage)")
        h = hashlib.sha256()
        with open(local, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != w["sha256"] or os.path.getsize(local) != w["size"]:
            fail(f"{os.path.relpath(local, root)} does not match the SHA-256 or size in _launch.json")
        # the in-app update file goes out with the same installer, and signed (the app ignores it otherwise)
        uj = os.path.join(root, "velocity", "update.json")
        try:
            with open(uj, encoding="utf-8-sig") as f:
                m = json.load(f)
        except (OSError, ValueError):
            fail("velocity/update.json is missing or not valid JSON (python _release.py --stage)")
        if (m.get("version"), (m.get("sha256") or "").lower()) != (w["version"], w["sha256"]):
            fail("velocity/update.json names another version or file than _launch.json (python _release.py --stage)")
        if not isinstance(m.get("signature"), str) or not m["signature"]:
            fail("velocity/update.json is not signed (tools\\sign_update.py --sign, then _release.py --stage)")
    return True


def values(cfg):
    s, c, d = cfg.get("seller", {}), cfg.get("checkout", {}), cfg.get("downloads", {})
    w = d.get("windows", {})

    def v(x, placeholder):
        x = (x or "").strip()
        return x if x else placeholder

    support = v(s.get("support_email"), "admin@zemaris.com")
    out = {
        "SELLER": v(s.get("legal_name"), "[SELLER LEGAL NAME]"),
        "SELLER_ADDRESS": v(s.get("address"), "[SELLER POSTAL ADDRESS]"),
        "GOVERNING_LAW": v(s.get("governing_law"), "[GOVERNING LAW]"),
        "PRIVACY_EMAIL": v(s.get("privacy_email"), support),
        "SUPPORT_EMAIL": support,
        "EMAIL_SENDER": v(s.get("email_sender"), "[EMAIL SENDING SERVICE]"),
        "RETENTION": v(s.get("data_kept_after_licence_ends"), "[RETENTION PERIOD]"),
        "WIN_VERSION": w.get("version") or "",
        "WIN_FILE": w.get("file") or "",
        "WIN_SIZE": _size_text(w["size"]) if isinstance(w.get("size"), int) and w["size"] > 0 else "",
        "WIN_SHA256": w.get("sha256") or "",
        "WIN_URL": (d.get("base_url") or "") + (w.get("file") or ""),
        "WIN_PUBLISHER": v(w.get("publisher"), "[PUBLISHER NAME ON THE CERTIFICATE]"),
        "WIN_DATE": w.get("date") or "",
    }
    conf = {"environment": c.get("environment"), "token": c.get("client_token") or "",
            "prices": {p: (c.get("prices") or {}).get(p) or "" for p in PLANS},
            "successUrl": "https://zemaris.com/thank-you.html", "support": support, "paddleJs": PADDLE_JS}
    raw = {"CHECKOUT_JSON": json.dumps(conf).replace("<", "\\u003c").replace("&", "\\u0026")}
    return out, raw


# ---------------------------------------------------------------- templates
# innermost block first (its text holds no other IF), so blocks may be nested
COND = re.compile(r"<!--IF (!?)(\w+)-->((?:(?!<!--IF ).)*?)(?:<!--ELSE-->((?:(?!<!--IF ).)*?))?<!--ENDIF-->", re.S)
TOKEN = re.compile(r"\{\{(\w+)\}\}")


def render(text, vals, raw, flags, name):
    def cond(m):
        neg, flag, yes, no = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        if flag not in flags:
            fail(f"{name}: unknown flag {flag}")
        return yes if flags[flag] != bool(neg) else no

    while True:
        new = COND.sub(cond, text)
        if new == text:
            break
        text = new
    if "<!--IF" in text or "<!--ELSE-->" in text or "<!--ENDIF-->" in text:
        fail(f"{name}: unmatched <!--IF--> / <!--ELSE--> / <!--ENDIF-->")

    def tok(m):
        k = m.group(1)
        if k in raw:
            return raw[k]
        if k not in vals:
            fail(f"{name}: unknown value {{{{{k}}}}}")
        return html.escape(vals[k], quote=True)

    return TOKEN.sub(tok, text)


def legal_text(name, vals):
    """A text file from _legal/ (copied from the app's legal folder), placeholders filled, as safe HTML."""
    path = os.path.join(HERE, "_legal", name)
    if not os.path.isfile(path):
        fail(f"_legal/{name} is missing: run  python _release.py --legal ..\\legal")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for ph, key in (("[SELLER LEGAL NAME]", "SELLER"), ("[GOVERNING LAW]", "GOVERNING_LAW")):
        text = text.replace(ph, vals[key])
    return '<pre class="legaltext">' + html.escape(text.strip("\n"), quote=False) + "</pre>"


BTN = re.compile(r'<a\b[^>]*\bclass="[^"]*\bbtn\b[^"]*"[^>]*>|<button\b[^>]*>', re.I)
PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9 ,:/()-]{3,}\]")


def check_page(name, page):
    missing = [m.group(0)[:90] for m in BTN.finditer(page) if " title=" not in m.group(0)]
    if missing:
        fail(f"{name}: every button needs a tooltip (title=...): " + "; ".join(missing))
    if TOKEN.search(page):
        fail(f"{name}: a {{{{value}}}} was left unfilled")


def build(out_dir=None, cfg=None, quiet=False, root=HERE):
    """Builds every page into out_dir (default: this folder). Returns {page name: html}.
    root is where a zemaris.com installer is looked for (tests use a temp folder)."""
    out_dir = out_dir or HERE
    cfg = cfg if cfg is not None else load_config()
    flags = {"checkout_live": check_checkout(cfg), "downloads_live": check_downloads(cfg, root),
             "signed": bool(cfg.get("downloads", {}).get("windows", {}).get("signed")),
             "activation": bool(cfg.get("licence", {}).get("activation_server", True))}
    vals, raw = values(cfg)
    raw = dict(raw)
    src = os.path.join(HERE, "_pages")
    built, placeholders = {}, set()
    for name in sorted(os.listdir(src)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(src, name), encoding="utf-8") as f:
            text = f.read()
        m = re.match(r"<!--\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*-->\s*\n", text)
        if not m:
            fail(f"{name}: first line must be <!-- Title | description | nav -->")
        title, desc, active = m.groups()
        body = text[m.end():]
        extra = ""
        em = re.match(r"<!--HEAD\n(.*?)\nHEAD-->\s*\n", body, re.S)
        if em:
            extra, body = em.group(1) + "\n", body[em.end():]
        if "{{EULA_TEXT}}" in body:
            raw["EULA_TEXT"] = legal_text("EULA.txt", vals)
        if "{{NOTICES_TEXT}}" in body:
            raw["NOTICES_TEXT"] = legal_text("THIRD-PARTY-NOTICES.txt", vals)
        nav = "".join(f'<a href="{href}"{" class=\"on\"" if key == active else ""}>{label}</a>' for key, href, label in NAV)
        path = "/" if name == "index.html" else "/" + name
        page = HEAD.format(title=title, desc=desc, nav=nav, extra=extra, path=path) + body + FOOT
        page = render(page, vals, raw, flags, name)
        check_page(name, page)
        placeholders.update(PLACEHOLDER.findall(page))
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        built[name] = page
        if not quiet:
            print("built", name)
    if not quiet:
        print("checkout:", "OPEN (" + cfg["checkout"]["environment"] + ")" if flags["checkout_live"] else "Coming soon")
        print("downloads:", "OPEN" if flags["downloads_live"] else "Coming soon")
        if placeholders:
            print("still to fill in:", ", ".join(sorted(placeholders)))
    return built


if __name__ == "__main__":
    try:
        build()
    except BuildError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
