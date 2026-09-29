# Số liệu và bằng chứng cho báo cáo

Tài liệu này gom các con số, bảng và nhận xét cần đưa vào chương kết quả của tiểu luận và slide. Mọi số liệu lấy từ bản bàn giao: dataset `ds-7ac47a589e`, đánh giá chạy lúc 2026-09-18 12:03:28 UTC. Cột "Nguồn" chỉ file để kiểm lại. Nếu dữ liệu hoặc nhãn thay đổi, chạy lại lệnh tương ứng và cập nhật; khi trích số trong báo cáo nên ghi kèm phiên bản dataset.

Cách dùng hệ thống và giải thích kỹ thuật chi tiết: `HUONG_DAN.md`. Giới hạn: `KNOWN_LIMITATIONS.md`.

## 1. Thông tin phiên bản

| Mục | Giá trị | Nguồn |
| --- | --- | --- |
| Phiên bản dữ liệu | `ds-7ac47a589e` | `eval/summary.md`, góc trên giao diện |
| Snapshot OpenStreetMap | Tải 2026-09-18 08:11:56 UTC, dữ liệu OSM đến 08:10:36 UTC, 1 592 phần tử trong bán kính 2 km | `data/raw/*.meta.json` (không kèm ZIP), `DATA_SOURCES.md` |
| Hash cấu hình tìm kiếm / queries / qrels | `4a28ca34dbfd` / `e0d390d9c4b5` / `e14ea1588df5` | `eval/summary.md` |
| Người duyệt nhãn | Tran Dat, 18/09/2026 | `eval/qrels.csv` |
| Test tự động | 136 test Python + 9 test JavaScript, tất cả đạt (18/09/2026) | `README.md` mục 11 |

## 2. Dữ liệu

### Quy mô corpus

| Danh mục | Số địa điểm |
| --- | ---: |
| Ăn uống | 36 |
| Trạm xe buýt | 27 |
| Cửa hàng tiện lợi | 11 |
| Trạm xăng | 10 |
| Văn phòng phẩm / photocopy | 7 |
| Nhà trọ | 2 |
| **Tổng trong chỉ mục** | **93** |

Nguồn: 91 địa điểm từ OpenStreetMap, 2 nhà trọ từ tin đăng công khai (phongtro123). Phạm vi: bán kính 2 km quanh tâm khuôn viên cơ sở 280 An Dương Vương (10.761357, 106.6821769, theo OSM). Nguồn: `data/pois.csv`, log import.

### Mức kiểm chứng

| Trạng thái | Số lượng | Ý nghĩa |
| --- | ---: | --- |
| Đã đối chiếu nguồn thứ hai (`cross_checked`) | 16 | 9 qua Foody/bài đăng của quán, 7 do người kiểm tra tra Google Maps |
| Chỉ có một nguồn (`source_only`) | 77 | Chủ yếu trạm xe buýt, trạm xăng, cửa hàng tiện lợi |
| Kiểm tra tại chỗ (`field_checked`) | 0 | |
| Bị loại vì sai (`uncertain`) | 1 | Không đưa vào chỉ mục |

Nguồn: `data/pois.csv`, `data/review_sheet.csv`.

### Phát hiện về chất lượng dữ liệu (dùng cho phần thảo luận)

- Một nhà hàng bị OSM đặt sai vị trí khoảng **490 m** (Út Cà Mau: OSM có hai điểm cùng tên, một điểm nằm trong khối trường học); đã sửa theo Foody và điểm OSM thứ hai.
- Một quán cơm tấm bị đặt **sai phía đường** (địa chỉ đúng 417 An Dương Vương); đã sửa.
- **6 quán sát trường** (trong 300 m) **không có tên** trong OSM; tên được bổ sung qua Google Maps.
- 1 nhà hàng chay có thông tin sai, bị loại.
- Một cửa hàng Circle K không có trong dữ liệu vì được gắn tag khác chuẩn; đã thêm luật nhận theo tên chuỗi cửa hàng.
- Luật chọn ban đầu (tối đa 4 quán mỗi vòng bán kính) bỏ sót quán gần trường; luật cuối lấy hết mọi địa điểm trong 500 m.

Kết luận có thể viết: dữ liệu mở dùng được cho demo nhưng cần bước đối chiếu; "lấy từ nguồn thật" không đồng nghĩa "đúng và còn hoạt động".

## 3. Tham số hệ thống

| Thành phần | Giá trị |
| --- | --- |
| Tiền xử lý | Unicode NFKD, bỏ dấu, `đ → d`, chữ thường, tách theo khoảng trắng; 5 viết tắt (`vpp`, `photo`, `cafe`, `coffee`, `bus`) |
| Chỉ mục | SQLite FTS5 (chỉ mục đảo), 4 cột: tên, danh mục, mô tả, tags |
| BM25 | k1 = 1,2; b = 0,75 (mặc định FTS5); trọng số cột tên 2,0, các cột khác 1,0 |
| Truy vấn | Các token nối AND |
| Khoảng cách | Haversine, R = 6 371 008,8 m; bán kính 300 / 500 / 1 000 / 2 000 m |
| Xếp hạng kết hợp | 0,6 × text_norm + 0,4 × geo_norm, **trọng số đặt tay** (không phải Learning to Rank) |
| Geofence | Vào ≤ 100 m, ra ≥ 130 m, 2 mẫu liên tiếp, bỏ mẫu sai số > 50 m, cooldown 30 giây |
| Chỉ đường | OSRM qua máy chủ FOSSGIS, đi bộ; Google Maps dự phòng |

Nguồn: `config/app.json`, `config/aliases.json`, `HUONG_DAN.md` phần C.

## 4. Đánh giá truy xuất thông tin

### Thiết lập

- 12 truy vấn có nhu cầu cụ thể; gốc là tâm khuôn viên; mỗi truy vấn có bán kính và danh mục riêng.
- Nhãn nhị phân 0/1 cho **toàn bộ** địa điểm trong phạm vi (danh mục + bán kính) của từng truy vấn: 232 nhãn, 56 nhãn liên quan. Gán trước khi xem kết quả xếp hạng; Claude soạn nháp, người duyệt ký.
- So sánh 3 chế độ trên **cùng tập ứng viên**: A = BM25, B = khoảng cách, C = kết hợp.
- Chỉ số: Precision@5, Recall@5 (chia cho tổng địa điểm liên quan trong nhãn của cả phạm vi), nDCG@5 (gain 2^rel − 1). Truy vấn không có đáp án: Recall/nDCG = N/A, loại khỏi trung bình.

| ID | Truy vấn | Bán kính | Danh mục | Nhu cầu | Số nhãn | Liên quan |
| --- | --- | ---: | --- | --- | ---: | ---: |
| Q01 | photocopy | 1 km | VPP/photocopy | Photocopy tài liệu | 4 | 3 |
| Q02 | van phong pham | 2 km | VPP/photocopy | Mua văn phòng phẩm, gõ không dấu | 7 | 3 |
| Q03 | cà phê | 500 m | Ăn uống | Quán cà phê ngồi học | 26 | 9 |
| Q04 | circle k | 300 m | Tất cả | Tìm Circle K | 22 | 2 |
| Q05 | Demon Kitchen | 300 m | Tất cả | Tìm đúng một quán | 22 | 1 |
| Q06 | com | 1 km | Ăn uống | Quán cơm trưa, không dấu | 32 | 3 |
| Q07 | trà sữa | 1 km | Ăn uống | Quán trà sữa | 32 | 2 |
| Q08 | cây xăng | 1 km | Trạm xăng | Đổ xăng | 7 | 7 |
| Q09 | xe buýt | 500 m | Trạm xe buýt | Trạm xe buýt về nhà | 20 | 20 |
| Q10 | phòng trọ | 1 km | Nhà trọ | Phòng trọ sinh viên | 2 | 2 |
| Q11 | sửa xe máy | 300 m | Tất cả | Không có đáp án trong corpus | 22 | 0 |
| Q12 | pizza | 2 km | Ăn uống | Quán pizza | 36 | 4 |

Nguồn: `eval/queries.csv`, `eval/qrels.csv`.

### Kết quả trung bình

| Chế độ | P@5 | P@5 (11 truy vấn có đáp án) | R@5 (11 truy vấn) | nDCG@5 (11 truy vấn) |
| --- | ---: | ---: | ---: | ---: |
| A: BM25 | **0,5833** | **0,6364** | **0,8654** | **1,0000** |
| B: khoảng cách | 0,5167 | 0,5636 | 0,8048 | 0,8806 |
| C: kết hợp | 0,5667 | 0,6182 | 0,8553 | 0,9838 |
| Mức trần có thể đạt theo nhãn | 0,5833 | 0,6364 | 0,8654 | 1,0000 |

Mức trần: nhiều truy vấn có ít hơn 5 địa điểm liên quan (P@5 tối đa của Q05 là 0,2) hoặc nhiều hơn 5 (R@5 tối đa của Q09 là 5/20 = 0,25). Nguồn: `eval/summary.md`, `eval/metrics.csv`.

### Kết quả từng truy vấn (A / B / C)

| ID | Trả về | P@5 | R@5 | nDCG@5 |
| --- | ---: | --- | --- | --- |
| Q01 | 4 | 0,6 / 0,6 / 0,6 | 1 / 1 / 1 | 1 / 0,967 / 1 |
| Q02 | 7 | 0,6 / 0,4 / 0,6 | 1 / 0,667 / 1 | 1 / 0,416 / 0,967 |
| Q03 | 13 | 1,0 / 0,4 / 0,8 | 0,556 / 0,222 / 0,444 | 1 / 0,384 / 0,854 |
| Q04 | 2 | 0,4 / 0,4 / 0,4 | 1 / 1 / 1 | 1 / 1 / 1 |
| Q05 | 1 | 0,2 / 0,2 / 0,2 | 1 / 1 / 1 | 1 / 1 / 1 |
| Q06 | 3 | 0,6 / 0,6 / 0,6 | 1 / 1 / 1 | 1 / 1 / 1 |
| Q07 | 3 | 0,4 / 0,4 / 0,4 | 1 / 1 / 1 | 1 / 0,920 / 1 |
| Q08 | 7 | 1,0 / 1,0 / 1,0 | 0,714 / 0,714 / 0,714 | 1 / 1 / 1 |
| Q09 | 20 | 1,0 / 1,0 / 1,0 | 0,25 / 0,25 / 0,25 | 1 / 1 / 1 |
| Q10 | 2 | 0,4 / 0,4 / 0,4 | 1 / 1 / 1 | 1 / 1 / 1 |
| Q11 | 0 | 0 / 0 / 0 | N/A | N/A |
| Q12 | 4 | 0,8 / 0,8 / 0,8 | 1 / 1 / 1 | 1 / 1 / 1 |

"Trả về" là số địa điểm khớp từ khóa trong phạm vi, giống nhau ở cả ba chế độ.

### Ví dụ thứ tự 5 kết quả đầu (1 = liên quan, 0 = không)

**Q03 "cà phê"** (OSM gắn cả quán trà sữa, nước mía, căng tin là "quán cà phê", nên chúng cũng khớp):

| Hạng | A: BM25 | B: khoảng cách | C: kết hợp |
| ---: | --- | --- | --- |
| 1 | Cafe Thềm Xưa (1) | Trà Sữa MayCha (0) | Passio Coffee (1) |
| 2 | Cà Phê Rita Võ (1) | Passio Coffee (1) | Cà Phê Rita Võ (1) |
| 3 | Passio Coffee (1) | Cà Phê Rita Võ (1) | The Coffee Bean & Tea Leaf (1) |
| 4 | Cafe ViEn (1) | Canteen SGU (0) | Mía Crush (0) |
| 5 | Coffee 161 (1) | Mía Crush (0) | Cafe ViEn (1) |

**Q02 "van phong pham"** (nhãn danh mục "Văn phòng phẩm / photocopy" làm mọi tiệm photocopy cũng khớp):

| Hạng | A: BM25 | B: khoảng cách | C: kết hợp |
| ---: | --- | --- | --- |
| 1 | VPP Hồng Ngọc (1) | Huỳnh Trí, photocopy (0) | Nhà Sách Ecobook (1) |
| 2 | Hồng Hà (1) | Photocopy Ngọc Lan (0) | Hồng Hà (1) |
| 3 | Nhà Sách Ecobook (1) | Nhà Sách Ecobook (1) | Huỳnh Trí, photocopy (0) |
| 4 | Huỳnh Trí, photocopy (0) | Photocopy BKV (0) | VPP Hồng Ngọc (1) |
| 5 | Minh Phước, photocopy (0) | Hồng Hà (1) | Photocopy BKV (0) |

Nguồn: `eval/results.csv`.

### Nhận xét có thể đưa vào báo cáo

1. Truy xuất không bỏ sót địa điểm liên quan nào ở cả 12 truy vấn; truy vấn không có đáp án trả về rỗng, không có kết quả sai.
2. BM25 đạt đúng mức trần P@5 và R@5 theo nhãn trên bộ truy vấn này.
3. Ba chế độ chỉ khác nhau ở 4 truy vấn (Q01, Q02, Q03, Q07). Khác biệt lớn nhất khi từ khóa mô tả loại địa điểm mà dữ liệu gắn nhãn rộng (Q02, Q03): xếp theo khoảng cách đưa địa điểm gần nhưng không đúng nhu cầu lên đầu.
4. Khi mọi kết quả đều dùng được như nhau (cây xăng, trạm xe buýt, pizza), ba chế độ cho chỉ số bằng nhau; "Gần nhất" là lựa chọn tự nhiên cho người dùng.
5. Chế độ kết hợp nằm giữa: giữ phần lớn độ chính xác văn bản và ưu tiên chỗ gần.

### Giới hạn phải nêu kèm

- 12 truy vấn, nhãn nhị phân, một người duyệt: đánh giá thăm dò, không có ý nghĩa thống kê, không kết luận chế độ nào vượt trội nói chung.
- Nhãn và chỉ mục cùng dựa trên tên và thẻ OSM nên kết quả có phần lạc quan; quy ước chỉ gán 1 khi có bằng chứng làm các truy vấn như "com" dễ đạt điểm cao.
- Trọng số giữ nguyên như trước khi đánh giá, không chỉnh theo kết quả.

## 5. Thời gian xử lý

Đo bằng `python -m scripts.benchmark` ngày 18/09/2026: 108 request (12 truy vấn × 3 chế độ × 3 lượt, sau một lượt khởi động không tính). Số đo thô: `eval/latency.csv`. Không dùng con số 500 ms trong bản cũ (đó là thời gian chờ giả).

| Chỉ số | Median | p95 | Max | Ghi chú |
| --- | ---: | ---: | ---: | --- |
| Xử lý request trong Flask (`request_ms`) | 1,47 ms | 2,29 ms | 5,10 ms | Kiểm tham số + tìm kiếm + tạo JSON; không gồm mạng |
| Riêng phần tìm kiếm (`server_ms`) | 0,54 ms | 0,86 ms | 1,17 ms | Chuẩn hóa + FTS5/BM25 + Haversine + xếp hạng |

Máy đo: Windows 11 (10.0.26200), 12 luồng CPU, Python 3.13.13. Dataset lúc đo: `ds-b3d684c628` (khác phiên bản đánh giá `ds-7ac47a589e` một chút do lượt thử import thêm dữ liệu; **cần đo lại sau khi đồng bộ DB** để cùng phiên bản với mục 4).

Cách diễn giải: trên corpus khoảng 93 địa điểm, phần tìm kiếm mất dưới 1 ms ở 95% lượt đo; thời gian người dùng cảm nhận chủ yếu do mạng, tải bản đồ và độ trễ gõ phím (0,3 giây). Đây là đo trên một máy, không phải kiểm thử tải; thời gian tải bản đồ và chỉ đường phụ thuộc mạng, không tính.

## 6. Kiểm thử

| Loại | Kết quả | Nguồn |
| --- | --- | --- |
| Test tự động Python | 136/136 đạt | `tests/`, lệnh `pytest -q` |
| Test tự động geofence (JavaScript) | 9/9 đạt | `tests/js/geofence.test.mjs` |
| Kiểm tra thủ công giao diện và tìm kiếm trên máy tính (B1–B12) | Đạt | `MANUAL_CHECKS.md` |
| Giao diện điện thoại, hộp hướng dẫn (B13–B16) | Cần kiểm lại sau khi đổi giao diện | `MANUAL_CHECKS.md` |
| Định vị thật, chỉ đường thật, geofence trên giao diện (C1–C8) | Chưa chạy | `MANUAL_CHECKS.md` |

Bảng đối chiếu R1–R5 và F01–F21: `README.md` mục 11.

## 7. Ảnh chụp nên có trong chương kết quả

Chụp từ đúng bản bàn giao, ghi phiên bản dataset ở góc trên:

1. Màn hình chính: bản đồ với marker đánh số và danh sách.
2. Cùng truy vấn "cà phê" ở 3 chế độ xếp hạng (3 ảnh hoặc ghép).
3. Bảng "Giải thích kết quả" đang mở (query chuẩn hóa, số ứng viên, cột điểm).
4. "văn phòng phẩm" và "van phong pham" cho cùng kết quả.
5. Chỉ đường đi bộ: tuyến trên bản đồ và thẻ quãng đường/thời gian.
6. Geofence: vòng 100/130 m và nhật ký có sự kiện vào/ra (chế độ mô phỏng).
7. Import `data/updates/them_poi_osm.csv` rồi tìm thấy "Phở Bắc Hải" ngay.
8. Giao diện trên điện thoại (bảng trượt).
9. Terminal: kết quả `pytest` và `scripts.evaluate`.

## 8. Những chỗ phải sửa trong Word/slide cũ

| Chỗ cũ | Vấn đề | Sửa thành |
| --- | --- | --- |
| Prototype HTML: bảng điểm "bm25" gán sẵn theo từ khóa, biến `maxBm25` bị ghi đè bởi từ khóa khớp cuối | Không phải BM25 thật | BM25 của SQLite FTS5 trên chỉ mục đảo thật (mục 3) |
| Gọi hàm tuyến tính trọng số đặt tay là Learning to Rank | Chưa có huấn luyện | "Xếp hạng kết hợp có trọng số đặt tay" |
| Công thức NDCG gain `2^rel − 1` nhưng bảng dùng gain tuyến tính | Không nhất quán. Ví dụ cũ nhãn [1, 2], ideal [2, 1]: NDCG@2 ≈ 0,796708 với gain mũ, ≈ 0,859719 với gain tuyến tính (không phải 0,861) | Bỏ toàn bộ số minh họa cũ; dùng kết quả mục 4 (gain mũ thống nhất) |
| Nhãn "đang mở = 2, đóng = 1" | Nhãn dựa đúng tín hiệu mà hàm điểm ưu tiên | Nhãn mới gán theo nhu cầu, trước khi xem xếp hạng (mục 4) |
| Slide "Đã thực hiện" liệt kê Spatial-Inverted Index, truy xuất đa kênh | Code không cài | Tách bảng "lý thuyết đã tìm hiểu / đã cài / hướng phát triển" (`HUONG_DAN.md` mục 32) |
| `isOpen`, rating cố định trong prototype | Không có nguồn, không phải dữ liệu thật | Bỏ; hệ thống mới không dùng giờ mở cửa/rating để xếp hạng |
| Gọi chỉ mục là B-tree / IR-tree | Sai thuật ngữ | Chỉ mục đảo FTS5; khoảng cách Haversine trên tập nhỏ, chưa có chỉ mục không gian |
| Mô tả mô hình neural (bi-encoder/cross-encoder) như phần hiện thực | Không cài | Chuyển sang hướng phát triển |
| Vị trí người dùng cố định ở Quận 1 (10.775, 106.700); 7 POI nhúng trong mã | Không đúng phạm vi HCMUE | Cơ sở 280 An Dương Vương, 3 chế độ vị trí, 93 POI có nguồn (mục 2) |
| Độ trễ 500 ms | Thời gian chờ giả | Số đo thật ở mục 5, hoặc ghi "chưa đo" |
| Mục lục Word lặp số trang 1 | Lỗi trường mục lục | Cập nhật field mục lục khi sửa Word |

Thông tin tác giả trong tài liệu gốc giữ nguyên; không tự thay.
