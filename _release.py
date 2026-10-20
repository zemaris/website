"""Fills the website's release details from the app's release files. It never switches anything on.

  python _release.py                       read ..\\dist\\update.json, check the installer next to it, copy ..\\legal
  python _release.py --update-json X.json --installer Velocity-Setup-1.7.2.exe
  python _release.py --signed --publisher "Name on the certificate"
  python _release.py --stage               also copy the installer to velocity/download/ and update.json to
                                           velocity/update.json in this repo (only for the zemaris.com address).
                                           Commit and push those files ONLY when the owner has said the packages
                                           are final and approved the push.

What it writes:
  _launch.json  downloads.base_url and downloads.windows (version, file, size, sha256, date, signed, publisher)
  _legal/       EULA.txt and THIRD-PARTY-NOTICES.txt, the same files the installer shows and installs
Then run  python _build.py.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)  # the Velocity repo (website/ sits inside it, git-ignored there)
SITE = "https://zemaris.com/"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(path):
    with open(path, encoding="utf-8-sig") as f:
        m = json.load(f)
    url, ver, digest, size = m.get("url", ""), m.get("version", ""), (m.get("sha256") or "").lower(), m.get("size")
    if not re.match(r"^\d+\.\d+\.\d+$", ver):
        raise SystemExit(f"{path}: version {ver!r} is not like 1.7.2")
    if not url.startswith("https://") or "/" not in url[8:]:
        raise SystemExit(f"{path}: url must be an https address of the installer")
    if not re.match(r"^[0-9a-f]{64}$", digest):
        raise SystemExit(f"{path}: sha256 must be 64 hex characters")
    if not isinstance(size, int) or size <= 0:
        raise SystemExit(f"{path}: size is missing (make it with make_manifest.ps1)")
    base, file = url.rsplit("/", 1)
    return {"version": ver, "base_url": base + "/", "file": file, "sha256": digest, "size": size}


def update_json_signed(path, app=APP):
    """True when update.json carries a valid signature by an update key built into the Velocity code at `app`
    (its updater.py UPDATE_PUBLIC_KEYS). Uses the app's own check, so the two can never disagree."""
    import importlib.util
    upd = os.path.join(app, "updater.py")
    if not os.path.isfile(upd):
        return False
    sys.path.insert(0, app)
    try:
        spec = importlib.util.spec_from_file_location("_velocity_updater_for_release", upd)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(path, encoding="utf-8-sig") as f:
            m = json.load(f)
        return isinstance(m, dict) and mod.manifest_signed(m)
    except (OSError, ValueError, ImportError, AttributeError):
        return False
    finally:
        sys.path.remove(app)


def main(argv=None, root=HERE, app=APP, today=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-json", default=os.path.join(app, "dist", "update.json"))
    ap.add_argument("--installer", help="installer file (default: next to update.json)")
    ap.add_argument("--legal", default=os.path.join(app, "legal"), help="folder with EULA.txt and THIRD-PARTY-NOTICES.txt")
    ap.add_argument("--no-release", action="store_true", help="only copy the legal texts")
    ap.add_argument("--signed", action="store_true", help="the installer is code-signed")
    ap.add_argument("--publisher", help="the name on the code-signing certificate, as Windows shows it")
    ap.add_argument("--stage", action="store_true", help="copy installer and update.json into this repo")
    a = ap.parse_args(argv)

    # legal texts
    dest = os.path.join(root, "_legal")
    os.makedirs(dest, exist_ok=True)
    for name in ("EULA.txt", "THIRD-PARTY-NOTICES.txt"):
        src = os.path.join(a.legal, name)
        if not os.path.isfile(src):
            raise SystemExit(f"{src} not found")
        shutil.copyfile(src, os.path.join(dest, name))
        print("copied", name)
    if a.no_release:
        return 0

    rel = read_manifest(a.update_json)
    installer = a.installer or os.path.join(os.path.dirname(os.path.abspath(a.update_json)), rel["file"])
    if not os.path.isfile(installer):
        raise SystemExit(f"installer not found: {installer}")
    if os.path.getsize(installer) != rel["size"] or sha256(installer) != rel["sha256"]:
        raise SystemExit(f"{installer} does not match update.json (size or SHA-256 differ): rebuild the manifest")

    cfg_path = os.path.join(root, "_launch.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    d = cfg.setdefault("downloads", {})
    w = d.setdefault("windows", {})
    d["base_url"] = rel["base_url"]
    w.update(version=rel["version"], file=rel["file"], size=rel["size"], sha256=rel["sha256"],
             date=(today or datetime.date.today()).strftime("%B %Y"))
    if a.signed:
        if not (a.publisher or w.get("publisher")):
            raise SystemExit("--signed needs --publisher (the exact name on the certificate)")
        w["signed"] = True
    if a.publisher:
        w["publisher"] = a.publisher
    with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"_launch.json: Windows {rel['version']}, {rel['size']} bytes, SHA-256 {rel['sha256']}")
    print("downloads.open is", d.get("open", False), "(this script never changes it)")

    if a.stage:
        if not rel["base_url"].startswith(SITE):
            raise SystemExit(f"--stage only works for files served from {SITE} (update.json says {rel['base_url']})")
        if not update_json_signed(a.update_json, app):
            raise SystemExit(f"{a.update_json} is not signed with the update key built into Velocity, so installed "
                             "copies would ignore it. Sign it: python tools\\sign_update.py --sign dist\\update.json")
        folder = os.path.join(root, *rel["base_url"][len(SITE):].strip("/").split("/"))
        os.makedirs(folder, exist_ok=True)
        shutil.copyfile(installer, os.path.join(folder, rel["file"]))
        os.makedirs(os.path.join(root, "velocity"), exist_ok=True)
        shutil.copyfile(a.update_json, os.path.join(root, "velocity", "update.json"))
        print("staged", os.path.relpath(os.path.join(folder, rel["file"]), root), "and velocity/update.json")
        print("Do not commit or push these until the owner says the packages are final.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
