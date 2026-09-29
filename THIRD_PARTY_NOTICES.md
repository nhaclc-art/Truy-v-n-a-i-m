# Thông báo bên thứ ba

## Leaflet 1.9.4

`static/vendor/leaflet/` chứa Leaflet 1.9.4 nguyên bản (tải bằng `python -m scripts.vendor_leaflet`, kiểm hash theo SRI chính thức). Giấy phép BSD 2-Clause, toàn văn ở `static/vendor/leaflet/LICENSE`. © Volodymyr Agafonkin, © CloudMade. https://leafletjs.com

## Tesseract.js 5.1.1, tesseract.js-core 5.1.1, dữ liệu nhận dạng

`static/vendor/tesseract/` (không commit; tải bằng `python -m scripts.vendor_tesseract`, SHA-256 ghi ở `config/vendor_tesseract.lock.json`) chứa tesseract.js và tesseract.js-core 5.1.1 (Apache License 2.0, © Tesseract.js contributors; lõi biên dịch từ Tesseract OCR, Apache License 2.0, © Google và các tác giả Tesseract) cùng dữ liệu `vie`, `eng` loại 4.0.0_best_int từ gói @tesseract.js-data 1.0.0 (tessdata, Apache License 2.0). Toàn văn giấy phép tải kèm trong thư mục. https://github.com/naptha/tesseract.js

## Dữ liệu OpenStreetMap

POI có `source_type = osm` và tọa độ cơ sở lấy từ OpenStreetMap. © OpenStreetMap contributors, cấp phép Open Database License 1.0 (ODbL). `data/pois.csv` là cơ sở dữ liệu phái sinh và giữ cùng giấy phép. https://www.openstreetmap.org/copyright

## Tile bản đồ

Nền bản đồ tải trực tiếp từ `tile.openstreetmap.org` khi xem, theo Tile Usage Policy của OpenStreetMap Foundation; ứng dụng không đóng gói tile. Attribution hiển thị ở góc bản đồ.

## Chỉ đường

Tuyến đi bộ (từ mốc M3) lấy từ dịch vụ `routing.openstreetmap.de` của FOSSGIS e.V. (OSRM), dữ liệu © OpenStreetMap contributors.

## Python

Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click, blinker (BSD-3-Clause); requests (Apache-2.0); pytest (MIT). Cài qua `requirements.txt`, không đóng gói kèm.
