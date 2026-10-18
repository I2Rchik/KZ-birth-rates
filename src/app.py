"""Presentation layer: a local website (Python standard library only).

It READS data/processed/ and model/artifact.json and renders the page.
It contains no regression and estimates nothing. The model artifact is
re-read on every request, so renaming it shows a plain-language message
on the next reload.

Run:  python run.py            (then open http://127.0.0.1:8050)
"""
import csv
import json
import os
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "src", "static")
SOURCE_URL = "https://stat.gov.kz/"

_source = {"checked": False, "reachable": None}


def check_source(timeout=3):
    """Is the publisher reachable? Only used to label the data as cached/offline."""
    try:
        req = urllib.request.Request(SOURCE_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        _source["reachable"] = True
    except Exception:
        _source["reachable"] = False
    _source["checked"] = True


def read_history(processed):
    path = os.path.join(processed, "panel.csv")
    hist = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hist.setdefault(row["code"], []).append([row["quarter"], float(row["cbr"]) if row["cbr"] else None])
    return hist


def state(root=ROOT):
    """Everything the page needs, or a plain-language error."""
    processed = os.path.join(root, "data", "processed")
    art_path = os.path.join(root, "model", "artifact.json")
    out = {"ok": True, "errors": [], "source": dict(_source)}
    try:
        with open(os.path.join(processed, "meta.json"), encoding="utf-8") as f:
            out["meta"] = json.load(f)
        out["history"] = read_history(processed)
    except FileNotFoundError:
        out["ok"] = False
        out["errors"].append({"code": "missing_data",
                              "message": "Processed data not found (data/processed). "
                                         "Rebuild it with: python run.py rebuild"})
    try:
        with open(art_path, encoding="utf-8") as f:
            a = json.load(f)
        keep = ("indicator", "estimated_at", "synthetic_data", "data_warnings", "sources", "regions",
                "specification", "coefficients", "std_errors", "p_values", "covariance",
                "residual_variance", "benchmark", "falsification", "diagnostic_flags", "latest",
                "forecast", "national", "robustness", "replication_tolerance_per_1000")
        out["model"] = {k: a.get(k) for k in keep}
    except FileNotFoundError:
        out["ok"] = False
        out["errors"].append({"code": "missing_model",
                              "message": "The model is missing: model/artifact.json was not found. "
                                         "The forecast cannot be shown. Re-create it with: python run.py model"})
    except json.JSONDecodeError:
        out["ok"] = False
        out["errors"].append({"code": "bad_model",
                              "message": "model/artifact.json is damaged and cannot be read. "
                                         "Re-create it with: python run.py model"})
    return out


class Handler(BaseHTTPRequestHandler):
    root = ROOT

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if self.path == "/app.js":
                with open(os.path.join(STATIC, "app.js"), encoding="utf-8") as f:
                    return self._send(200, f.read(), "application/javascript; charset=utf-8")
            if self.path == "/api/state":
                return self._send(200, json.dumps(state(self.root)), "application/json")
            return self._send(404, "Not found", "text/plain")
        except Exception as e:  # never a stack trace in the browser
            msg = {"ok": False, "errors": [{"code": "server", "message": f"Unexpected error: {type(e).__name__}. "
                                                                        f"See the terminal for details."}]}
            print("ERROR", repr(e), file=sys.stderr)
            return self._send(200, json.dumps(msg), "application/json")


def serve(host="127.0.0.1", port=8050, root=ROOT, check=True):
    Handler.root = root
    if check:
        threading.Thread(target=check_source, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    httpd = serve(port=port)
    print(f"Serving on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()
