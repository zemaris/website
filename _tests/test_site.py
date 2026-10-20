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


def base_cfg():
    return _build.load_config()


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


class Built(unittest.TestCase):
    """The site as it is configured now (everything switched off)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zsite-")
        cls.pages = _build.build(cls.tmp, base_cfg(), quiet=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

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
        self.assertIn("[GOVERNING LAW]", t)
        self.assertIn("[SELLER LEGAL NAME]", t)
        self.assertIn("customer portal", t)
        for word in ("Cloudflare", "anonymous PC code", "[EMAIL SENDING SERVICE]", "Anthropic", "Microsoft Store"):
            self.assertIn(word, p)
        self.assertIn("14 days", self.pages["refunds.html"])
        self.assertIn('name="robots" content="noindex"', self.pages["thank-you.html"])

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
        pages = self.build(live_checkout(base_cfg()))
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
        # seller filled everywhere, escaped
        for n in ("terms.html", "legal.html", "privacy.html", "eula.html"):
            self.assertIn("Test Seller &lt;&amp;&gt;", pages[n], n)
            self.assertNotIn("[SELLER LEGAL NAME]", pages[n], n)
        self.assertIn("Testland", pages["eula.html"])
        self.assertNotIn("[GOVERNING LAW]", pages["eula.html"])
        self.assertIn("privacy@zemaris.com", pages["privacy.html"])
        self.assertNotIn("Test Seller <&>", "".join(pages.values()))
        # downloads stay closed while only checkout is open
        self.assertNotIn(".exe", pages["download.html"])

    def test_refuses_wrong_settings(self):
        good = live_checkout(base_cfg())
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
        c = copy.deepcopy(base_cfg())
        c["downloads"]["open"] = True
        c["downloads"]["base_url"] = base
        c["downloads"]["windows"].update(version="9.8.7", file="Velocity-Setup-9.8.7.exe", size=len(self.data),
                                         sha256=self.digest, date="January 2027", signed=False, publisher="")
        c["downloads"]["windows"].update(w)
        return c

    def put_file(self, data=None):
        d = os.path.join(self.tmp, "velocity", "download")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "Velocity-Setup-9.8.7.exe"), "wb") as f:
            f.write(self.data if data is None else data)

    def test_open_with_matching_file(self):
        self.put_file()
        pages = _build.build(self.out, self.cfg(), quiet=True, root=self.tmp)
        dl = pages["download.html"]
        self.assertIn('href="https://zemaris.com/velocity/download/Velocity-Setup-9.8.7.exe"', dl)
        self.assertIn(self.digest, dl)
        self.assertIn("Version 9.8.7", dl)
        self.assertIn(_build._size_text(len(self.data)), dl)
        self.assertIn("Not digitally signed yet", dl)
        self.assertNotIn("soon", dl[dl.index('data-os="windows"'):dl.index('data-os="mac"')])
        self.assertIn("Velocity-Setup-9.8.7.exe", pages["support.html"])
        self.assertIn("Current", pages["whats-new.html"])
        self.assertIn("Start 30-day free trial", pages["index.html"])
        # checkout still closed
        self.assertEqual(len(re.findall(r">Coming soon<", pages["pricing.html"])), 3)

    def test_signed(self):
        self.put_file()
        pages = _build.build(self.out, self.cfg(signed=True, publisher="Jane Example"), quiet=True, root=self.tmp)
        self.assertIn("Signed by Jane Example", pages["download.html"])
        self.assertIn("should say <b>Jane Example</b>", pages["support.html"])
        self.assertNotIn("Not digitally signed", pages["download.html"])
        with self.assertRaises(_build.BuildError):
            _build.build(self.out, self.cfg(signed=True, publisher=""), quiet=True, root=self.tmp)

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
        pages = _build.build(self.out, self.cfg(base="https://downloads.example.com/v/"), quiet=True, root=self.tmp)
        self.assertIn('href="https://downloads.example.com/v/Velocity-Setup-9.8.7.exe"', pages["download.html"])


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
        shutil.copyfile(os.path.join(SITE, "_launch.json"), os.path.join(self.root, "_launch.json"))
        self.data = b"MZ release " * 500
        with open(os.path.join(self.app, "dist", "Velocity-Setup-2.0.1.exe"), "wb") as f:
            f.write(self.data)
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data))

    def manifest(self, digest, size, url="https://zemaris.com/velocity/download/Velocity-Setup-2.0.1.exe"):
        with open(os.path.join(self.app, "dist", "update.json"), "w", encoding="utf-8") as f:
            json.dump({"version": "2.0.1", "url": url, "sha256": digest, "size": size, "notes": ""}, f)

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

    def test_stage_refuses_other_hosts(self):
        self.manifest(hashlib.sha256(self.data).hexdigest(), len(self.data), url="https://cdn.example.com/Velocity-Setup-2.0.1.exe")
        with self.assertRaises(SystemExit):
            self.run_release("--stage")


if __name__ == "__main__":
    unittest.main(verbosity=1)
