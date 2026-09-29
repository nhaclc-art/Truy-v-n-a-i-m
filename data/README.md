# Dữ liệu

`data/pois.csv` là nguồn dữ liệu duy nhất của corpus. `data/georank.db` được sinh lại từ file này bằng lệnh import, không sửa tay và không commit.

## Schema `pois.csv`

UTF-8, dòng đầu là tên cột. Import từ chối file có cột ngoài danh sách này (ví dụ cột điểm BM25).

| Cột | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `id` | có | ID ổn định, chỉ gồm `a-z`, `0-9`, `-`. OSM: `osm-node-<id>`, `osm-way-<id>`; nguồn khác: `src-<nguồn>-<mã>` |
| `name` | có | Tên hiển thị. POI OSM không tên dùng nhãn tạm "… (chưa rõ tên)" |
| `category` | có | Một trong `an_uong`, `tien_loi`, `vpp_photocopy`, `nha_tro`, `tram_xang`, `tram_xe_buyt` (`config/app.json`) |
| `address` | | Địa chỉ nếu nguồn có |
| `lat`, `lon` | có | Tọa độ WGS84; phải cách điểm tham chiếu không quá 2 km |
| `description`, `tags` | | Văn bản được đưa vào chỉ mục tìm kiếm cùng tên và danh mục |
| `source_url`, `source_type`, `source_id` | `source_url`, `source_type` | Nguồn kiểm chứng được (`osm`, `listing`, …) |
| `retrieved_at` | | Ngày lấy dữ liệu, dạng `2026-09-18` |
| `verification_status` | có | `source_only`, `cross_checked`, `field_checked`; `uncertain` thì import bỏ qua và xóa khỏi DB |
| `verified_at`, `verification_note` | | Ngày và ghi chú kiểm chứng |
| `listing_url`, `listing_checked_at` | với `nha_tro` | Tin đăng và ngày kiểm tra tin |
| `opening_hours` | | Giờ mở cửa theo nguồn, chỉ để hiển thị, không dùng để xếp hạng |

## Thêm hoặc sửa dữ liệu (không sửa mã)

```powershell
python -m scripts.import_pois data\pois.csv            # thêm/sửa theo id, không xóa POI vắng mặt
python -m scripts.import_pois data\pois.csv --replace  # đồng bộ DB đúng bằng nội dung file
```

Import kiểm tra toàn bộ file trước khi ghi; chỉ cần một dòng lỗi là không ghi gì. Chạy lặp cùng file không tạo bản ghi trùng. App đang chạy thấy dữ liệu mới ở request kế tiếp. `dataset_version` (`ds-` + 10 ký tự hash của nội dung bảng) đổi khi dữ liệu đổi.

`data/updates/them_poi_osm.csv` là ví dụ thêm một POI thật (Phở Bắc Hải, OSM) nằm ngoài corpus: import file này rồi tìm "pho bac hai" để thấy POI mới xuất hiện. Muốn giữ lâu dài thì chép dòng đó vào `pois.csv`; lần import `--replace` kế tiếp sẽ xóa POI không có trong `pois.csv`.

## Tái tạo corpus từ nguồn

```powershell
python -m scripts.fetch_osm          # snapshot Overpass mới vào data/raw/ (không commit)
python -m scripts.build_draft        # data/pois_draft.csv theo config/osm_corpus.json + data/manual/*.csv
python -m scripts.apply_review       # data/pois.csv = bản nháp + kết quả duyệt trong data/review_sheet.csv
python -m scripts.make_review_sheet  # thêm POI mới vào bảng duyệt, giữ phần đã điền
```

Không chép tay bản nháp đè lên `pois.csv`: mọi chỉnh sửa (tên thật, địa chỉ, tọa độ đúng, trạng thái kiểm chứng) nằm trong `data/review_sheet.csv` và được `apply_review` áp lại mỗi lần, nên dữ liệu tái tạo được từ nguồn. Cách điền bảng duyệt: `MANUAL_CHECKS.md`, phần A. Nguồn và giấy phép: `DATA_SOURCES.md`.
