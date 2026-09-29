# Phiếu kiểm tra thủ công

Test tự động (`python -m pytest -q`, `node --test tests/js/geofence.test.mjs`) chỉ chứng minh logic trên dữ liệu tổng hợp. Phiếu này dành cho những gì cần người nhìn: dữ liệu thật, giao diện, trình duyệt, thiết bị.

**Cách điền:** cột "Đạt?" ghi `Đạt`, `Không đạt` hoặc `Bỏ qua`. Cột "Ghi chú" ghi hiện tượng thấy được, query đã gõ, tên file ảnh chụp nếu có. Điền xong gửi lại cho Claude; Claude sửa lỗi và cập nhật dữ liệu. Không xóa ca "Không đạt" khi đã sửa, chỉ ghi thêm lần thử mới.

Người thử: ______________________  Ngày: ____________  Trình duyệt/thiết bị: ______________________

## A. Dữ liệu

### A1. Duyệt từng POI trong `data/review_sheet.csv`

Tạo bảng bằng `python -m scripts.make_review_sheet`. Mỗi dòng có link nguồn (`source_url`), link bản đồ OSM (`osm_map`) và Google Maps (`google_maps`) tại đúng tọa độ. Chỉ điền các cột ở cuối:

| Cột | Điền gì |
| --- | --- |
| `ket_qua` | `dung` (đúng tên, loại hình, vị trí theo nguồn khác) · `dung_tai_cho` (đã đến tận nơi) · `sai` (có thông tin sai, ghi bản đúng ở các cột sau) · `dong_cua` (không còn hoạt động/không thấy; bị loại khỏi corpus) · `khong_ro` (không kiểm được) |
| `ten_dung` | Tên thật nếu tên sai, hoặc tên của điểm đang ghi "(chưa rõ tên)" |
| `dia_chi_dung` | Địa chỉ nếu thiếu hoặc sai |
| `danh_muc_dung` | Danh mục đúng nếu xếp nhầm (`an_uong`, `tien_loi`, `vpp_photocopy`, `nha_tro`, `tram_xang`, `tram_xe_buyt`) |
| `ghi_chu` | Kiểm bằng gì: Google Maps, trang web của quán, đi tận nơi… kèm link nếu có |
| `nguoi_kiem_tra`, `ngay_kiem_tra` | Tên người kiểm, ngày dạng `2026-09-20` |
| `toa_do_dung` | Tọa độ đúng dạng `10.76, 106.68` nếu marker lệch chỗ |

Điền xong chạy `python -m scripts.apply_review` rồi import `data\pois.csv --replace`; không sửa tay `data/pois.csv`.

Claude đã điền sẵn 11 dòng bằng đối chiếu web (Foody, Threads, ZaloPay), ghi người kiểm tra là "Claude (đối chiếu web, chưa khảo sát)". Người duyệt có thể sửa hoặc xác nhận lại các dòng này. Các điểm còn lại cần mở Google Maps thủ công: Google Maps không cho truy cập tự động.

Ưu tiên: các điểm sẽ trình diễn (ít nhất 10 đạt), mọi điểm "(chưa rõ tên)", nhà trọ, trạm xăng, trạm xe buýt. Không cần duyệt hết một lần. Mở bằng Excel thì lưu lại bằng định dạng **CSV UTF-8** để giữ tiếng Việt.

### A2. Nhà trọ chờ tọa độ

Mở tin, tìm đầu hẻm hoặc căn nhà trên Google Maps, chuột phải lên đúng vị trí, bấm dòng tọa độ để sao chép.

| Tin | Địa chỉ trong tin | Tọa độ (lat, lon) | Vẫn là phòng trọ? | Ghi chú |
| --- | --- | --- | --- | --- |
| [phongtro123 #712386](https://phongtro123.com/phong-moi-may-lanh-dhsp-dhsg-cd-kinh-te-2-pr712386.html) | 86/9 Trần Bình Trọng | | | |
| [phongtro123 pr648241](https://phongtro123.com/cho-thue-phong-75-12-nguyen-van-cu-phuong-1-quan-5-co-may-lanh-pr648241.html) | 75/12 Nguyễn Văn Cừ | | | |
| [phongtro123 #706311](https://phongtro123.com/phong-ban-cong-moi-xay-co-thang-may-gan-dh-su-pham-q-5-pr706311.html) (đã có trong CSV, tọa độ gần đúng) | 378 An Dương Vương | | | |
| [phongtro123 #702637](https://phongtro123.com/chinh-chu-cho-thue-phong-tro-tai-338-1-16-an-duong-vuong-phuong-cho-quan-pr702637.html) (đã có trong CSV, tin hết hạn) | 338/1/16 An Dương Vương | | | |

### A3. Địa điểm còn thiếu muốn thêm

Ví dụ Circle K trên Trần Bình Trọng nếu sau lần tải dữ liệu mới vẫn chưa có. Cần có nguồn kiểm chứng được (link OSM, trang của cửa hàng, hoặc ghi "khảo sát tại chỗ ngày …").

| Tên | Danh mục | Tọa độ hoặc link Google Maps | Địa chỉ | Nguồn | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| | | | | | |
| | | | | | |

## B. Giao diện và tìm kiếm

Chuẩn bị: `python app.py`, mở http://127.0.0.1:5000 bằng Chrome hoặc Edge, tải lại bằng Ctrl+F5.

| Ca | Thao tác | Kết quả cần có | Đạt? | Ghi chú |
| --- | --- | --- | --- | --- |
| B1 (F02) | Gõ "cà phê". Bấm một thẻ, rồi bấm một marker khác | Số marker bằng số thẻ; số trên marker khớp số thứ tự thẻ. Bấm thẻ mở popup đúng tên; bấm marker tô viền và cuộn tới thẻ | Đạt | Người dùng xác nhận 18/09/2026 (giao diện desktop) |
| B2 (F03) | Lần lượt gõ "văn phòng phẩm", "van phong pham", "VPP", giữ nguyên bán kính và cách xếp | Cùng tập kết quả. Thử thêm một tên có chữ "Đ/đ" gõ bằng "d" | Đạt | Người dùng xác nhận 18/09/2026 |
| B3 (F04, R2) | Nhờ một người khác nhìn bản đồ/danh sách rồi tự chọn một tên POI, gõ có dấu và không dấu | Tìm ra POI đó. Ghi chính xác query họ chọn | Đạt | Người dùng xác nhận 18/09/2026; query người kiểm tra chọn: ____ |
| B4 (F05) | Xóa trống ô từ khóa; gõ "khongtontai"; gõ `"`, `*`, `<b>x</b>` | Rỗng: danh sách theo khoảng cách, bảng giải thích ghi "duyệt theo vị trí". Không có kết quả: có hộp gợi ý. Ký tự lạ: không lỗi, không hiện chữ đậm | Đạt | Người dùng xác nhận 18/09/2026 |
| B5 (F06) | Chọn một danh mục và bán kính 300 m | Mọi thẻ đúng danh mục, khoảng cách ≤ 300 m; vòng tròn trên bản đồ đổi theo | Đạt | Người dùng xác nhận 18/09/2026 |
| B6 (F07) | Xếp "Gần nhất". Bấm "Mô phỏng", bấm một điểm khác trên bản đồ, rồi kéo chấm cam. Bấm "Tâm khuôn viên" | Khoảng cách tăng dần; nhãn đổi sang MÔ PHỎNG, khoảng cách và thứ tự tính lại; quay về thì nhãn THAM CHIẾU | Đạt | Người dùng xác nhận 18/09/2026 |
| B7 (F19, R3) | Cùng một query có chữ (vd "com"), chuyển qua 3 cách xếp | Số "địa điểm trong bán kính" giữ nguyên. "Đúng từ khóa": cột BM25 thô tăng dần (càng âm càng đứng đầu). "Kết hợp": cột điểm kết hợp giảm dần. Hai cách cho cùng thứ tự thì ghi đúng như vậy | Đạt | Người dùng xác nhận 18/09/2026 |
| B8 (F20, R4) | Mở "Giải thích kết quả"; mở thêm `/api/search?q=com&radius_m=1000` ở tab khác với cùng tham số | Query chuẩn hóa, ba số đếm, điểm từng dòng và dataset khớp JSON | Đạt | Người dùng xác nhận 18/09/2026 |
| B9 (F10) | Gõ thật nhanh "c", "co", "com", "com t" | Kết quả cuối là của query cuối | Đạt | Người dùng xác nhận 18/09/2026 |
| B10 (F17, R1) | App đang chạy: `python -m scripts.import_pois data\updates\them_poi_osm.csv`, rồi tìm "pho bac hai" (bán kính 2 km). Sau đó sửa tên một POI trong `data/pois.csv` (thêm chữ "Kiemtra"), import `data\pois.csv --replace`, tìm "kiemtra". Hoàn tác, import lại | POI mới xuất hiện không cần khởi động lại app. "kiemtra" tìm ra, sau hoàn tác không còn khớp. Import lặp không tăng số POI | Đạt | Người dùng xác nhận 18/09/2026 |
| B11 (F16) | Trang đã tải xong thì tắt mạng, tìm tiếp | Tìm kiếm vẫn chạy; nền bản đồ có thể không tải và góc bản đồ báo lỗi tile. Không mô tả đây là bản đồ offline | Đạt | Người dùng xác nhận 18/09/2026 |
| B12 (F18) | Tìm `<img src=x onerror=alert(1)>` | Không bật hộp thoại alert; chuỗi hiện dạng chữ | Đạt | Người dùng xác nhận 18/09/2026 |
| B13 | Thu hẹp cửa sổ dưới 900 px hoặc bật chế độ điện thoại trong DevTools | Bản đồ phủ toàn màn hình, danh sách là bảng trượt ở dưới, không tràn ngang | Kiểm lại | Đạt trên giao diện cũ (18/09/2026); giao diện điện thoại đã đổi sau đó |
| B14 | Màn hình hẹp: kéo thanh xám ở đầu bảng trượt lên/xuống; bấm vào thanh; chạm một thẻ; chạm một marker | Bảng dừng ở 3 mức (thấp, nửa màn hình, gần đầy); chạm thẻ thì bảng hạ xuống và bản đồ hiện đúng marker phía trên bảng; chạm marker thì bảng mở nửa và cuộn tới thẻ; ghi nguồn OSM ở góc bản đồ luôn nhìn thấy | | |
| B15 | Bấm nút **?** (Hướng dẫn) trên thanh trên cùng; đóng bằng nút ×, phím Esc, bấm ra ngoài | Modal hướng dẫn mở và đóng được cả 3 cách; trên điện thoại chiếm toàn màn hình, cuộn được | | |
| B16 | Bật "Mô phỏng", bấm "Theo dõi 100 m", rồi cuộn danh sách xuống cuối và cuộn nhật ký sự kiện | Danh sách và nhật ký đứng yên, không bị kéo về mỗi giây; thẻ Geofence nằm nổi trên bản đồ | | |

## C. Định vị, chỉ đường, geofence

| Ca | Thao tác | Kết quả cần có | Đạt? | Ghi chú |
| --- | --- | --- | --- | --- |
| C1 (F08) | Bấm "Vị trí của tôi", cho phép quyền. Chờ vài giây rồi bấm lại để tắt | Nhãn VỊ TRÍ THẬT, tọa độ, sai số ±m, giờ cập nhật; vòng sai số trên bản đồ. Tắt thì về THAM CHIẾU. Máy tính có thể định vị theo Wi-Fi/IP nên sai số lớn: ghi đúng số đo | | |
| C2 (F09) | Chặn quyền vị trí cho trang (ổ khóa trên thanh địa chỉ → Vị trí → Chặn), tải lại, bấm "Vị trí của tôi" | Báo đã từ chối quyền; nhãn vẫn THAM CHIẾU, không tự chuyển MÔ PHỎNG | | |
| C3 (F11) | Chọn một POI, bấm "Chỉ đường" | Đường xanh bám theo phố, không phải đường thẳng; thẻ "Chỉ đường đi bộ" có quãng đường theo tuyến, số phút máy chủ ước tính, khoảng cách đường chim bay tách riêng | | |
| C4 (F12) | Tắt mạng sau khi trang đã tải, bấm "Chỉ đường" | Báo không lấy được tuyến, không vẽ đường giả; vẫn có nút "Mở Google Maps" ghi rõ chỉ đường ngoài ứng dụng | | |
| C5 | Đang có tuyến thì bật "Mô phỏng" và kéo chấm cam đi chỗ khác | Thẻ chỉ đường báo vị trí gốc đã đổi, có nút "Tính lại tuyến" | | |
| C6 (F13) | Bấm "Theo dõi 100 m" trên một POI. Bật "Mô phỏng", đặt chấm cam ngoài vòng nét đứt, đợi 2 giây rồi kéo vào trong vòng đặc | Nhật ký có "Khởi tạo: ngoài vùng", sau khoảng 2 giây trong vùng có đúng một dòng "Vào vùng … · mô phỏng" và một thông báo nổi | | |
| C7 (F14) | Giữ chấm trong vòng 100 m, kéo qua lại giữa 100 m và 130 m, rồi kéo ra ngoài vòng nét đứt | Dao động giữa hai vòng không sinh sự kiện; ra ngoài 130 m sau khoảng 2 giây có một dòng "Ra khỏi vùng". Chưa đủ 30 giây từ thông báo trước thì dòng ghi "không thông báo do cooldown" và không có thông báo nổi | | |
| C8 (F15) | Đang theo dõi thì bấm "Tâm khuôn viên" hoặc "Vị trí của tôi"; hoặc theo dõi một POI khác | Nhật ký ghi "Đặt lại trạng thái" hoặc "Dừng/Bắt đầu theo dõi"; không có dòng vào/ra giả ngay sau đó | | |

## E. Phần cuối kỳ: why-not, sửa lỗi gõ, giọng nói, điện thoại

Máy tính: mở `http://127.0.0.1:5000` bằng Chrome hoặc Edge. Điện thoại: mở bằng đường dẫn **HTTPS** (xem `HUONG_DAN.md` mục 10D). Qua địa chỉ LAN dạng `http://192.168…` thì micro và định vị bị trình duyệt chặn.

| Ca | Thao tác | Kết quả mong đợi | Đạt? | Ghi chú |
| --- | --- | --- | --- | --- |
| E1 | "cà phê", 500 m, Gần nhất. Bấm **Không thấy chỗ bạn cần?**, gõ "Thềm", chọn Cafe Thềm Xưa | Thẻ tím trên bản đồ; thanh 4 bước ✓ ✓ ✓ ✗ ở "5 kết quả đầu"; một câu lý do "vì xa hơn…"; tối đa 3 cách sửa; vòng tím "?" trên bản đồ | | |
| E2 | Ở E1 bấm **Áp dụng** cách đầu tiên | Ô tìm kiếm/bộ lọc đổi theo đề xuất, quán được chọn trong danh sách, thẻ tím báo "đã có trong … kết quả đầu" | | |
| E3 | Chọn "Ăn uống", gõ "circle k", 300 m, hỏi Circle K (qua liên kết trong thông báo "Không có kết quả") | Bước "Danh mục" ✗; cách sửa đầu tiên là bỏ lọc "Ăn uống" | | |
| E4 | Gõ "ăn sáng", 500 m, hỏi Canteen SGU | Bước "Khớp từ khóa" ✗, lý do ghi từ “sáng” có dấu; mở "Dữ liệu của địa điểm" thấy tag "breakfast"; **không** có đề xuất "brunch" | | |
| E5 | Gõ lần lượt "photocoppy", "circlek", "tra suwa", "caay xawng" | Dòng xanh "Đã hiểu … là …", kết quả như khi gõ đúng; bấm "Tìm đúng như đã gõ" thì kết quả rỗng | | |
| E6 | Gõ "ăn sáng" | Không có dòng "Đã hiểu" (không bị đổi thành "ăn hàng") | | |
| E7 | Bấm micro, cho phép micro, nói "cây xăng" | Nút đỏ nhấp nháy khi nghe; chữ hiện dần vào ô tìm kiếm; dòng "Nghe được … (độ tin cậy …)"; danh sách trạm xăng | | |
| E8 | Nói "photocopy" | Ghi lại câu nghe được. Nếu nghe thành "phô tô cóp pi" thì dòng xanh báo đã gộp thành "photocopy" | | |
| E9 | Chặn micro cho trang rồi bấm micro | Thông báo "Trình duyệt chặn micro…", không treo | | |
| E10 | Mở bằng Firefox | Không có nút micro; mọi chức năng khác vẫn chạy | | |
| E11 | Điện thoại (HTTPS): làm lại E1, E5, E7 | Thẻ tím nằm trên bản đồ, không bị bảng trượt che; ô gõ tên không làm trang tự phóng to (iOS); gợi ý tên hiện khi gõ; micro chạy | | |
| E12 | Điện thoại: bấm "Tải nhật ký giọng nói" | Tải được `voice_log.csv` (trên iOS có thể mở ra xem thay vì tải) | | |

### Tìm bằng ảnh (sau khi chạy `python -m scripts.vendor_tesseract`)

| Ca | Thao tác | Kết quả mong đợi | Đạt? | Ghi chú |
| --- | --- | --- | --- | --- |
| E13 | Máy tính: bấm máy ảnh, chọn ảnh chụp rõ biển Circle K (hoặc ảnh biển có trong dữ liệu) | Thẻ cam "Đọc biển hiệu": ảnh nhỏ, tiến độ các bước, rồi "Chữ đọc được", "Tìm theo:" các từ, "Có thể là:" quán đúng đứng đầu và được chọn trên bản đồ; dòng cam "Đang tìm theo chữ trên ảnh" | | |
| E14 | Mở DevTools → Console trong lúc đọc ảnh | Không có lỗi CSP (Refused to…) hay 404 của file trong `static/vendor/tesseract` | | |
| E15 | Chưa chạy `vendor_tesseract` (hoặc đổi tên thư mục), chọn ảnh | Thẻ báo "Chưa cài bộ đọc chữ…", trang không treo | | |
| E16 | Chọn ảnh biển quán không có trong dữ liệu | Thẻ hiện chữ đọc được; kết quả (nếu có) chỉ là "Có thể là", người dùng thấy rõ không khớp tên | | |
| E17 | Điện thoại (HTTPS): bấm máy ảnh | Mở camera sau (hoặc cho chọn); ảnh dọc hiển thị đúng chiều; đọc được trong thời gian chấp nhận được (ghi số giây) | | |
| E18 | Bấm "Tìm như bình thường" trên dòng cam; hoặc gõ câu mới | Về kiểu nối AND, dòng cam biến mất | | |

### Lộ trình nhiều chặng

| Ca | Thao tác | Kết quả mong đợi | Đạt? | Ghi chú |
| --- | --- | --- | --- | --- |
| E19 | Bấm **Lập lộ trình nhiều chặng**, giữ 3 chặng mặc định (cà phê/cơm/phim), ngân sách 3 km, bấm **Lập lộ trình** | Thẻ hồng hiện tóm tắt từng chặng: "cà phê" và "cơm" có ứng viên, "phim" báo **không khớp địa điểm nào** (đúng, vì corpus không có rạp phim); vì thiếu 1 chặng nên **không có lộ trình nào**, kèm câu giải thích rõ lý do (không phải thông báo lỗi) | | |
| E19b | Mở **Đổi chặng hoặc ngân sách**, sửa chặng 3 thành "xe buýt", bấm lại **Lập lộ trình** | Cả 3 chặng có ứng viên; hiện 1–3 lộ trình với thứ tự chặng, quãng đường từng đoạn, tổng quãng đường (ước tính) và số phút; bản đồ hiện các điểm đánh số 1-2-3 nối bằng nét đứt hồng | | |
| E20 | Bấm **+ Thêm chặng** (lên 4), **− Bớt chặng** (về 2); đổi ngân sách quãng đường; đổi thời gian mỗi chặng rồi bấm lại **Lập lộ trình** | Số ô nhập đổi theo, giữ nguyên chữ đã gõ ở các ô còn lại; nút +/− biến mất khi tới 4 hoặc 2 chặng; kết quả tính lại đúng theo tham số mới | | |
| E21 | Đặt ngân sách quãng đường rất nhỏ (1500 m nếu vẫn ra kết quả, hoặc sửa để không có lộ trình nào lọt) | Thông báo rõ không có lộ trình trong ngân sách và gợi ý quãng đường ngắn nhất tìm được | | |
| E22 | Trên một lộ trình, bấm **Xem trên bản đồ** ở lộ trình khác | Bản đồ vẽ lại đúng lộ trình vừa chọn; nút của lộ trình đang xem đổi thành "Đang xem" | | |
| E23 | Bấm **Chỉ đường thật cho lộ trình đang xem** | Từng chặng lần lượt hiện "đang tính…" rồi quãng đường/số phút thật; bản đồ vẽ thêm đường liền nét theo từng chặng; nếu một chặng lỗi (mất mạng) vẫn hiện các chặng khác và có link Google Maps dự phòng | | |
| E24 | Gõ một chặng thành từ không có trong dữ liệu (ví dụ "karaoke"), lập lộ trình | Chặng đó báo "không khớp địa điểm nào"; không có lộ trình; không có nút "Vì sao thiếu chỗ khác" ở chặng rỗng đó | | |
| E25 | Với một chặng có kết quả, bấm **Vì sao thiếu chỗ khác ở chặng này?**, gõ tên một địa điểm khác cùng loại | Mở đúng thẻ "Vì sao không thấy?" với dòng phụ ghi rõ đang hỏi theo chặng nào (không phải ô tìm kiếm chính); phân tích và đề xuất hiện như bình thường | | |
| E26 | Điện thoại (HTTPS): làm lại E19, E23 | Thẻ lộ trình không bị bảng trượt che; ô nhập không làm iOS tự phóng to; chạm nút đủ dễ | | |

## D. Duyệt nhãn đánh giá IR (R5)

`eval/qrels.csv` liệt kê, cho mỗi truy vấn trong `eval/queries.csv`, **mọi** POI thuộc danh mục và bán kính của truy vấn đó, sắp theo ID. Claude điền nháp `relevance` (1 = đáp ứng nhu cầu, 0 = không) và `reason`, ghi `labeled_by = claude-draft`. Người duyệt:

1. Đọc cột `information_need` của truy vấn trong `eval/queries.csv`.
2. Với từng dòng, quyết định POI có đáp ứng nhu cầu đó không, dựa trên nguồn (`source_url`), **không** mở kết quả xếp hạng của app khi đang duyệt.
3. Sửa `relevance`/`reason` nếu không đồng ý. Các dòng Claude ghi "(cần xác nhận)" trong `reason` là chỗ nên xem kỹ nhất (căng tin và nhà hàng chung cho truy vấn "com", căng tin cho "cà phê"/"trà sữa").
4. Xem xong **toàn bộ** thì ký: `python -m scripts.sign_labels --reviewer "Họ tên" --confirm-reviewed`. Lệnh ghi `reviewed_by`/`reviewed_at` cho mọi dòng chưa có người duyệt; chưa xem hết thì đừng chạy.
5. Chạy `python -m scripts.evaluate --check-only`, rồi `python -m scripts.evaluate`.

Người duyệt: ______________________  Ngày duyệt xong: ____________  Số dòng đã sửa so với nháp: ______
