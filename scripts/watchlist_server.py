import json
import os
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "watchlist"
PREFERENCES = ROOT / "data" / "watchlist_preferences.json"
DEFAULTS = {
    "version": 1,
    "targets": {"monthly_total": 100000, "area_m2": 35, "station_walk_minutes": 15, "total_commute_minutes": 60, "building_age_estimate_years": 20},
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

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/preferences.json":
            if PREFERENCES.exists():
                data = json.loads(PREFERENCES.read_text())
            else:
                data = DEFAULTS
            body = json.dumps(data).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        super().do_GET()

    def do_POST(self):
        if self.path != "/preferences.json":
            self.send_error(404); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 10_000:
                raise ValueError()
            data = validate_preferences(json.loads(self.rfile.read(length)))
            PREFERENCES.parent.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=PREFERENCES.parent, delete=False) as output:
                json.dump(data, output, indent=2); output.write("\n")
            Path(output.name).replace(PREFERENCES)
            self.send_response(204); self.end_headers()
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid preferences")

if __name__ == "__main__":
    os.chdir(WATCHLIST)
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("WATCHLIST_PORT", "1221"))), Handler).serve_forever()
