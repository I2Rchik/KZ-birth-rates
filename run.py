"""One entry point for everything.

  python run.py                 start the website (http://127.0.0.1:8050)
  python run.py rebuild         data/raw -> data/processed -> model/artifact.json + outputs/
  python run.py check           rebuild, then verify the headline numbers reproduce within tolerance
  python run.py test            run the automated tests
  python run.py ingest | model  run one layer only
  python run.py register-raw FILE --series births --url URL --id SERIES_ID [--publisher NAME]
                                copy a downloaded file into data/raw and record it in the manifest
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))


def cmd_serve(args):
    import webbrowser
    import app
    httpd = app.serve(port=args.port)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Serving {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopped")


def cmd_ingest(args):
    import ingest
    try:
        p = ingest.build()
    except ingest.DataError as e:
        sys.exit(f"DATA ERROR: {e}")
    print(f"data/processed rebuilt: {p.code.nunique()} regions, {p.quarter.min()}-{p.quarter.max()}")


def cmd_model(args):
    import model
    import report
    a = model.run()
    report.write()
    b = a["benchmark"]
    print(f"model/artifact.json written. Hold-out RMSE model {b['rmse_model']:.3f} vs benchmark "
          f"{b['rmse_benchmark']:.3f} (ratio {b['rmse_ratio']:.3f}): {b['winner']} wins.")


def cmd_rebuild(args):
    cmd_ingest(args)
    cmd_model(args)


def cmd_check(args):
    """Re-run the whole pipeline and compare the headline numbers with the
    committed artifact. Passes if every regional forecast and the national
    forecast reproduce within the stated tolerance."""
    path = os.path.join(ROOT, "model", "artifact.json")
    with open(path, encoding="utf-8") as f:
        before = json.load(f)
    cmd_rebuild(args)
    with open(path, encoding="utf-8") as f:
        after = json.load(f)
    tol = before["replication_tolerance_per_1000"]
    bad = []
    for c, fc in before["forecast"].items():
        if fc.get("available"):
            d = abs(fc["forecast_level"] - after["forecast"][c]["forecast_level"])
            if d > tol:
                bad.append(f"{c}: {d:.4f}")
    nb, na = before["national"].get("forecast"), after["national"].get("forecast")
    if nb and na and abs(nb["value"] - na["value"]) > tol:
        bad.append(f"national: {abs(nb['value'] - na['value']):.4f}")
    if bad:
        sys.exit("CHECK FAILED (difference per 1,000 above tolerance): " + ", ".join(bad))
    print(f"CHECK PASSED: all headline forecasts reproduce within ±{tol} births per 1,000.")


def cmd_test(args):
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if r.wasSuccessful() else 1)


def cmd_register(args):
    raw = os.path.join(ROOT, "data", "raw")
    os.makedirs(raw, exist_ok=True)
    name = os.path.basename(args.file)
    dest = os.path.join(raw, name)
    if os.path.exists(dest):
        sys.exit(f"data/raw/{name} already exists. Raw files are written once; give the new download a new name.")
    shutil.copy2(args.file, dest)
    with open(dest, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    mpath = os.path.join(raw, "manifest.json")
    manifest = {"files": []}
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            manifest = json.load(f)
    manifest["files"].append({
        "series": args.series, "file": name, "sha256": digest,
        "publisher": args.publisher, "url": args.url, "identifier": args.id,
        "retrieved": args.retrieved or dt.date.today().isoformat(),
        "revised": args.revised, "navigation": args.navigation,
    })
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"registered data/raw/{name} as '{args.series}'. Add the same details to data/raw/SOURCES.md.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="serve",
                    choices=["serve", "ingest", "model", "rebuild", "check", "test", "register-raw"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8050")))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--series")
    ap.add_argument("--url", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--publisher", default="Bureau of National Statistics of the Republic of Kazakhstan")
    ap.add_argument("--retrieved")
    ap.add_argument("--revised", default="yes: operational monthly data are revised when annual data are final")
    ap.add_argument("--navigation", default="")
    args = ap.parse_args()
    if args.command == "register-raw" and not (args.file and args.series):
        ap.error("register-raw needs FILE and --series")
    {"serve": cmd_serve, "ingest": cmd_ingest, "model": cmd_model, "rebuild": cmd_rebuild,
     "check": cmd_check, "test": cmd_test, "register-raw": cmd_register}[args.command](args)


if __name__ == "__main__":
    main()
