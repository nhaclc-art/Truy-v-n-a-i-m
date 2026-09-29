# STATUS — GeoRank HCMUE

## Cuối kỳ: lộ trình nhiều chặng (27/09/2026)

Hạn nộp đã đặt là thứ Bảy 26/09/2026 (file 08/09); hôm nay 27/09/2026 đã qua hạn đó. Người dùng vẫn yêu cầu thêm tính năng này sau khi được cảnh báo và chọn "bản nhẹ" thay bản đầy đủ (cần dữ liệu rạp phim, giờ chiếu).

| Hạng mục | Trạng thái |
| --- | --- |
| `src/itinerary.py`, `/api/itinerary` | Đã viết, có test (`tests/test_itinerary.py`, bổ sung `tests/test_api.py`, `tests/test_config.py`); **chưa chạy pytest** |
| `src/search.py` (`parse_origin` tách ra dùng chung) | Đã sửa, cần `pytest` xác nhận test cũ (search/whynot/ocr) vẫn đạt |
| Giao diện lộ trình (`static/js/app.js`, `map.js`, `app.css`, `index.html`) | Đã viết (form nhiều chặng, 3 lộ trình, chỉ đường thật, tái dùng why-not theo chặng); chưa mở trên trình duyệt |
| `scripts.check_itinerary` | Đã viết, chưa chạy (không phải đánh giá IR, chỉ kiểm tra thăm dò trên dữ liệu thật) |

## Cuối kỳ: why-not (23/09/2026)

| Hạng mục | Trạng thái |
| --- | --- |
| `src/search.py` tách bước + tham số `alpha` | PASS (`pytest` 160 passed, lượt 1) |
| `src/whynot.py`, `/api/whynot`, `/api/pois` | PASS lượt 1; lượt 2 sửa D-44/D-45 (lấy từ trong tên, hiển thị có dấu, thanh 4 bước), cần chạy lại test |
| Giao diện why-not | Làm lại theo D-44 (thẻ nổi, một lối vào), chưa kiểm trên trình duyệt |
| `scripts.eval_whynot` | Lượt 1: 83/83 câu trả lời được (68 từ R5 + 15 soạn tay đã ký bởi Tran Dat). Cần chạy lại sau D-45 |
| `eval/whynot_questions.csv` | Đã ký: Tran Dat, 23/09/2026 |
| Khảo sát `eval/whynot_survey.csv` | Chờ thu thập |
| Phương án B: `src/spell.py`, `scripts.eval_spell`, giao diện "Đã hiểu …" | Đã viết, chưa chạy; phải kiểm R5 không đổi |
| Giọng nói: `static/js/voice.js`, gộp âm tiết trong `src/spell.py`, `scripts.eval_voice` | Đã viết, chưa chạy. `eval/voice_queries.csv` trống, chờ thu dữ liệu đọc thật |
| Tìm bằng ảnh: `static/js/ocr.js`, `src/ocr_query.py`, `/api/ocr-query`, `match=any`, `scripts.vendor_tesseract`, `scripts.eval_ocr` | Đã viết, chưa chạy. Cần tải bộ đọc chữ; `eval/ocr_cases.csv` trống, chờ chụp biển thật |
| Điện thoại | Giao diện đã xem lại (ô nhập 16px, vùng chạm, thẻ nổi). Chưa thử trên thiết bị thật; cách mở HTTPS ở `HUONG_DAN.md` 10D; ca E11–E12 |

Cập nhật: 18/09/2026, sau khi soạn nhãn nháp và công cụ bàn giao (M7). File nội bộ, không đưa vào source ZIP.

## Cổng

| Cổng | Trạng thái |
| --- | --- |
| G0 — Khởi động được | PASS |
| G1 — Lát cắt IR thật | PASS: ca B1–B12 đạt (người dùng xác nhận 18/09/2026) |
| G2 — Demo đầu ra | IN PROGRESS: code GPS, chỉ đường, geofence đã viết; test/ca thủ công C chưa có kết quả |
| G3 — IR đạt yêu cầu | PASS: R1–R4 có test tự động + ca B đạt; R5 đánh giá chạy với nhãn do Tran Dat duyệt |
| G4 — Bàn giao | IN PROGRESS: README, KNOWN_LIMITATIONS, script xuất ZIP đã viết; chưa xuất và thử ZIP sạch |

## Dữ liệu

`ds-7ac47a589e`: 93 POI (ăn uống 36, tiện lợi 11, VPP/photocopy 7, nhà trọ 2, trạm xăng 10, trạm xe buýt 27); 16 `cross_checked`. Chi tiết trong `DATA_SOURCES.md`.

## Nhãn R5

`eval/qrels.csv`: 232 dòng (labeled_by `claude-draft`), người duyệt Tran Dat, giữ nguyên nhãn nháp. Số POI liên quan: Q01 3, Q02 3, Q03 9, Q04 2, Q05 1, Q06 3, Q07 2, Q08 7, Q09 20, Q10 2, Q11 0, Q12 4.

## Kết quả mới nhất (18/09/2026)

| Hạng mục | Kết quả |
| --- | --- |
| `pytest` | PASS, 136 test |
| `node --test tests/js/geofence.test.mjs` | PASS, 9 test |
| `sign_labels` | 232/232 dòng có người duyệt Tran Dat |
| `evaluate` | BM25 P@5 0,5833 / R@5 0,8654 / nDCG@5 1,0; khoảng cách 0,5167 / 0,8048 / 0,8806; kết hợp 0,5667 / 0,8553 / 0,9838. BM25 đạt đúng mức trần P@5 và R@5 theo nhãn; khác biệt giữa chế độ chỉ ở Q01, Q02, Q03, Q07 |
| `benchmark` | request_ms median 1,47 / p95 2,29; server_ms median 0,54 / p95 0,86 (108 lần đo). Dataset lúc đo `ds-b3d684c628` ≠ phiên bản đánh giá `ds-7ac47a589e`: cần import lại `data\pois.csv --replace` rồi đo lại trước khi xuất ZIP |
| `export_source` | NOT RUN |
| Giao diện điện thoại (bảng trượt, thẻ nổi, nút định vị), modal hướng dẫn, sửa lỗi cuộn khi theo dõi | Đã viết, NOT RUN; ca B13–B16 cần kiểm |
| Kế hoạch chuyển thành app | `docs/planning/07_KE_HOACH_APP.md`, chờ người dùng chọn mức 0–3 |
| `HUONG_DAN.md` | Đã viết (hướng dẫn sử dụng + giải thích kỹ thuật + phân tích đánh giá) |

## Việc cần người

1. Điền phiếu `MANUAL_CHECKS.md` (ít nhất B3 cho R2, B7, B10, C1, C3, C6).
2. Xuất ZIP, giải nén vào thư mục sạch, chạy lại README mục 2–3 (F21).
3. Điền khối thông tin bàn giao trong README (hoặc để người nhận điền).

## Lệnh (PowerShell, tại thư mục `georank-hcmue`, venv đã activate)

```powershell
python -m pytest -q
node --test tests/js/geofence.test.mjs
python -m scripts.evaluate --check-only
python -m scripts.sign_labels --reviewer "Họ tên" --confirm-reviewed   # chỉ sau khi đã xem hết nhãn
python -m scripts.evaluate
python -m scripts.export_source --release v1.0-giuaky
```

## Bước kế tiếp

Claude: đọc kết quả test/đánh giá, sửa lỗi, cập nhật biên bản bàn giao trong README (mục 11) theo kết quả thật, rồi mới làm outline sửa Word/slide.
