# zemaris.com

Website of Zemaris, maker of Velocity. Pages are generated: edit `_pages/*.html`, then run `python _build.py`.

- `_launch.json`: launch switches (checkout, downloads) and the seller details. See `LAUNCH-PREP.md`.
- `python _release.py`: fills the download details from the app's `dist\update.json` and copies the licence
  agreement and open-source notices from the app's `legal` folder into `_legal/`.
- Tests: `python _tests\test_site.py` and `node --test _tests\checkout.test.mjs`.
- GitHub Pages never publishes files or folders starting with `_`; `_config.yml` also keeps this README and
  LAUNCH-PREP.md off the site.
