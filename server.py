import os
import json
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from fetch_today_live_data import fetch_and_save_live_data_for_market, discover_crops, MARKET_COORDS, get_crop_market_keys
import db_manager
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8000))
DIRECTORY = os.environ.get("APP_DIR", BASE_DIR)

class MultiCropLiveDataServer(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/health" or path == "/api/health":
            self._send_json({"status": "healthy", "time": datetime.now().isoformat()})
            return

        if path == "/api/crops":
            crops = discover_crops()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "crops": crops}).encode("utf-8"))
            return

        elif path == "/api/fetch_live":
            market = query.get("market", ["Nagpur"])[0]
            crop = query.get("crop", ["mosambi"])[0]
            res = fetch_and_save_live_data_for_market(market, crop_name=crop)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        elif path == "/api/fetch_live_all":
            crop = query.get("crop", ["mosambi"])[0]
            market_keys = get_crop_market_keys(crop)
            results = []
            for mkey in market_keys:
                res = fetch_and_save_live_data_for_market(mkey, crop_name=crop)
                results.append(res)

            today_display = datetime.now().strftime("%d %b %Y")
            response_data = {
                "success": True,
                "crop": crop,
                "total_markets_updated": len(results),
                "details": results,
                "message": f"Successfully fetched & saved Today's Live Real-Time Data ({today_display}) for ALL Mandis in crop '{crop}'!"
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        # DuckDB Dedicated APIs
        elif path == "/api/db/crops":
            data = db_manager.get_crops()
            self._send_json({"success": True, "crops": data})
            return

        elif path == "/api/db/markets":
            crop = query.get("crop", [None])[0]
            data = db_manager.get_markets(crop)
            self._send_json({"success": True, "crop": crop, "markets": data})
            return

        elif path == "/api/db/latest":
            crop = query.get("crop", ["mosambi"])[0]
            data = db_manager.get_latest_prices(crop)
            self._send_json({"success": True, "crop": crop, "latest_prices": data})
            return

        elif path == "/api/db/history":
            crop = query.get("crop", ["mosambi"])[0]
            market = query.get("market", ["Maharashtra_Nagpur_Nagpur"])[0]
            limit = int(query.get("limit", [365])[0])
            data = db_manager.get_market_history(crop, market, limit)
            self._send_json({"success": True, "crop": crop, "market": market, "history": data})
            return

        elif path == "/api/db/forecasts":
            crop = query.get("crop", ["mosambi"])[0]
            market = query.get("market", ["Maharashtra_Nagpur_Nagpur"])[0]
            data = db_manager.get_market_forecasts(crop, market)
            self._send_json({"success": True, "crop": crop, "market": market, "forecasts": data})
            return

        elif path == "/api/db/arbitrage":
            crop = query.get("crop", ["mosambi"])[0]
            data = db_manager.get_arbitrage_analysis(crop)
            self._send_json({"success": True, "arbitrage": data})
            return

        elif path == "/api/db/query":
            sql = query.get("sql", ["SELECT * FROM v_latest_mandi_prices LIMIT 5"])[0]
            try:
                data = db_manager.run_analytics_query(sql)
                self._send_json({"success": True, "query": sql, "data": data})
            except Exception as ex:
                self._send_json({"success": False, "error": str(ex)}, status=400)
            return

        # Delegate static file requests to standard handler
        return super().do_GET()

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

def background_continuous_data_updater():
    """
    Background daemon worker that runs continuously when deployed in the cloud,
    fetching and storing fresh daily Mandi prices, weather, and NASA data every 24 hours.
    """
    time.sleep(15)  # wait for server to settle
    while True:
        try:
            print("[BACKGROUND SYNC] Starting scheduled continuous daily data ingestion...")
            crops = discover_crops()
            for crop in crops:
                market_keys = get_crop_market_keys(crop)
                for mkey in market_keys:
                    fetch_and_save_live_data_for_market(mkey, crop_name=crop)
            print("[BACKGROUND SYNC] Daily continuous live data ingestion completed successfully!")
        except Exception as e:
            print(f"[BACKGROUND SYNC ERROR]: {e}")
        # Run every 24 hours (86,400 seconds)
        time.sleep(86400)

def run_server():
    os.chdir(DIRECTORY)
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, MultiCropLiveDataServer)
    print(f"==================================================")
    print(f" AGRI ORACLE SERVER STARTED AT http://localhost:{PORT}")
    print(f" DuckDB & Live Scraper Engine Active")
    print(f"==================================================")

    # Start automated continuous background data ingestion daemon
    updater_thread = threading.Thread(target=background_continuous_data_updater, daemon=True)
    updater_thread.start()

    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
