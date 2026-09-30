# GeoRank HCMUE

Hệ thống truy vấn tiện ích lân cận dựa trên từ khóa và vị trí quanh cơ sở 280 An Dương Vương của Trường Đại học Sư phạm TP.HCM. Demo môn Truy vấn thông tin: dữ liệu địa điểm có nguồn → chuẩn hóa → chỉ mục đảo SQLite FTS5 → truy xuất BM25 → lọc và xếp hạng theo khoảng cách → bản đồ, danh sách, chỉ đường, geofence → đánh giá Precision@5/Recall@5.

Hướng dẫn sử dụng từng chức năng, kịch bản demo và giải thích kỹ thuật chi tiết: `HUONG_DAN.md`. Số liệu, bảng kết quả và danh sách chỗ cần sửa cho tiểu luận/slide: `SO_LIEU_BAO_CAO.md`.

## Thông tin

```text
Chủ tài khoản/tổ chức GitHub: nhaclc-art
Tên repository: Truy-v-n-a-i-m
URL repository: https://github.com/nhaclc-art/Truy-v-n-a-i-m
Học viên thực hiện: Lê Ca Nhạc
Giảng viên hướng dẫn: TS. Nguyễn Quốc Huy
Cơ sở HCMUE sử dụng: Trường Đại học Sư phạm TP.HCM, cơ sở 280 An Dương Vương
Ngày kiểm thử gần nhất: [29-09-2026]
```

Không ghi token hay mật khẩu vào file này. Trạng thái chi tiết từng tiêu chí ở mục 11.

## 1. Bài toán và phạm vi

Sinh viên cần tìm nhanh tiện ích quanh trường theo từ khóa tự do, có dấu hoặc không dấu, và theo vị trí. Phạm vi: một cơ sở, bán kính 2 km quanh điểm tham chiếu (tâm khuôn viên theo OpenStreetMap, không phải cổng), 6 danh mục: ăn uống, cửa hàng tiện lợi, văn phòng phẩm/photocopy, nhà trọ, trạm xăng, trạm xe buýt.

Bốn đầu ra: marker trên bản đồ; danh sách theo khoảng cách; chỉ đường đi bộ trong ứng dụng (có liên kết Google Maps dự phòng); geofence vào/ra vùng 100 m quanh một địa điểm.

Không làm: đặt phòng, thanh toán, đánh giá cộng đồng, tài khoản, ứng dụng di động, thông báo nền khi đóng trang, Elasticsearch/PostGIS/H3/Redis/Kafka, học xếp hạng (LTR) hay mô hình neural.

## 2. Cài đặt (Windows PowerShell)

Cần Python 3.13 (đã thử 3.13.13 trên Windows 11). Node.js 22 chỉ cần để chạy test JavaScript. Bản đồ và chỉ đường cần Internet; tìm kiếm chạy local.

Mở PowerShell tại thư mục chứa `app.py`:

```powershell
py -3.13 -m venv .venv                 # hoặc: python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Các lệnh bên dưới gọi thẳng Python trong venv nên không cần `Activate.ps1` (có máy chặn script). Nếu đã activate venv thì thay `.\.venv\Scripts\python.exe` bằng `python`.

## 3. Chạy ứng dụng

```powershell
.\.venv\Scripts\python.exe -m scripts.import_pois data\pois.csv --replace   # tạo DB + chỉ mục từ CSV
.\.venv\Scripts\python.exe app.py                                          # mở http://127.0.0.1:5000
```

DB `data/georank.db` được sinh lại từ `data/pois.csv`, không commit. Ứng dụng chỉ nghe trên `127.0.0.1`: trình duyệt coi localhost là môi trường an toàn nên định vị hoạt động.

Test và đánh giá:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/js/geofence.test.mjs
.\.venv\Scripts\python.exe -m scripts.evaluate --check-only   # kiểm nhãn đủ và đã duyệt
.\.venv\Scripts\python.exe -m scripts.evaluate                # ghi eval/results.csv, metrics.csv, summary.md
.\.venv\Scripts\python.exe -m scripts.benchmark               # đo thời gian phản hồi, ghi eval/latency.csv
.\.venv\Scripts\python.exe -m scripts.eval_whynot             # đánh giá why-not, ghi eval/whynot_*.csv, whynot_summary.md
.\.venv\Scripts\python.exe -m scripts.eval_spell              # đánh giá sửa lỗi gõ, ghi eval/spell_results.csv, spell_summary.md
.\.venv\Scripts\python.exe -m scripts.eval_voice              # đánh giá giọng nói (sau khi điền eval/voice_queries.csv)
.\.venv\Scripts\python.exe -m scripts.vendor_tesseract        # một lần: tải bộ đọc chữ (~12 MB) cho nút máy ảnh
.\.venv\Scripts\python.exe -m scripts.eval_ocr                # đánh giá tìm bằng ảnh (sau khi điền eval/ocr_cases.csv)
.\.venv\Scripts\python.exe -m scripts.check_itinerary         # kiểm tra nhanh lộ trình nhiều chặng trên dữ liệu thật (thăm dò)
```

Các con số cho báo cáo (chỉ số IR, dữ liệu, thời gian phản hồi, kiểm thử) gom trong `SO_LIEU_BAO_CAO.md`.

## 4. Thêm hoặc sửa dữ liệu (không sửa mã)

Sửa `data/pois.csv` (schema ở `data/README.md`) rồi chạy lại lệnh import. Import kiểm tra toàn bộ file trước khi ghi, có lỗi thì không ghi gì; upsert theo ID nên chạy lặp không sinh bản ghi trùng; app đang chạy thấy dữ liệu mới ở request kế tiếp; `dataset_version` đổi theo nội dung.

Ví dụ thêm một địa điểm thật (Phở Bắc Hải, OSM):

```powershell
.\.venv\Scripts\python.exe -m scripts.import_pois data\updates\them_poi_osm.csv
```

rồi tìm "pho bac hai" với bán kính 2 km. Muốn tái tạo corpus từ OpenStreetMap và giữ kết quả duyệt dữ liệu: xem `data/README.md` (fetch → build_draft → apply_review).

## 5. Cách tìm kiếm và xếp hạng

- **Chuẩn hóa** như nhau cho dữ liệu và truy vấn: Unicode NFKD, bỏ dấu, `đ → d`, chữ thường, ký tự không phải chữ/số thành khoảng trắng. Tách từ theo khoảng trắng (baseline, chưa phải tách từ tiếng Việt). Alias công khai trong `config/aliases.json`: `vpp`, `photo`, `cafe`, `coffee`, `bus`.
- **Chỉ mục đảo:** bảng SQLite FTS5 gồm tên, danh mục, mô tả, tags. Truy vấn dựng từ các token đã chuẩn hóa, nối AND; không nhận cú pháp FTS của người dùng; tham số SQL được bind.
- **BM25:** hàm `bm25()` của FTS5 với trọng số cột tên 2.0, các cột khác 1.0; giá trị càng nhỏ (càng âm) càng khớp. FTS5 kẹp IDF về gần 0 khi một từ xuất hiện trong hơn nửa corpus.
- **Khoảng cách:** Haversine, bán kính Trái Đất 6 371 008,8 m, đường chim bay. Lọc bán kính trên toàn bộ ứng viên rồi mới xếp hạng và cắt số lượng.
- **Ba chế độ xếp hạng** trên cùng tập ứng viên: gần nhất (khoảng cách, rồi ID); đúng từ khóa (BM25, rồi khoảng cách, rồi ID); kết hợp `0,6 × text_norm + 0,4 × geo_norm` với `text_norm = (−BM25)/max(−BM25)` trong lần truy vấn và `geo_norm = max(0, 1 − khoảng cách/bán kính)`. Trọng số **đặt tay, chưa huấn luyện**; đây không phải Learning to Rank. Query rỗng luôn sắp theo khoảng cách, không có điểm văn bản.
- **Bảng "Giải thích kết quả"** trong giao diện hiện query chuẩn hóa, biểu thức FTS5, số ứng viên sau từng bước lọc và các thành phần điểm của từng kết quả.
- **Vì sao không có? (why-not, phần mới cuối kỳ)**: người dùng chỉ ra một địa điểm mong đợi nhưng không có trong top 5. Hệ thống làm hai việc:
  - chẩn đoán bước đã loại địa điểm (thiếu từ khóa, khác danh mục, ngoài bán kính, xếp hạng thấp);
  - đề xuất các truy vấn sửa ít nhất để địa điểm vào top-k: bỏ/thêm/thay từ, nới bán kính, bỏ lọc danh mục, đổi cách xếp, chỉnh α tính chính xác qua giao điểm tuyến tính, tăng k.

  Đề xuất được chấm `penalty = λ·Δk + (1 − λ)·Δq` theo He & Lo (ICDE 2012) và Chen et al. (ICDE 2015, 2016), và đã được chạy lại bằng `search()` để xác nhận. API `GET /api/whynot`; code `src/whynot.py`; chi tiết `HUONG_DAN.md` mục 10A, 15A, 29A.
- **Sửa lỗi gõ (phần mới cuối kỳ)**: chỉ sửa token không có trong từ vựng của chỉ mục (lấy qua `fts5vocab`). Có ba cách sửa:
  - gộp token bị tách ("piz za");
  - tách token dính ("circlek");
  - sửa chữ theo khoảng cách Damerau–Levenshtein, tối đa 1–2 lỗi ("photocoppy", "tra suwa").

  Không sửa từ ngắn và âm tiết tiếng Việt hợp lệ. Giao diện báo "Đã hiểu … là …" và cho tìm đúng như đã gõ. Code `src/spell.py`; đánh giá `scripts.eval_spell` trên 21 biến thể gõ sai; chi tiết `HUONG_DAN.md` mục 10B, 15B, 29B.
- **Tìm bằng giọng nói (truy vấn đa phương thức)**: nút micro dùng Web Speech API của trình duyệt (tiếng Việt).
  - Câu nghe được đi qua cùng bước sửa lỗi gõ, có gộp âm tiết từ mượn ("phô tô cóp pi" → photocopy).
  - Giao diện hiện các cách nghe khác và cho tải nhật ký làm dữ liệu đánh giá (WER + chỉ số truy xuất, `scripts.eval_voice`).
  - Cần Chrome/Edge/Safari, Internet, HTTPS hoặc localhost.
  - Code `static/js/voice.js`; chi tiết `HUONG_DAN.md` mục 10C, 15C.
- **Tìm bằng ảnh biển hiệu**: nút máy ảnh đọc chữ trên ảnh bằng Tesseract.js ngay trong trình duyệt (ảnh không gửi đi).
  - Backend biến đoạn chữ dài, nhiễu thành truy vấn: sửa nhầm ký tự OCR và lỗi gõ, bỏ số, từ lạ, từ quá phổ biến, giữ từ hiếm.
  - Truy vấn được tìm kiểu OR (`match=any`), xếp BM25.
  - Cần tải bộ đọc chữ một lần: `python -m scripts.vendor_tesseract`.
  - Đánh giá `scripts.eval_ocr` so AND nguyên văn / OR không lọc / cách của hệ thống.
  - Code `static/js/ocr.js`, `src/ocr_query.py`; chi tiết `HUONG_DAN.md` mục 10E, 15D, 29C.
- **Điện thoại**: giao diện bảng trượt; micro và định vị cần HTTPS. Cách mở qua cáp USB (Android) hoặc đường hầm HTTPS tạm ở `HUONG_DAN.md` mục 10D.
- **Lập lộ trình nhiều chặng (phần mới cuối kỳ, "bản nhẹ")**: ví dụ "cà phê → ăn tối → phim" trong một ngân sách quãng đường. Khác bài toán "điểm hẹn nhiều người, một điểm gặp": ở đây một người, nhiều chặng có thứ tự.
  - Mỗi chặng là một truy vấn từ khóa (dùng lại đúng chỉ mục FTS5/BM25 và bộ sửa lỗi gõ); vét cạn tổ hợp giữa các chặng, lọc theo tổng quãng đường ước tính = Haversine × hệ số quanh co (đặt tay).
  - Bấm "Chỉ đường thật" gọi lại đúng `/api/route` (OSRM) cho từng chặng, không thêm máy chủ ngoài mới.
  - **Không** xử lý giờ chiếu phim, giờ mở cửa hay tình trạng còn chỗ; không đánh giá được bằng P@5/nDCG (không có "địa điểm liên quan" cho bài toán chọn tổ hợp). Có script kiểm tra nhanh trên dữ liệu thật thay cho đánh giá IR.
  - API `GET /api/itinerary`; code `src/itinerary.py`; chi tiết `HUONG_DAN.md` mục 10F, 15D bis, 29D.

## 6. Dữ liệu

Tại thời điểm viết (18/09/2026): `dataset_version` `ds-7ac47a589e`, 93 địa điểm (ăn uống 36, tiện lợi 11, VPP/photocopy 7, nhà trọ 2, trạm xăng 10, trạm xe buýt 27), trong đó 16 địa điểm đã đối chiếu với nguồn thứ hai. Nguồn chính là snapshot OpenStreetMap ngày 18/09/2026 (© OpenStreetMap contributors, ODbL); nhà trọ lấy từ tin đăng công khai. Nguồn, luật chọn, kết quả đối chiếu và dữ liệu chưa xác minh: `DATA_SOURCES.md`. Giờ mở cửa lấy nguyên từ nguồn, chỉ để hiển thị.

## 7. Đánh giá IR (R5)

12 truy vấn trong `eval/queries.csv` (tên riêng, danh mục, có/không dấu, một truy vấn không có đáp án). `eval/qrels.csv` gán nhãn 0/1 cho **mọi** địa điểm trong phạm vi (danh mục + bán kính) của từng truy vấn, sắp theo ID, không dựa vào thứ hạng. Nhãn do Claude soạn nháp (`labeled_by = claude-draft`) và phải được một người duyệt ký bằng:

```powershell
.\.venv\Scripts\python.exe -m scripts.sign_labels --reviewer "Họ tên người duyệt" --confirm-reviewed
```

Người duyệt: Nhaclc (18/09/2026). Kết quả trên `ds-7ac47a589e`: BM25 P@5 0,5833 / R@5 0,8654 / nDCG@5 1,0000; khoảng cách 0,5167 / 0,8048 / 0,8806; kết hợp 0,5667 / 0,8553 / 0,9838. Phân tích: `HUONG_DAN.md` mục 29. So sánh ba chế độ: A = BM25, B = khoảng cách, C = kết hợp. Chỉ số: Precision@5 (vị trí thiếu tính không liên quan), Recall@5 (chia cho tổng địa điểm liên quan trong nhãn của cả phạm vi; truy vấn không có đáp án là N/A), nDCG@5 với gain 2^rel − 1. `eval/summary.md` ghi dataset version và hash của cấu hình/nhãn. Đây là đánh giá thăm dò trên mẫu nhỏ, không có ý nghĩa thống kê.

## 8. Định vị, chỉ đường, geofence và mạng

- **Vị trí gốc** có ba chế độ luôn gắn nhãn: tâm khuôn viên (tham chiếu), vị trí thật từ trình duyệt (`watchPosition`, dừng bằng `clearWatch`), mô phỏng (bấm hoặc kéo trên bản đồ). Khi bị từ chối quyền, ứng dụng báo lỗi và không tự chuyển sang mô phỏng. Máy tính thường định vị theo Wi-Fi/IP nên sai số có thể lớn.
- **Chỉ đường:** tuyến đi bộ từ máy chủ OSRM công cộng của FOSSGIS (`routing.openstreetmap.de`), gọi khi người dùng bấm, tối đa 1 request/giây. Quãng đường và thời gian do máy chủ ước tính; khoảng cách đường chim bay hiển thị riêng. Lỗi mạng hoặc không có tuyến thì không vẽ đường giả, chỉ đưa liên kết Google Maps (chỉ đường ngoài ứng dụng).
- **Geofence:** vào vùng khi ≤ 100 m, ra khi ≥ 130 m, cần 2 mẫu liên tiếp, bỏ mẫu định vị có sai số > 50 m, cooldown thông báo 30 giây. Chế độ mô phỏng gửi 1 mẫu/giây. Chỉ hoạt động khi trang đang mở.
- **Mạng:** nền bản đồ tải từ tile OpenStreetMap khi xem, không đóng gói offline. Mất mạng sau khi trang đã tải thì tìm kiếm vẫn chạy, còn bản đồ nền và chỉ đường thì không.

## 9. Kiểm thử

Test tự động dùng dữ liệu tổng hợp trong `tests/fixtures/` (không nằm trong corpus): chuẩn hóa, Haversine, import, tìm kiếm, API, chỉ đường (giả lập máy chủ), chỉ số đánh giá, xuất ZIP, geofence (136 test Python, 9 test JavaScript). Kiểm tra thủ công trên trình duyệt và thiết bị thật: phiếu `MANUAL_CHECKS.md`. Giới hạn đã biết: `KNOWN_LIMITATIONS.md`.

## 10. Đưa source lên GitHub của người nhận

1. Người nhận tự đăng nhập GitHub, tạo repository **trống** (chưa thêm README, .gitignore hay license), đặt tên ví dụ `georank-hcmue`, chọn public/private tùy nhu cầu.
2. Giải nén `georank-hcmue-source.zip`, mở PowerShell tại thư mục chứa `app.py` và `README.md`:

   ```powershell
   git init -b main
   git add .
   git status --short
   git diff --cached --stat
   ```

3. Kiểm tra danh sách file đã stage: không có `.venv/`, file `.db`, `.env`, tài liệu gốc Word/PPT hay file giá. Sau đó (thay `YOUR_USERNAME`):

   ```powershell
   git commit -m "Initial GeoRank HCMUE demo"
   git remote add origin https://github.com/YOUR_USERNAME/georank-hcmue.git
   git remote -v
   git push -u origin main
   ```

4. Kiểm tra lại từ bản clone sạch ở thư mục khác, chạy lại mục 2, 3 và một lượt tìm kiếm, ba chế độ xếp hạng, import `data\updates\them_poi_osm.csv`, đánh giá:

   ```powershell
   git clone https://github.com/YOUR_USERNAME/georank-hcmue.git georank-hcmue-check
   cd georank-hcmue-check
   ```

Git cần danh tính và cách đăng nhập của chính người nhận; không dùng token của người khác, không `push --force` lên repo có sẵn. Đưa lên GitHub không tự triển khai Flask thành website; hosting là phạm vi khác.

## 11. Biên bản bàn giao

Cập nhật bảng này ngay trước khi xuất bản ZIP cuối. Trạng thái dưới đây ghi ngày 18/09/2026.

| Mục | Trạng thái | Bằng chứng / ghi chú |
| --- | --- | --- |
| Test tự động | PASS | `pytest`: 136 passed; `node --test tests/js/geofence.test.mjs`: 9 passed (18/09/2026) |
| R1 Cập nhật dữ liệu và chỉ mục | PASS | Test tự động PASS; import lặp không sinh trùng; ca B10 đạt (người dùng xác nhận 18/09/2026) |
| R2 Query ngoài kịch bản | PASS | Ca B3 đạt (người dùng xác nhận 18/09/2026); nên ghi lại query người kiểm tra đã chọn |
| R3 Ba chế độ xếp hạng | PASS | Test tự động PASS; ca B7 đạt; đánh giá cho thấy thứ tự khác nhau trên cùng tập ứng viên |
| R4 Kiểm tra quá trình truy vấn | PASS | Test API PASS; ca B8 đạt |
| R5 Đánh giá IR | PASS | 12 truy vấn, 232 nhãn do Nhaclc duyệt; `scripts.evaluate` chạy 18/09/2026 trên `ds-7ac47a589e`; kết quả trong `eval/` |
| Thời gian phản hồi | Cần đo lại | `scripts.benchmark` 18/09/2026: `server_ms` median 0,54 / p95 0,86 ms, nhưng đo trên `ds-b3d684c628`; đo lại sau khi import `data\pois.csv --replace` về `ds-7ac47a589e` |
| F01 Cài, import, chạy | Một phần | Chạy được trên máy phát triển; chưa thử từ ZIP sạch (F21) |
| F02–F07, F10, F16–F20 | PASS (máy tính) | Ca B1–B12 đạt, người dùng xác nhận 18/09/2026 |
| Giao diện điện thoại, modal hướng dẫn | NOT RUN | Đã làm lại sau lượt kiểm B; ca B13–B16 cần kiểm lại |
| F08, F09 Định vị thật | NOT RUN | Ca C1, C2 |
| F11, F12 Chỉ đường | Một phần | Test adapter (giả lập máy chủ) PASS; ca C3, C4 trên mạng thật chưa chạy |
| F13–F15 Geofence | Một phần | Test máy trạng thái PASS; ca C6–C8 trên giao diện chưa chạy |
| F21 Giải nén ZIP vào thư mục sạch | NOT RUN | |
| Đẩy lên GitHub và clone lại | NOT RUN | Người nhận thực hiện theo mục 10 |
