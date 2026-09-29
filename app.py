"""GeoRank HCMUE: Flask phục vụ giao diện tĩnh và API tìm kiếm, chỉ đường.

Chạy: python app.py  → http://127.0.0.1:5000
"""
import mimetypes
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from src import db, routing
from src.config import ROOT, load_app_config, load_campus
from src.geo import haversine_m, valid_lat_lon
from src.importer import POI_FIELDS
from src.search import SearchError, parse_params, search
from src.itinerary import ItineraryError, parse_itinerary_params, plan
from src.ocr_query import build_ocr_query
from src.whynot import PoiNotFound, why_not

# Registry Windows đôi khi gán .js là text/plain; trình duyệt sẽ từ chối nạp ES module khi đó.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# Chặn yêu cầu chỉ đường từ điểm xuất phát quá xa phạm vi demo (tránh dùng dịch vụ công cộng vào việc khác).
MAX_ROUTE_ORIGIN_M = 10_000

# 'wasm-unsafe-eval': bộ đọc chữ Tesseract.js (static/vendor/tesseract) chạy WebAssembly trong Web Worker;
# chỉ cho biên dịch WebAssembly, không mở eval() cho JavaScript. blob: cho ảnh xem trước (ảnh không rời máy).
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'wasm-unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https://tile.openstreetmap.org; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def create_app(db_path: Path | str | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    cfg = load_app_config()
    campus = load_campus()
    labels = {c["id"]: c["label"] for c in cfg["categories"]}

    def open_db() -> sqlite3.Connection:
        # Mỗi request một kết nối mới: dữ liệu vừa import có hiệu lực ngay ở request kế tiếp.
        return db.connect(db_path)

    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        # Tile OSM yêu cầu trình duyệt gửi Referer; chính sách này chỉ gửi origin, không gửi đường dẫn/query.
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error=exc.description), exc.code
        return exc

    @app.errorhandler(sqlite3.OperationalError)
    def db_not_ready(_exc):
        return jsonify(error="DB chưa sẵn sàng; chạy python -m scripts.import_pois data/pois.csv"), 503

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        conn = open_db()
        try:
            poi_count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
            version = db.get_meta(conn, "dataset_version")
        finally:
            conn.close()
        return jsonify(status="ok", poi_count=poi_count, dataset_version=version)

    @app.get("/api/config")
    def config():
        conn = open_db()
        try:
            version = db.get_meta(conn, "dataset_version")
        finally:
            conn.close()
        routing = cfg["routing"]
        return jsonify(
            campus={
                "name": campus["name"],
                "site_name": campus["site_name"],
                "address": campus["address"],
                "reference_point": campus["reference_point"],
            },
            categories=cfg["categories"],
            search=cfg["search"],
            ranking=cfg["ranking"],
            geofence=cfg["geofence"],
            whynot={"k": cfg["whynot"]["k"], "lambda": cfg["whynot"]["lambda"]},
            itinerary={k: v for k, v in cfg["itinerary"].items() if k != "note"},
            ocr={"search_radius_m": cfg["ocr"]["search_radius_m"], "max_text_chars": cfg["ocr"]["max_text_chars"]},
            routing={
                "mode_label": routing["mode_label"],
                "attribution": routing["attribution"],
                "fix_the_map_url": routing["fix_the_map_url"],
            },
            map=cfg["map"],
            dataset_version=version,
        )

    @app.get("/api/search")
    def search_endpoint():
        try:
            params = parse_params(request.args, cfg, campus["reference_point"])
        except SearchError as exc:
            return jsonify(error=str(exc)), 400
        conn = open_db()
        try:
            return jsonify(search(conn, params, cfg))
        finally:
            conn.close()

    @app.get("/api/pois")
    def poi_list():
        # Danh sách gọn để người dùng chỉ ra địa điểm mong đợi khi hỏi "Vì sao không có?".
        conn = open_db()
        try:
            rows = conn.execute("SELECT id, name, category, address, lat, lon FROM pois ORDER BY name, id").fetchall()
        finally:
            conn.close()
        return jsonify(
            items=[{**dict(r), "category_label": labels.get(r["category"], r["category"])} for r in rows]
        )

    @app.get("/api/ocr-query")
    def ocr_query_endpoint():
        # Nhận chữ đã đọc trong trình duyệt (không nhận ảnh), trả truy vấn đã lọc kèm lý do bỏ từng từ.
        text = request.args.get("text", "")
        if not text.strip():
            return jsonify(error="thiếu text"), 400
        if len(text) > cfg["ocr"]["max_text_chars"]:
            return jsonify(error=f"text tối đa {cfg['ocr']['max_text_chars']} ký tự"), 400
        conn = open_db()
        try:
            return jsonify(build_ocr_query(conn, text, cfg))
        finally:
            conn.close()

    @app.get("/api/itinerary")
    def itinerary_endpoint():
        try:
            params = parse_itinerary_params(request.args, cfg, campus["reference_point"])
        except ItineraryError as exc:
            return jsonify(error=str(exc)), 400
        conn = open_db()
        try:
            return jsonify(plan(conn, cfg, params))
        finally:
            conn.close()

    @app.get("/api/whynot")
    def whynot_endpoint():
        try:
            params = parse_params(request.args, cfg, campus["reference_point"])
        except SearchError as exc:
            return jsonify(error=str(exc)), 400
        poi_id = request.args.get("poi_id", "")
        if not poi_id:
            return jsonify(error="thiếu poi_id"), 400
        k_raw = request.args.get("k") or str(cfg["whynot"]["k"])
        try:
            k = int(k_raw)
        except ValueError:
            return jsonify(error="k phải là số nguyên"), 400
        if not 1 <= k <= cfg["search"]["max_limit"]:
            return jsonify(error=f"k phải từ 1 đến {cfg['search']['max_limit']}"), 400
        conn = open_db()
        try:
            return jsonify(why_not(conn, params, poi_id, cfg, k))
        except PoiNotFound:
            return jsonify(error="không tìm thấy POI"), 404
        finally:
            conn.close()

    @app.get("/api/pois/<poi_id>")
    def poi_detail(poi_id: str):
        conn = open_db()
        try:
            row = conn.execute("SELECT * FROM pois WHERE id = ?", (poi_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return jsonify(error="không tìm thấy POI"), 404
        poi = {name: row[name] for name in POI_FIELDS}
        poi["category_label"] = labels.get(poi["category"], poi["category"])
        return jsonify(poi)

    @app.get("/api/route")
    def route_endpoint():
        try:
            from_lat = float(request.args.get("from_lat", ""))
            from_lon = float(request.args.get("from_lon", ""))
        except ValueError:
            return jsonify(error="from_lat và from_lon phải là số"), 400
        if not valid_lat_lon(from_lat, from_lon):
            return jsonify(error="from_lat/from_lon ngoài miền hợp lệ"), 400
        poi_id = request.args.get("poi_id", "")
        if not poi_id:
            return jsonify(error="thiếu poi_id"), 400

        conn = open_db()
        try:
            poi = conn.execute("SELECT id, name, lat, lon FROM pois WHERE id = ?", (poi_id,)).fetchone()
        finally:
            conn.close()
        if poi is None:
            return jsonify(error="không tìm thấy POI"), 404
        straight_m = haversine_m(from_lat, from_lon, poi["lat"], poi["lon"])
        if straight_m > MAX_ROUTE_ORIGIN_M:
            return jsonify(error=f"điểm xuất phát cách POI hơn {MAX_ROUTE_ORIGIN_M // 1000} km"), 400

        routing_cfg = cfg["routing"]
        payload = {
            "poi": {"id": poi["id"], "name": poi["name"], "lat": poi["lat"], "lon": poi["lon"]},
            "from": {"lat": from_lat, "lon": from_lon},
            "straight_distance_m": straight_m,
            "mode_label": routing_cfg["mode_label"],
            "provider": routing_cfg["provider"],
            "attribution": routing_cfg["attribution"],
            "fix_the_map_url": routing_cfg["fix_the_map_url"],
            "google_maps_url": routing.google_maps_url(from_lat, from_lon, poi["lat"], poi["lon"]),
        }
        routing.wait_for_slot()
        try:
            payload["route"] = routing.fetch_route(routing_cfg, from_lat, from_lon, poi["lat"], poi["lon"])
        except routing.RoutingError as exc:
            return jsonify({"error": str(exc), "code": exc.code, **payload}), exc.status
        return jsonify(payload)

    return app


if __name__ == "__main__":
    # Chỉ nghe trên localhost: trình duyệt coi localhost là secure context nên Geolocation hoạt động.
    create_app().run(host="127.0.0.1", port=5000, debug=False)
