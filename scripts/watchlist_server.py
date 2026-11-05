import json
import os
import subprocess
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "watchlist"
PREFERENCES = ROOT / "data" / "watchlist_preferences.json"
DEFAULT_PREFERENCES = ROOT / "data" / "watchlist_defaults.json"
BOOKMARKS = ROOT / "data" / "watchlist_bookmarks.json"
DEFAULTS = {
    "version": 1,
    "targets": {"monthly_total": 100000, "area_m2": 35, "station_walk_minutes": 15, "total_commute_minutes": 90, "building_age_estimate_years": 20},
    "weights": {"budget": 15, "commute": 18, "space": 7, "layout": 6, "floor": 6, "building_age": 9, "structure": 5, "facilities": 8, "orientation": 3, "elevator": 3, "bike_parking": 2, "gas": 2, "surroundings": 7, "initial_cost": 4, "foreigner_friendly": 5, "renovation": 0},
}


def validate_preferences(data):
    if not isinstance(data, dict):
        raise ValueError()
    targets, weights = data.get("targets"), data.get("weights")
    if set(targets or {}) != set(DEFAULTS["targets"]) or set(weights or {}) != set(DEFAULTS["weights"]):
        raise ValueError()
    for key, value in targets.items():
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1_000_000:
            raise ValueError()
    for value in weights.values():
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 30:
            raise ValueError()
    return {"version": 1, "targets": targets, "weights": weights}


def validate_bookmarks(data):
    bookmarks = data.get("bookmarks") if isinstance(data, dict) else None
    notes = data.get("notes", {}) if isinstance(data, dict) else None
    if (not isinstance(bookmarks, list) or len(bookmarks) > 10_000
            or any(not isinstance(item, str) or len(item) > 200 for item in bookmarks)
            or not isinstance(notes, dict) or len(notes) > 10_000
            or any(not isinstance(key, str) or len(key) > 200 or not isinstance(note, str) or len(note) > 10_000 for key, note in notes.items())):
        raise ValueError()
    return {"bookmarks": list(dict.fromkeys(bookmarks)), "notes": notes}

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/bookmarks.json":
            body = json.dumps(json.loads(BOOKMARKS.read_text()) if BOOKMARKS.exists() else {"bookmarks": []}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path in ("/preferences.json", "/defaults.json"):
            path = PREFERENCES if self.path == "/preferences.json" else DEFAULT_PREFERENCES
            if path.exists():
                data = json.loads(path.read_text())
            else:
                data = DEFAULTS
            body = json.dumps(data).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        super().do_GET()

    def do_POST(self):
        if self.path == "/bookmarks.json":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > 2_000_000:
                    raise ValueError()
                data = validate_bookmarks(json.loads(self.rfile.read(length)))
                BOOKMARKS.parent.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile("w", dir=BOOKMARKS.parent, delete=False) as output:
                    json.dump(data, output, indent=2); output.write("\n")
                Path(output.name).replace(BOOKMARKS)
                self.send_response(204); self.end_headers(); return
            except (ValueError, json.JSONDecodeError):
                self.send_error(400, "Invalid bookmarks"); return
        if self.path not in ("/preferences.json", "/defaults.json"):
            self.send_error(404); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 10_000:
                raise ValueError()
            data = validate_preferences(json.loads(self.rfile.read(length)))
            path = PREFERENCES if self.path == "/preferences.json" else DEFAULT_PREFERENCES
            path.parent.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
                json.dump(data, output, indent=2); output.write("\n")
            Path(output.name).replace(path)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_watchlist.py")], check=True)
            self.send_response(204); self.end_headers()
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid preferences")

if __name__ == "__main__":
    os.chdir(WATCHLIST)
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("WATCHLIST_PORT", "1221"))), Handler).serve_forever()
