"""Builds the zemaris.com pages: wraps each _pages/*.html body in the shared header and footer.

Each page starts with one line:  <!-- Title | meta description | active-nav-key -->
Run:  python website/_build.py      (GitHub Pages ignores files and folders starting with "_")
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

NAV = [("features", "/features.html", "Features"), ("compare", "/compare.html", "Compare"),
       ("pricing", "/pricing.html", "Pricing"), ("support", "/support.html", "Support"),
       ("whatsnew", "/whats-new.html", "What's new"), ("download", "/download.html", "Download")]

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
    <a class="brand" href="/"><img src="/assets/zemaris-mark.svg" alt="" width="32" height="32">Zemaris</a>
    <nav class="links" aria-label="Main">{nav}</nav>
    <div class="hd-actions">
      <button class="iconbtn" id="themeBtn" title="Switch light / dark" aria-label="Switch light or dark theme">
        <svg class="theme-light-ic" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="theme-dark-ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
      <a class="btn small primary" href="/download.html">Get Velocity</a>
      <button class="iconbtn" id="menuBtn" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
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
        <a class="brand" href="/"><img src="/assets/zemaris-mark.svg" alt="" width="30" height="30">Zemaris</a>
        <p>Fast, honest software. Velocity is our download manager for Windows.</p>
      </div>
      <div><h5>Product</h5><a href="/features.html">Features</a><a href="/compare.html">Compare</a><a href="/pricing.html">Pricing</a><a href="/whats-new.html">What's new</a><a href="/download.html">Download</a><a href="/languages.html">Languages</a></div>
      <div><h5>Help</h5><a href="/support.html">Help centre</a><a href="/support.html#troubleshoot">Troubleshooting</a><a href="/support.html#licence">Licence & activation</a><a href="mailto:admin@zemaris.com">Contact us</a></div>
      <div><h5>Company</h5><a href="/about.html">About Zemaris</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="mailto:admin@zemaris.com">admin@zemaris.com</a></div>
    </div>
    <div class="fbottom"><span>© 2026 Zemaris. All rights reserved.</span><span>No ads · No tracking · No bundled software</span></div>
  </div>
</footer>
</body>
</html>
"""


def build():
    src = os.path.join(HERE, "_pages")
    for name in sorted(os.listdir(src)):
        if not name.endswith(".html"):
            continue
        text = open(os.path.join(src, name), encoding="utf-8").read()
        m = re.match(r"<!--\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*-->\s*\n", text)
        if not m:
            raise SystemExit(f"{name}: first line must be <!-- Title | description | nav -->")
        title, desc, active = m.groups()
        body = text[m.end():]
        extra = ""
        em = re.match(r"<!--HEAD\n(.*?)\nHEAD-->\s*\n", body, re.S)
        if em:
            extra, body = em.group(1) + "\n", body[em.end():]
        nav = "".join(f'<a href="{href}"{" class=\"on\"" if key == active else ""}>{label}</a>' for key, href, label in NAV)
        path = "/" if name == "index.html" else "/" + name
        html = HEAD.format(title=title, desc=desc, nav=nav, extra=extra, path=path) + body + FOOT
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        print("built", name)


if __name__ == "__main__":
    build()
