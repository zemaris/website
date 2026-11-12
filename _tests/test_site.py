"""Checks for the zemaris.com build: switches, placeholders, links, scripts, legal texts and tooltips.

Run:  python _tests\\test_site.py        (offline; builds into temp folders, never into the site itself)
"""
import copy
import hashlib
import html
import html.parser
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)  # short read-and-forget opens in the tests

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.dirname(SITE)
sys.path.insert(0, SITE)
import _build  # noqa: E402
import _release  # noqa: E402

TOKEN = "test_" + "a1b2c3d4e5f6a7b8c9d0e1f2a3b"
PRICES = {"monthly": "pri_" + "a" * 26, "yearly": "pri_" + "b" * 26, "lifetime": "pri_" + "c" * 26}
SELLER = {"legal_name": "Test Seller <&>", "address": "1 Test Street, Testville", "governing_law": "Testland",
          "privacy_email": "privacy@zemaris.com", "support_email": "admin@zemaris.com", "email_sender": "TestMail"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "path",
        "circle", "rect"}


def isolate():
    """The Release tests load Velocity's own code (licence.py, and updater.py through _release.py): first the app's
    tests/isolation.py, as for every test that loads it (temp data folder; licence server, registry and the Windows
    start-up entry off). Once per run."""
    if "isolation" not in sys.modules:
        sys.path.insert(0, os.path.join(APP, "tests"))
        import isolation
        isolation.setup("zsite-iso-")


def base_cfg():
    return _build.load_config()


def closed_cfg():
    """The real settings with both launch switches off, so these checks do not depend on how _launch.json is set."""
    cfg = copy.deepcopy(base_cfg())
    cfg["checkout"]["open"] = False
    cfg["downloads"]["open"] = False
    return cfg


def live_checkout(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["seller"].update(SELLER)
    cfg["checkout"].update(open=True, environment="sandbox", client_token=TOKEN, prices=dict(PRICES))
    return cfg


class Page(html.parser.HTMLParser):
    """Collects links, scripts, ids and tag balance of one page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids, self.links, self.scripts, self.json_scripts = [], [], set(), [], [], []
        self._in_json = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.errors.append(f"duplicate id {a['id']}")
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag == "link" and "href" in a:
            self.links.append(a["href"])
        if tag == "img" and "src" in a:
            self.links.append(a["src"])
        if tag == "script":
            if "src" in a:
                self.scripts.append(a["src"])
            if a.get("type") in ("application/json", "application/ld+json"):
                self._in_json = []
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()
        if tag == "script" and self._in_json is not None:
            self.json_scripts.append("".join(self._in_json))
            self._in_json = None

    def handle_data(self, data):
        if self._in_json is not None:
            self._in_json.append(data)


def parse(text):
    p = Page()
    p.feed(text)
    p.close()
    return p


def final_section(page):
    """The end section of a page (<section class="final" id="launch">)."""
    m = re.search(r'<section class="final" id="launch">.*?</section>', page, re.S)
    return m.group(0) if m else ""


def plain(text):
    """A page or legal text as words: tags removed, entities decoded, wrapped lines joined."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text)))


def doubled(text):
    """Seller or law wording written twice ("trading as" twice in one sentence, "the laws of the laws of").
    Written apart from _build.py's own check on purpose."""
    t = plain(text).lower()
    return re.findall(r"trading as [^.]{0,80}?trading as", t) + re.findall(r"laws of (?:the )?laws of", t)


class Closed(unittest.TestCase):
    """The site with both launch switches off."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zsite-")
        cls.pages = _build.build(cls.tmp, closed_cfg(), quiet=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_switches_off_means_coming_soon_and_no_payment_script(self):
        pr = self.pages["pricing.html"]
        self.assertNotIn("data-checkout=", pr)
        self.assertNotIn("checkout.js", pr)
        self.assertNotIn("paddle.js", pr.lower())
        self.assertNotIn("checkout-config", pr)
        self.assertEqual(len(re.findall(r'class="btn[^"]*soon"[^>]*>Coming soon<', pr)), 3)
        self.assertIn("Contact us", pr)
        dl = self.pages["download.html"]
        self.assertNotIn(".exe", dl)
        self.assertNotIn("SHA-256", dl)
        self.assertIn('>Coming soon</a>', dl)
        self.assertIn("System requirements", dl)
        for name, text in self.pages.items():
            self.assertNotIn("cdn.paddle.com", text.replace('"paddleJs"', ""), name)
        for n in ("index.html", "download.html"):  # before launch the end section is still the launch list
            self.assertIn("Join the launch list", final_section(self.pages[n]), n)
            self.assertNotIn("Download free trial", self.pages[n], n)


class Built(unittest.TestCase):
    """The site as it is configured now in _launch.json."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zsite-")
        cls.pages = _build.build(cls.tmp, base_cfg(), quiet=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_launch_switches_as_configured(self):
        cfg = base_cfg()
        pr, dl = self.pages["pricing.html"], self.pages["download.html"]
        for name, text in self.pages.items():  # Paddle's script is never a page script, only loaded by checkout.js
            self.assertNotIn('src="https://cdn.paddle.com', text, name)
        if cfg["checkout"]["open"]:
            for plan in _build.PLANS:
                self.assertIn(f'data-checkout="{plan}"', pr)
            self.assertNotIn(">Coming soon<", pr)
            self.assertIn('<script src="/assets/checkout.js" defer></script>', pr)
            conf = json.loads(parse(pr).json_scripts[0])
            self.assertEqual(conf["prices"], {p: cfg["checkout"]["prices"][p] for p in _build.PLANS})
            self.assertEqual(conf["token"], cfg["checkout"]["client_token"])
            self.assertEqual(conf["environment"], cfg["checkout"]["environment"])
            self.assertIsNone(_build.PLACEHOLDER.search("\n".join(self.pages.values())))
        if cfg["downloads"]["open"]:
            d, w = cfg["downloads"], cfg["downloads"]["windows"]
            card = dl[dl.index('data-os="windows"'):dl.index('data-os="mac"')]
            self.assertNotIn("soon", card)
            self.assertIn(f'href="{d["base_url"]}{w["file"]}"', card)
            self.assertIn(w["sha256"], card)
            self.assertIn(f'Version {w["version"]}', card)
            self.assertRegex(self.pages["whats-new.html"],
                             r'Velocity (?:Download Manager )?' + re.escape(w["version"]) + r' <span class="tag new">Current</span>')
            self.assertEqual(self.pages["whats-new.html"].count('<span class="tag new">Current</span>'), 1)
            if d["base_url"].startswith("https://zemaris.com/"):
                local = os.path.join(SITE, *d["base_url"][len("https://zemaris.com/"):].strip("/").split("/"), w["file"])
                self.assertEqual(os.path.getsize(local), w["size"])
                with open(os.path.join(SITE, "velocity", "update.json"), encoding="utf-8-sig") as f:
                    self.assertEqual(json.load(f)["url"], d["base_url"] + w["file"])

    def test_every_source_page_is_built(self):
        src = sorted(n for n in os.listdir(os.path.join(SITE, "_pages")) if n.endswith(".html"))
        self.assertEqual(sorted(self.pages), src)
        for n in ("thank-you.html", "refunds.html", "legal.html", "third-party.html", "eula.html", "velocity-pdf.html"):
            self.assertIn(n, self.pages)

    def test_html_is_well_formed_and_json_parses(self):
        for name, text in self.pages.items():
            p = parse(text)
            self.assertEqual(p.errors, [], name)
            self.assertEqual(p.stack, [], f"{name}: unclosed {p.stack}")
            for j in p.json_scripts:
                json.loads(j)

    def test_local_links_scripts_and_anchors_exist(self):
        ids = {name: parse(t).ids for name, t in self.pages.items()}
        for name, text in self.pages.items():
            p = parse(text)
            for url in p.links + p.scripts:
                if re.match(r"^(https?:|mailto:)", url):
                    continue
                path, _, frag = url.partition("#")
                target = name if path == "" else path.lstrip("/") or "index.html"
                if target.endswith(".html") or path == "" or path == "/":
                    self.assertIn(target, self.pages, f"{name}: link to missing page {url}")
                    if frag:
                        self.assertIn(frag, ids[target], f"{name}: link to missing anchor {url}")
                else:
                    self.assertTrue(os.path.isfile(os.path.join(SITE, *target.split("/"))), f"{name}: missing file {url}")
            for s in p.scripts:
                self.assertTrue(s.startswith("/assets/"), f"{name}: outside script {s}")

    def test_every_button_has_a_tooltip(self):
        for name, text in self.pages.items():
            for m in _build.BTN.finditer(text):
                self.assertIn(" title=", m.group(0), f"{name}: {m.group(0)[:80]}")

    def test_no_template_left(self):
        for name, text in self.pages.items():
            self.assertNotIn("<!--IF", text, name)
            self.assertNotIn("<!--ENDIF", text, name)
            self.assertIsNone(_build.TOKEN.search(text), name)

    def test_honest_text(self):
        allt = "\n".join(self.pages.values())
        self.assertNotIn("PDF/UA", allt)
        self.assertNotIn("No bundled software", allt)
        self.assertNotIn("no bundled extras", allt)
        self.assertNotIn("installer adds automatically", allt)
        self.assertNotIn("Check the publisher is <b>Zemaris</b>", allt)
        self.assertNotIn("Velocity-Setup.exe", allt)
        self.assertNotIn("Windows, Mac &amp; Linux<", allt)
        self.assertIn("Mac &amp; Linux in testing", self.pages["index.html"])
        self.assertIn("Unknown publisher", self.pages["support.html"])
        wn = self.pages["whats-new.html"]
        self.assertIn("Velocity 1.7.2", wn)
        self.assertIn("Velocity 1.7.1", wn)
        self.assertIn("Velocity PDF", self.pages["index.html"])  # footer link
        self.assertIn('href="/velocity-pdf.html"', self.pages["download.html"])

    def test_no_competitor_names(self):
        allt = "\n".join(self.pages.values()).lower()
        for name in ("internet download manager", "idm", "acrobat", "foxit", "free download manager", "jdownloader",
                     "eagleget", "pdfelement", "nitro", "updf", "pdf-xchange"):
            self.assertIsNone(re.search(r"\b" + re.escape(name) + r"\b", allt), name)

    def test_eula_page_is_the_installer_text(self):
        src = open(os.path.join(SITE, "_legal", "EULA.txt"), encoding="utf-8").read().strip("\n")
        app = os.path.join(APP, "legal", "EULA.txt")
        if os.path.isfile(app):
            self.assertEqual(open(app, encoding="utf-8").read().strip("\n"), src, "_legal/EULA.txt is older than the app's")
        m = re.search(r'<pre class="legaltext">(.*?)</pre>', self.pages["eula.html"], re.S)
        self.assertEqual(html.unescape(m.group(1)), src)  # placeholders not filled yet, so word for word
        notices = open(os.path.join(SITE, "_legal", "THIRD-PARTY-NOTICES.txt"), encoding="utf-8").read().strip("\n")
        m = re.search(r'<pre class="legaltext">(.*?)</pre>', self.pages["third-party.html"], re.S)
        self.assertEqual(html.unescape(m.group(1)), notices)

    def test_terms_and_privacy_cover_both_apps_and_paddle(self):
        t, p = self.pages["terms.html"], self.pages["privacy.html"]
        for text in (t, p):
            self.assertIn("Velocity PDF", text)
            self.assertIn("Paddle", text)
        self.assertIn("Merchant of Record", t)
        s = base_cfg()["seller"]

        def shown(key, placeholder):  # the value from _launch.json, or its placeholder while it is empty
            v = (s.get(key) or "").strip()
            return html.escape(v, quote=True) if v else placeholder

        self.assertIn(shown("governing_law", "[GOVERNING LAW]"), t)
        self.assertIn(shown("legal_name", "[SELLER LEGAL NAME]"), t)
        self.assertIn("customer portal", t)
        for word in ("Cloudflare", "anonymous PC code", shown("email_sender", "[EMAIL SENDING SERVICE]"), "Anthropic",
                     "Microsoft Store"):
            self.assertIn(word, p)
        self.assertIn("14 days", self.pages["refunds.html"])
        self.assertIn('name="robots" content="noindex"', self.pages["thank-you.html"])

    def test_seller_and_law_are_written_once(self):
        """12 Nov 2026 the EULA, terms, privacy and legal notice said "Muhammad Asif, trading as Zemaris, trading as
        Zemaris" and "the laws of the laws of the Sultanate of Oman": the values held words the sentences add."""
        for name, text in self.pages.items():
            self.assertEqual(doubled(text), [], name)
        for path in (os.path.join(SITE, "_legal", "EULA.txt"), os.path.join(SITE, "_legal", "THIRD-PARTY-NOTICES.txt"),
                     os.path.join(APP, "legal", "EULA.txt")):
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    self.assertEqual(doubled(f.read()), [], path)
        s = base_cfg()["seller"]
        seller = (s.get("legal_name") or "").strip() or "[SELLER LEGAL NAME]"
        law = (s.get("governing_law") or "").strip() or "[GOVERNING LAW]"
        for n in ("terms.html", "privacy.html", "legal.html", "eula.html"):
            self.assertIn(f"{seller}, trading as Zemaris", plain(self.pages[n]), n)
        for n in ("terms.html", "eula.html"):
            self.assertEqual(plain(self.pages[n]).count("governed by the laws of " + law), 1, n)

    def test_new_name_in_titles_meta_and_schema(self):
        """1.7.5: the product is "Velocity Download Manager" (by Zemaris) in every product page's title, Open Graph
        title, description and the schema; the old name "Velocity by Zemaris" is left only where a page says it was
        renamed, and in the schema's alternateName."""
        for n in ("index.html", "download.html", "features.html", "compare.html", "pricing.html", "support.html",
                  "whats-new.html", "languages.html", "eula.html", "thank-you.html"):
            text = self.pages[n]
            title = html.unescape(re.search(r"<title>(.*?)</title>", text).group(1))
            self.assertIn("Velocity Download Manager", title, n)
            og = html.unescape(re.search(r'<meta property="og:title" content="([^"]*)">', text).group(1))
            self.assertEqual(og, title, n)
            desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)">', text).group(1))
            self.assertIn("Velocity Download Manager", desc, n)
        for n, text in self.pages.items():
            head = text[:text.index("<body>")]
            for m in re.finditer(r'<title>(.*?)</title>|<meta (?:name|property)="[^"]+" content="([^"]*)">', head):
                self.assertNotIn("Velocity by Zemaris", html.unescape(m.group(1) or m.group(2)), n)
            outside_legal = re.sub(r'<pre class="legaltext">.*?</pre>', "", text, flags=re.S)
            olds = outside_legal.count("Velocity by Zemaris")
            if n == "support.html":   # "called Velocity by Zemaris before version 1.7.5" (Installed apps)
                self.assertIn("called <b>Velocity by Zemaris</b> before version 1.7.5", text)
                self.assertEqual(olds, 1, n)
            elif n == "index.html":   # the schema's alternateName, so searches for the old name still find it
                self.assertEqual(olds, 1, n)
            else:
                self.assertEqual(olds, 0, n)
        schema = json.loads(parse(self.pages["index.html"]).json_scripts[0])
        self.assertEqual(schema["name"], "Velocity Download Manager")
        self.assertEqual(schema["publisher"]["name"], "Zemaris")
        home = self.pages["index.html"]
        self.assertIn("Velocity Download Manager", plain(home[home.index("<footer"):]))
        wn = self.pages["whats-new.html"]
        self.assertIn("Velocity Download Manager 1.7.5", wn)
        self.assertIn("now called <b>Velocity Download Manager</b>", wn)

    def test_download_warning_help(self):
        """A short "Seeing a warning when you download?" help: in the download page's Windows card (collapsible) and
        in support.html#smartscreen: the browser's and Windows' messages, the clicks, why, and how to check the file."""
        cfg = base_cfg()
        sp = self.pages["support.html"]
        m = re.search(r'<details id="smartscreen"><summary>Seeing a warning when you download\?</summary>(.*?)</details>',
                      sp, re.S)
        self.assertIsNotNone(m, "support.html#smartscreen")
        blocks = [("support.html", plain(m.group(1)))]
        self.assertIn('<a href="#verify">check the file</a>', m.group(1))
        self.assertIn('href="#smartscreen"', sp[:sp.index('id="start"')])   # in the page's table of contents
        if cfg["downloads"]["open"]:
            dl = self.pages["download.html"]
            card = dl[dl.index('data-os="windows"'):dl.index('data-os="mac"')]
            m = re.search(r'<details class="reqs warnhelp" id="warning-help"><summary>Seeing a warning when you download\?'
                          r'</summary>(.*?)</details>', card, re.S)
            self.assertIsNotNone(m, "download.html Windows card")
            self.assertIn('href="/support.html#verify"', m.group(1))
            self.assertIn('href="#warning-help"', card)  # the "Not digitally signed yet (what this means)" link
            blocks.append(("download.html", plain(m.group(1))))
        signed = cfg["downloads"]["windows"].get("signed")
        for n, t in blocks:
            for words in ("\"isn't commonly downloaded\"", "Keep", "\"Windows protected your PC\"", "More info",
                          "Run anyway", "new app", "SHA-256", "not a sign of a virus", "usually a few clicks"):
                self.assertIn(words, t, n)
            # each browser its own steps (second 1.7.5 review). Edge (Microsoft's own steps): the three dots next to
            # the download, Keep, then Show more, then Keep anyway: "Keep anyway" stays hidden until "Show more", and
            # clicking the download itself opens none of these
            self.assertNotIn("click the download, then", t, n)
            edge = re.search(r"In Microsoft Edge:?(.*?)In Chrome", t, re.S)
            self.assertIsNotNone(edge, f"{n}: Edge steps before Chrome's")
            e = edge.group(1)
            self.assertIn("three dots", e, n)
            self.assertIn("Show more", e, n)
            self.assertLess(e.index("Keep"), e.index("Show more"), n)
            self.assertLess(e.index("Show more"), e.index("Keep anyway"), n)
            chrome = re.search(r"In Chrome:?(.*?)In Windows", t, re.S)
            self.assertIsNotNone(chrome, f"{n}: Chrome steps before Windows'")
            for words in ("Ctrl+J", "\"isn't commonly downloaded\"", "suspicious", "Keep", "Download suspicious file"):
                self.assertIn(words, chrome.group(1), n)
            if not signed:
                self.assertIn("code-signed yet", t, n)
                self.assertIn("Code signing is on the way", t, n)
                # Smart App Control blocks an unsigned installer with no Run anyway button: say so, and where to get
                # help, without telling anyone to switch security off
                self.assertIn("Smart App Control", t, n)
                sac = t[t.index("Smart App Control"):]
                self.assertIn("no Run anyway button", sac, n)
                self.assertIn(cfg["seller"]["support_email"], sac, n)
                self.assertNotRegex(sac[:300].lower(), r"turn (it )?off|switch (it )?off|disable", n)
            else:
                self.assertNotIn("Smart App Control", t, n)

    def test_thank_you_email_subject_fits_old_and_new_server(self):
        """The key email's subject changed with 1.7.5 ("Your Velocity licence key" -> "Your Velocity Download Manager
        licence key", server/worker.js), and the site and the licence server go live at different times: the page
        names only the start both share, never one full subject."""
        ty = plain(self.pages["thank-you.html"])
        self.assertIn('subject starts with "Your Velocity"', ty)
        self.assertNotIn('"Your Velocity licence key"', ty)
        self.assertNotIn('"Your Velocity Download Manager licence key"', ty)
        worker = os.path.join(APP, "server", "worker.js")
        if os.path.isfile(worker):
            with open(worker, encoding="utf-8") as f:
                m = re.search(r"const subject = (.*?);", f.read(), re.S)   # the key email (new key, or sent again)
            self.assertIsNotNone(m, "server/worker.js: the key email's subject")
            keys = [s for s in re.findall(r'"([^"]*)"', m.group(1)) if " " in s]     # the texts, not "resend"
            self.assertTrue(keys and all("licence key" in s for s in keys), keys)
            for s in keys:
                self.assertTrue(s.startswith("Your Velocity"), s)

    def test_titles_and_descriptions_fit_search_results(self):
        """Search results show about 60 characters of a title and 160 of a description. The longer name pushed the
        home title and four descriptions past that (second 1.7.5 review)."""
        for n, text in self.pages.items():
            m = re.search(r"<title>(.*?)</title>", text)
            if m:
                self.assertLessEqual(len(html.unescape(m.group(1))), 60, n)
            d = re.search(r'<meta name="description" content="([^"]*)">', text)
            if d and "Velocity Download Manager" in html.unescape(d.group(1)):
                self.assertLessEqual(len(html.unescape(d.group(1))), 160, n)

    def test_legal_pages_changed_by_the_rename_are_dated_after_it(self):
        """A legal page whose text names "Velocity Download Manager" was changed by the 1.7.5 rename, so its "Last
        updated" date is 12 November 2026 or later (legal.html kept 20 October 2026)."""
        import datetime
        checked = []
        for n, text in self.pages.items():
            m = re.search(r'<p class="updated">Last updated: (\d{1,2} \w+ \d{4})</p>', text)
            if not m:
                continue
            body = text[text.index('<main id="main">'):text.index("</main>")]    # the page's own text, not the footer
            body = re.sub(r'<pre class="legaltext">.*?</pre>', "", body, flags=re.S)
            if "Velocity Download Manager" not in body:
                continue
            day = datetime.datetime.strptime(m.group(1), "%d %B %Y").date()
            self.assertGreaterEqual(day, datetime.date(2026, 11, 12), n)
            checked.append(n)
        self.assertIn("legal.html", checked)

    def test_narrow_screens_do_not_scroll_sideways(self):
        """At 375 px thank-you.html's two-part row and support.html's PowerShell line (#verify, which download-page
        links now open) ran 10 px past the screen. Measured in headless Edge; here only the rules that fix it."""
        with open(os.path.join(SITE, "assets", "style.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".dive > * { min-width: 0 }", css)
        self.assertRegex(css, r"\.faq code[^{]*\{ overflow-wrap: anywhere \}")
        self.assertIn("Get-FileHash", self.pages["support.html"])
        self.assertIn('class="dive', self.pages["thank-you.html"])

    def test_site_files_are_built_from_sources(self):
        """The built pages in the repo are up to date with _pages and _launch.json."""
        for name, text in self.pages.items():
            with open(os.path.join(SITE, name), encoding="utf-8") as f:
                self.assertEqual(f.read(), text, f"{name} is out of date: run python _build.py")


class Checkout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zsite-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, cfg):
        return _build.build(self.tmp, cfg, quiet=True)

    def test_live_checkout(self):
        pages = self.build(live_checkout(closed_cfg()))
        pr = pages["pricing.html"]
        for plan in ("monthly", "yearly", "lifetime"):
            self.assertIn(f'data-checkout="{plan}"', pr)
        self.assertNotIn(">Coming soon<", pr)
        self.assertIn('<script src="/assets/checkout.js" defer></script>', pr)
        conf = json.loads(parse(pr).json_scripts[0])
        self.assertEqual(conf["token"], TOKEN)
        self.assertEqual(conf["prices"], PRICES)
        self.assertEqual(conf["environment"], "sandbox")
        self.assertEqual(conf["successUrl"], "https://zemaris.com/thank-you.html")
        self.assertEqual(conf["paddleJs"], "https://cdn.paddle.com/paddle/v2/paddle.js")
        # seller filled everywhere, escaped (the EULA only where the app's EULA.txt still has the placeholder:
        # once the app fills it in, the page shows the installer's words as they are)
        with open(os.path.join(SITE, "_legal", "EULA.txt"), encoding="utf-8") as f:
            eula_src = f.read()
        for n in ("terms.html", "legal.html", "privacy.html", "eula.html"):
            if n != "eula.html" or "[SELLER LEGAL NAME]" in eula_src:
                self.assertIn("Test Seller &lt;&amp;&gt;", pages[n], n)
            self.assertNotIn("[SELLER LEGAL NAME]", pages[n], n)
        if "[GOVERNING LAW]" in eula_src:
            self.assertIn("Testland", pages["eula.html"])
        self.assertNotIn("[GOVERNING LAW]", pages["eula.html"])
        self.assertIn("privacy@zemaris.com", pages["privacy.html"])
        self.assertNotIn("Test Seller <&>", "".join(pages.values()))
        # downloads stay closed while only checkout is open
        self.assertNotIn(".exe", pages["download.html"])

    def test_refuses_wrong_settings(self):
        good = live_checkout(closed_cfg())
        bad = []
        c = copy.deepcopy(good); c["checkout"]["client_token"] = ""; bad.append(c)
        c = copy.deepcopy(good); c["checkout"]["client_token"] = "pdl_sdbx_apikey_01abcdefghijklmnopqrstuvwxyz"; bad.append(c)
        c = copy.deepcopy(good); c["checkout"]["client_token"] = "live_" + "a" * 27; bad.append(c)  # live token in sandbox
        c = copy.deepcopy(good); c["checkout"]["environment"] = "live"; bad.append(c)
        c = copy.deepcopy(good); c["checkout"]["prices"]["yearly"] = "pri_123"; bad.append(c)
        c = copy.deepcopy(good); c["checkout"]["prices"]["lifetime"] = ""; bad.append(c)
        for k in ("legal_name", "address", "governing_law", "email_sender"):
            c = copy.deepcopy(good); c["seller"][k] = ""; bad.append(c)
        for c in bad:
            with self.assertRaises(_build.BuildError):
                self.build(c)
        prod = copy.deepcopy(good)
        prod["checkout"].update(environment="production", client_token="live_" + "a" * 27)
        self.assertIn('"environment": "production"', self.build(prod)["pricing.html"])

    def test_seller_or_law_written_twice_stops_the_build(self):
        # the values of 12 Nov 2026, which the sentences already wrapped in ", trading as Zemaris" and "the laws of"
        for k, v in (("legal_name", "Muhammad Asif, trading as Zemaris"), ("governing_law", "the laws of the Sultanate of Oman")):
            c = closed_cfg()
            c["seller"][k] = v
            with self.assertRaises(_build.BuildError, msg=k):
                self.build(c)
        self.assertTrue(doubled('<b>A, trading as Zemaris</b>, trading as\nZemaris ("Zemaris"'))
        self.assertTrue(doubled("governed by the laws of the\nlaws of Oman"))
        self.assertEqual(doubled("A, trading as Zemaris. B is governed by the laws of Oman."), [])

    def test_checkout_json_cannot_break_out_of_its_script(self):
        _, raw = _build.values({"checkout": {"client_token": "</script><b>", "prices": {}}})
        self.assertNotIn("<", raw["CHECKOUT_JSON"])
        self.assertEqual(json.loads(raw["CHECKOUT_JSON"])["token"], "</script><b>")


class Downloads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zsite-")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.out)
        self.data = b"MZ fake installer " * 1000
        self.digest = hashlib.sha256(self.data).hexdigest()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cfg(self, base="https://zemaris.com/velocity/download/", **w):
        c = closed_cfg()
        c["downloads"]["open"] = True
        c["downloads"]["base_url"] = base
        c["downloads"]["windows"].update(version="9.8.7", file="Velocity-Setup-9.8.7.exe", size=len(self.data),
                                         sha256=self.digest, date="January 2027", signed=False, publisher="")
        c["downloads"]["windows"].update(w)
        return c

    def put_file(self, data=None, update=True, **uj):
        d = os.path.join(self.tmp, "velocity", "download")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "Velocity-Setup-9.8.7.exe"), "wb") as f:
            f.write(self.data if data is None else data)
        if update:
            m = {"version": "9.8.7", "url": "https://zemaris.com/velocity/download/Velocity-Setup-9.8.7.exe",
                 "sha256": self.digest, "size": len(self.data), "notes": "", "signature": "c2lnbmVk"} | uj
            with open(os.path.join(self.tmp, "velocity", "update.json"), "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in m.items() if v is not None}, f)

    def test_open_with_matching_file(self):
        self.put_file()
        pages = _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)
        dl = pages["download.html"]
        self.assertIn('href="https://zemaris.com/velocity/download/Velocity-Setup-9.8.7.exe"', dl)
        self.assertIn(self.digest, dl)
        self.assertIn("Version 9.8.7", dl)
        self.assertIn(_build._size_text(len(self.data)), dl)
        self.assertIn("Not digitally signed yet", dl)
        card = dl[dl.index('data-os="windows"'):dl.index('data-os="mac"')]
        self.assertNotIn("soon", card)
        self.assertIn("Seeing a warning when you download?", card)
        self.assertIn("isn't code-signed yet", plain(card))
        self.assertIn("Velocity-Setup-9.8.7.exe", pages["support.html"])
        self.assertIn("Current", pages["whats-new.html"])
        self.assertIn("Start 30-day free trial", pages["index.html"])
        # with downloads open the end section of home and download is a plain download button, no launch list
        # the download page's own end button downloads the installer instead of linking to itself
        for n, href in (("index.html", "/download.html"),
                        ("download.html", re.escape("https://zemaris.com/velocity/download/Velocity-Setup-9.8.7.exe"))):
            end = final_section(pages[n])
            self.assertRegex(end, r'<a class="btn primary" href="' + href + r'" title="[^"]+">(?:\s*<svg.*?</svg>)?'
                                  r'Download free trial</a>', n)
            for gone in ("launch list", "mailto:", "launches", "Join our list"):
                self.assertNotIn(gone, end, n)
            self.assertNotIn("Please%20tell%20me%20when%20Velocity%20launches", pages[n], n)
        # the macOS, Linux and phone cards ask for an email, never the launch list that no longer exists
        # (Velocity PDF and Velocity Browser cards further down keep their own launch list: not released yet)
        cards = dl[dl.index('data-os="mac"'):dl.index('data-os="ext"')]
        self.assertNotIn('href="#launch"', dl)
        self.assertNotIn("launch list", cards)
        self.assertEqual(len(re.findall(r">Email me when ready<", cards)), 4)
        # checkout still closed
        self.assertEqual(len(re.findall(r">Coming soon<", pages["pricing.html"])), 3)

    def test_signed(self):
        self.put_file()
        pages = _build.build(self.out, self.cfg(signed=True, publisher="Jane Example"), quiet=True, root=self.tmp)
        self.assertIn("Signed by Jane Example", pages["download.html"])
        self.assertIn("signed by <b>Jane Example</b>", pages["download.html"])   # the warning help
        self.assertNotIn("code-signed yet", plain(pages["download.html"]) + plain(pages["support.html"]))
        self.assertIn("should say <b>Jane Example</b>", pages["support.html"])
        self.assertNotIn("Not digitally signed", pages["download.html"])
        with self.assertRaises(_build.BuildError):
            _build.build(self.out, self.cfg(signed=True, publisher=""), quiet=True, root=self.tmp)

    def test_whats_new_current_follows_the_version_on_the_site(self):
        """The 1.7.5 entry says "Next update" until the site serves 1.7.5, then "Current" (and 1.7.4 no longer is)."""
        def entries(version):
            self.put_file(version=version)
            wn = _build.build(self.out, self.cfg(version=version), quiet=True, root=self.tmp)["whats-new.html"]
            return {v: re.search(r"<h3>Velocity (?:Download Manager )?" + re.escape(v) + r" (.*?)</h3>\s*"
                                 r'<div class="date">(.*?)</div>', wn).groups() for v in ("1.7.5", "1.7.4")}, wn
        e, wn = entries("1.7.4")
        self.assertEqual(e["1.7.5"], ('<span class="tag">Next update</span>', "Coming soon"))
        self.assertEqual(e["1.7.4"], ('<span class="tag new">Current</span>', "November 2026"))
        for v in ("1.7.5", "1.7.10", "2.0.0"):
            e, wn = entries(v)
            self.assertEqual(e["1.7.5"], ('<span class="tag new">Current</span>', "January 2027"), v)
            self.assertEqual(e["1.7.4"], ('<span class="tag">First public release</span>', "November 2026"), v)
            self.assertEqual(wn.count("Current</span>"), 1, v)
        closed = _build.build(self.out, closed_cfg(), quiet=True)["whats-new.html"]   # downloads off: nothing current
        self.assertNotIn("Current</span>", closed)
        self.assertIn('<span class="tag">Next update</span>', closed)

    def test_refuses_missing_or_wrong_file(self):
        with self.assertRaises(_build.BuildError):  # not in the repo
            _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)
        self.put_file(b"something else")
        with self.assertRaises(_build.BuildError):
            _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)
        for bad in (dict(sha256="abc"), dict(size=0), dict(version="1.7"), dict(file="x.zip")):
            self.put_file()
            with self.assertRaises(_build.BuildError):
                _build.build(self.out, self.cfg(**bad), quiet=True, root=self.tmp)
        with self.assertRaises(_build.BuildError):
            _build.build(self.out, self.cfg(base="http://zemaris.com/velocity/download/"), quiet=True, root=self.tmp)

    def test_other_https_host_needs_no_local_file(self):
        pages = _build.build(self.out, self.cfg(base="https://downloads.zemaris.com/v/"), quiet=True, root=self.tmp)
        self.assertIn('href="https://downloads.zemaris.com/v/Velocity-Setup-9.8.7.exe"', pages["download.html"])
        pages = _build.build(self.out, self.cfg(base="https://github.com/zemaris/velocity/releases/download/v9.8.7/"),
                             quiet=True, root=self.tmp)
        self.assertIn("github.com/zemaris/velocity/releases/download/v9.8.7/Velocity-Setup-9.8.7.exe", pages["download.html"])

    def test_refuses_hosts_the_app_would_refuse(self):
        for base in ("https://downloads.example.com/v/", "https://evilzemaris.com/v/", "https://github.com/someone/v/"):
            with self.assertRaises(_build.BuildError, msg=base):
                _build.build(self.out, self.cfg(base=base), quiet=True, root=self.tmp)

    def test_refuses_missing_unsigned_or_other_update_json(self):
        self.put_file(update=False)
        with self.assertRaises(_build.BuildError):
            _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)
        for bad in (dict(signature=None), dict(signature=""), dict(version="9.8.6"), dict(sha256="0" * 64)):
            self.put_file(**bad)
            with self.assertRaises(_build.BuildError, msg=str(bad)):
                _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)


class Template(unittest.TestCase):
    def r(self, text, **flags):
        f = {"a": False, "b": False}
        f.update(flags)
        return _build.render(text, {"X": "<x>"}, {"RAW": "<raw>"}, f, "t")

    def test_blocks(self):
        t = "1<!--IF a-->A<!--IF b-->B<!--ELSE-->nb<!--ENDIF--><!--ELSE-->na<!--ENDIF-->2"
        self.assertEqual(self.r(t), "1na2")
        self.assertEqual(self.r(t, a=True), "1Anb2")
        self.assertEqual(self.r(t, a=True, b=True), "1AB2")
        self.assertEqual(self.r("<!--IF !a-->off<!--ENDIF-->"), "off")
        self.assertEqual(self.r("{{X}}{{RAW}}"), "&lt;x&gt;<raw>")

    def test_release_flags(self):
        def flags(text, version, live=True):
            return _build.release_flags(text, {"downloads": {"windows": {"version": version}}}, live)
        t = "<!--IF released_1_7_5-->a<!--ENDIF--><!--IF !released_1_10_0-->b<!--ENDIF-->"
        self.assertEqual(flags(t, "1.7.4"), {"released_1_7_5": False, "released_1_10_0": False})
        self.assertEqual(flags(t, "1.7.5"), {"released_1_7_5": True, "released_1_10_0": False})
        self.assertEqual(flags(t, "1.9.0"), {"released_1_7_5": True, "released_1_10_0": False})   # numbers, not text
        self.assertEqual(flags(t, "1.10.0"), {"released_1_7_5": True, "released_1_10_0": True})
        self.assertEqual(flags(t, "2.0.0", live=False), {"released_1_7_5": False, "released_1_10_0": False})
        self.assertEqual(flags(t, ""), {"released_1_7_5": False, "released_1_10_0": False})
        self.assertEqual(flags("no flags", "1.7.5"), {})
        with self.assertRaises(_build.BuildError):   # any other unknown flag still stops the build
            self.r("<!--IF released_1_7-->x<!--ENDIF-->")

    def test_mistakes_stop_the_build(self):
        for t in ("<!--IF zz-->x<!--ENDIF-->", "<!--IF a-->x", "{{NOPE}}", "x<!--ENDIF-->"):
            with self.assertRaises(_build.BuildError):
                self.r(t)


class Release(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zrel-")
        self.root = os.path.join(self.tmp, "site")
        self.app = os.path.join(self.tmp, "app")
        os.makedirs(os.path.join(self.root))
        os.makedirs(os.path.join(self.app, "dist"))
        os.makedirs(os.path.join(self.app, "legal"))
        for n in ("EULA.txt", "THIRD-PARTY-NOTICES.txt"):
            with open(os.path.join(self.app, "legal", n), "w", encoding="utf-8") as f:
                f.write(n + " text\n")
        with open(os.path.join(self.root, "_launch.json"), "w", encoding="utf-8") as f:
            json.dump(closed_cfg(), f)  # both switches off: _release.py must never turn them on
        self.data = b"MZ release " * 500
        with open(os.path.join(self.app, "dist", "Velocity-Setup-2.0.1.exe"), "wb") as f:
            f.write(self.data)
        # the app's real update check, with a throwaway update key built into a temp copy (never the real one)
        isolate()
        import licence
        self.licence = licence
        self.priv, pub = licence.new_keypair()
        shutil.copyfile(os.path.join(APP, "licence.py"), os.path.join(self.app, "licence.py"))
        src = open(os.path.join(APP, "updater.py"), encoding="utf-8").read()
        src = re.sub(r"^UPDATE_PUBLIC_KEYS = .*$", f"UPDATE_PUBLIC_KEYS = (({pub[0]}, {pub[1]}),)", src, count=1, flags=re.M)
        with open(os.path.join(self.app, "updater.py"), "w", encoding="utf-8") as f:
            f.write(src)
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data))

    def manifest(self, digest, size, url="https://zemaris.com/velocity/download/Velocity-Setup-2.0.1.exe", signed=True):
        m = {"version": "2.0.1", "url": url, "sha256": digest, "size": size, "notes": ""}
        if signed:
            import base64
            msg = json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            m["signature"] = base64.b64encode(self.licence.sign(msg, self.priv, domain=b"VELOCITY-UPDATE-JSON\x00")).decode()
        with open(os.path.join(self.app, "dist", "update.json"), "w", encoding="utf-8") as f:
            json.dump(m, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_release(self, *args):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            return _release.main(list(args), root=self.root, app=self.app,
                                 today=__import__("datetime").date(2027, 1, 5))

    def cfg(self):
        return json.load(open(os.path.join(self.root, "_launch.json"), encoding="utf-8"))

    def test_fills_details_and_copies_legal_but_never_opens(self):
        self.run_release()
        w = self.cfg()["downloads"]["windows"]
        self.assertEqual((w["version"], w["file"], w["size"], w["date"]), ("2.0.1", "Velocity-Setup-2.0.1.exe", len(self.data), "January 2027"))
        self.assertEqual(w["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertFalse(self.cfg()["downloads"]["open"])
        self.assertFalse(self.cfg()["checkout"]["open"])
        self.assertEqual(open(os.path.join(self.root, "_legal", "EULA.txt"), encoding="utf-8").read(), "EULA.txt text\n")
        self.assertFalse(os.path.exists(os.path.join(self.root, "velocity")))

    def test_refuses_mismatch(self):
        self.manifest("0" * 64, len(self.data))
        with self.assertRaises(SystemExit):
            self.run_release()
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data), url="http://zemaris.com/x/Velocity-Setup-2.0.1.exe")
        with self.assertRaises(SystemExit):
            self.run_release()

    def test_signed_needs_publisher_and_stage_copies(self):
        with self.assertRaises(SystemExit):
            self.run_release("--signed")
        self.run_release("--signed", "--publisher", "Jane Example", "--stage")
        w = self.cfg()["downloads"]["windows"]
        self.assertTrue(w["signed"])
        self.assertEqual(w["publisher"], "Jane Example")
        staged = os.path.join(self.root, "velocity", "download", "Velocity-Setup-2.0.1.exe")
        self.assertEqual(open(staged, "rb").read(), self.data)
        self.assertEqual(json.load(open(os.path.join(self.root, "velocity", "update.json")))["version"], "2.0.1")

    def test_stage_refuses_an_unsigned_or_changed_update_json(self):
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data), signed=False)
        with self.assertRaises(SystemExit):
            self.run_release("--stage")
        self.assertFalse(os.path.exists(os.path.join(self.root, "velocity")))
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data))
        p = os.path.join(self.app, "dist", "update.json")
        m = json.load(open(p, encoding="utf-8"))
        m["notes"] = "changed after signing"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(m, f)
        with self.assertRaises(SystemExit):
            self.run_release("--stage")
        self.run_release()          # filling in the details without staging still works

    def test_stage_refuses_other_hosts(self):
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data), url="https://cdn.example.com/Velocity-Setup-2.0.1.exe")
        with self.assertRaises(SystemExit):
            self.run_release("--stage")


if __name__ == "__main__":
    unittest.main(verbosity=1)
