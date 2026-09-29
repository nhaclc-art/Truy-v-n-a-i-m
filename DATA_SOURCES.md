# Nguồn dữ liệu

Bản đang xây dựng (mốc M1). Corpus chưa khóa; số lượng và trạng thái kiểm chứng sẽ cập nhật khi chạy `scripts.build_draft` và import.

## Vị trí cơ sở

`config/campus.json`: tâm OSM way 140703173 (Trường Đại học Sư phạm TP.HCM, 280 An Dương Vương), đối chiếu với node 9586952123. © OpenStreetMap contributors, ODbL 1.0.

## POI từ OpenStreetMap

- Lấy bằng `python -m scripts.fetch_osm` (một truy vấn Overpass, bán kính 2 km quanh điểm tham chiếu). Mỗi lần tải là một file mới `data/raw/osm_<ngàyTgiờZ>.json`; truy vấn, endpoint, thời điểm, mốc dữ liệu OSM và SHA-256 của phản hồi ghi trong file `.meta.json` đi kèm.
- Tag thu: `amenity=restaurant|fast_food|cafe|food_court|fuel`, `shop=convenience|stationery|copyshop|books`, `highway=bus_stop`, và phần tử có `name`/`brand` là chuỗi cửa hàng tiện lợi (Circle K, FamilyMart, GS25, Ministop, 7-Eleven, B's Mart, WinMart) vì có nơi gắn tag khác `shop=convenience`.
- Làm sạch bằng `python -m scripts.build_draft` theo `config/osm_corpus.json`:
  - Tên lấy từ `name`, thiếu thì từ `brand` (ghi chú trong `verification_note`). POI không tên chỉ nhận khi cách điểm tham chiếu ≤ 300 m, với nhãn tạm "… (chưa rõ tên)" để người kiểm tra điền tên thật; xa hơn thì bỏ.
  - `shop=books` chỉ nhận khi tên thể hiện văn phòng phẩm/photocopy. Bỏ bản ghi có tên trùng nhau trong vòng 30 m (POI không tên không bị gộp).
  - Vòng ≤ 300 m và ≤ 500 m: lấy hết mọi danh mục. Vòng ≤ 1000 m: ăn uống 4, tiện lợi 4, xe buýt 4, trạm xăng và VPP lấy hết. Vòng ≤ 2000 m: ăn uống 4, tiện lợi 3, trạm xăng 3, xe buýt 3, VPP lấy hết. Trong cùng vòng ưu tiên bản ghi có địa chỉ, cuisine, giờ mở cửa rồi đến OSM ID.
  - Trạm xe buýt ghi số tuyến từ `route_ref` vào `tags`. Way/relation dùng tâm hình học, không phải lối vào.
- Bản đầu (snapshot 18/09/2026 06:09 UTC, chỉ lấy tối đa 4 điểm ăn uống/vòng) làm sót Cà Phê Rita Võ và các quán không tên sát Demon Kitchen; luật hiện tại sửa việc này (DECISIONS D-26).
- Giấy phép: ODbL 1.0, "© OpenStreetMap contributors". `data/pois.csv` là cơ sở dữ liệu phái sinh và giữ cùng giấy phép.
- Giờ mở cửa lấy nguyên từ OSM, chưa kiểm tra, chỉ để hiển thị.

## Đối chiếu chéo

Kết quả duyệt nằm trong `data/review_sheet.csv` và được áp vào `data/pois.csv` bằng `scripts.apply_review`. Lượt đầu (18/09/2026, Claude đối chiếu web, chưa khảo sát tại chỗ):

- Khớp nguồn thứ hai (Foody hoặc bài đăng về quán): Cà Phê Rita Võ, Trà Sữa Bocha, Sushi M&H, Gỏi Cuốn Ngon Ngon, Demon Kitchen Tai Pai Dong, Nhà hàng Ếch Xanh, Cơm Tấm Nguyễn Văn Cừ, Cafe Thềm Xưa.
- **Sai vị trí trong OSM:** Nhà Hàng Út Cà Mau. Node 4676482492 nằm trong khối trường học cạnh HCMUE, trong khi Foody ghi 512–514 Nguyễn Thị Minh Khai, Quận 3. OSM có node thứ hai cùng tên (6520653685) đúng địa chỉ đó; corpus dùng tọa độ node này. Nên báo sửa trên OSM.
- Chưa kết luận ở lượt đầu: Cơm Tấm 419, Nhà Hàng Chay Hoa Ưu Đàm (xem lượt người dùng bên dưới).

Lượt người dùng tra Google Maps (18/09/2026):

- Đặt tên cho 6 điểm OSM không tên: Nhà Hàng Bê Vàng, Nhà Hàng Biển Việt, Bún Bò Viên, Trà Sữa MayCha (213E Nguyễn Văn Cừ), Passio Coffee (số 213; tên đường Nguyễn Văn Cừ suy từ vị trí, cần xác nhận), Mía Crush (29 Nguyễn Trãi).
- Cơm Tấm 419: địa chỉ đúng 417 An Dương Vương, Chợ Quán, phía bên kia đường so với node OSM. Tọa độ trong corpus là gần đúng, lấy theo node OSM có địa chỉ 419 An Dương Vương sát bên.
- Nhà Hàng Chay Hoa Ưu Đàm: thông tin sai, bị loại khỏi corpus (`uncertain`).

Google Maps không được tra tự động (điều khoản cấm trích xuất tự động; Places API cần tài khoản trả phí).

## Nhà trọ

OSM trong phạm vi 2 km không có tag nào chứng minh là nhà trọ, và khách sạn/hostel/ký túc xá không được đổi nhãn. Nguồn dùng là tin đăng công khai, kiểm tra ngày 18/09/2026, lưu trong `data/manual/nha_tro.csv`:

| ID | Nguồn | Tình trạng tin khi kiểm tra |
| --- | --- | --- |
| `src-phongtro123-706311` | phongtro123.com tin #706311, 378 An Dương Vương | Đăng 08/07/2026, không thấy thông báo hết hạn |
| `src-phongtro123-702637` | phongtro123.com tin #702637, 338/1/16 An Dương Vương | Đăng 09/03/2026, đã hết hạn |

Không lưu số điện thoại, tên người đăng hay giá. Tin còn tồn tại không có nghĩa là còn phòng. Tọa độ lấy theo tâm hẻm tương ứng trên OSM, là **gần đúng**. Cả hai đang ở trạng thái `source_only` và **chờ người duyệt** trước khi khóa corpus.

Tin trên phongtro123 thường hết hạn sau vài ngày theo gói đăng (tin #712386 đăng 01/09/2026 đã hết hạn khi kiểm tra 18/09/2026), nên "hết hạn" không chứng minh nơi đó ngừng cho thuê, và tin còn hiển thị cũng không chứng minh còn phòng.

### Đã xác minh, chờ tọa độ

Hai tin dưới đây thuộc mục "Cho thuê phòng trọ", mô tả phòng riêng, đều ở Phường Chợ Quán. Overpass và Nominatim quá tải/từ chối kết nối lúc tra ngày 18/09/2026 nên chưa định vị được; chưa đưa vào CSV vì import bắt buộc có tọa độ.

| Tin | Địa chỉ trong tin | Đăng | Tình trạng |
| --- | --- | --- | --- |
| [phongtro123 #712386](https://phongtro123.com/phong-moi-may-lanh-dhsp-dhsg-cd-kinh-te-2-pr712386.html) | 86/9 Trần Bình Trọng | 01/09/2026 | Hết hạn |
| [phongtro123 trang pr648241](https://phongtro123.com/cho-thue-phong-75-12-nguyen-van-cu-phuong-1-quan-5-co-may-lanh-pr648241.html) (mã tin hiển thị #704673) | 75/12 Nguyễn Văn Cừ | 05/07/2026 | Hết hạn 10/07/2026 |

### Đã loại

| Tin | Lý do |
| --- | --- |
| phongtro123 #294682, 402/36 An Dương Vương | Hết hạn; OSM không có hẻm 402 để định vị |
| phongtro123 #689097, hẻm 80 Nguyễn Trãi | Tin tự mô tả là căn hộ dịch vụ (CHDV), không phải nhà trọ |
| phongtro123 #699786, 138 Nguyễn Trãi | Hết hạn; mô tả loại phòng không rõ |
| phongtro123 #314907, 31/16 Nguyễn Văn Cừ | Đăng năm 2020 |
| Các tin sleepbox, ký túc xá, căn hộ/studio | Không phải nhà trọ |
| Các tin chỉ ghi tên đường, không có số nhà | Không định vị được |

Chưa xử lý: hẻm 835 Trần Hưng Đạo (tin đăng 05/2025) và 55 Trần Hưng Đạo (số nhà mặt tiền, cần định vị).

## Bản đồ và chỉ đường

- Nền bản đồ: tile OpenStreetMap, © OpenStreetMap contributors, theo Tile Usage Policy của OSMF.
- Chỉ đường đi bộ: FOSSGIS e.V. `routing.openstreetmap.de` (OSRM), dữ liệu © OpenStreetMap contributors.
