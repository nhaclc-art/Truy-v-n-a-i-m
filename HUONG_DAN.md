# GeoRank HCMUE — Hướng dẫn sử dụng và giải thích kỹ thuật

Tài liệu này dành cho người dùng ứng dụng, người trình bày demo và người muốn hiểu hệ thống hoạt động thế nào. Cài đặt và bàn giao xem `README.md`; giới hạn đã biết xem `KNOWN_LIMITATIONS.md`; nguồn dữ liệu xem `DATA_SOURCES.md`.

**Mục lục**

- Phần A — Sử dụng ứng dụng: 1. Khởi động · 2. Giao diện · 3. Tìm kiếm · 4. Danh mục và bán kính · 5. Ba cách xếp hạng · 6. Vị trí gốc · 7. Thẻ kết quả · 8. Chỉ đường · 9. Geofence · 10. Bảng giải thích kết quả · 11. Kịch bản demo · 12. Xử lý sự cố
- Phần B — Quản lý dữ liệu và đánh giá: 13. Luồng dữ liệu · 14. Thêm/sửa địa điểm · 15. Đánh giá IR · 16. Xuất source
- Phần C — Giải thích kỹ thuật: 17. Kiến trúc · 18. Mô hình dữ liệu · 19. Tiền xử lý văn bản · 20. Chỉ mục đảo FTS5 · 21. BM25 · 22. Không gian · 23. Xếp hạng · 24. API · 25. Giao diện web · 26. Định vị · 27. Chỉ đường · 28. Geofence · 29. Chỉ số đánh giá và kết quả · 30. Kiểm thử · 31. Bảng công nghệ · 32. Đã cài và chưa cài · 33. Thuật ngữ

---

# Phần A — Sử dụng ứng dụng

## 1. Khởi động

Trong thư mục chứa `app.py`, sau khi đã cài theo `README.md`:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_pois data\pois.csv --replace
.\.venv\Scripts\python.exe app.py
```

Mở http://127.0.0.1:5000 bằng Chrome hoặc Edge. Lần đầu nên tải lại bằng Ctrl+F5 để trình duyệt không dùng file cũ.

## 2. Giao diện

| Vùng | Nội dung |
| --- | --- |
| Thanh trên cùng | Tên hệ thống, tên cơ sở, phiên bản dữ liệu (`Dữ liệu ds-…`), nút **Hướng dẫn** (mở hộp hướng dẫn nhanh ngay trong ứng dụng) |
| Cột trái (máy tính) / bảng trượt (điện thoại) | Ô tìm kiếm; chip danh mục; chọn bán kính; chọn cách xếp hạng; thẻ **Vị trí gốc**; danh sách kết quả; bảng **Giải thích kết quả** |
| Bản đồ | Marker tròn đánh số theo thứ hạng, màu theo danh mục; chấm vị trí gốc; vòng tròn bán kính; thẻ **Chỉ đường** và **Geofence** nổi ở góc trên trái khi đang dùng; chú giải màu (góc dưới trái); nút phóng to/thu nhỏ (góc trên phải); ghi nguồn © OpenStreetMap (góc dưới phải) |

**Trên điện thoại** (màn hình rộng dưới 900 px): bản đồ phủ toàn màn hình; danh sách nằm trong bảng trượt ở dưới với ba mức cao (thấp: chỉ ô tìm kiếm và danh mục; nửa màn hình; gần đầy). Chạm thanh xám ở đầu bảng để chuyển mức, hoặc kéo thanh lên/xuống. Chạm một kết quả thì bảng hạ xuống và bản đồ đưa marker vào phần còn nhìn thấy; chạm marker thì bảng mở nửa và cuộn tới thẻ. Chạm ô tìm kiếm thì bảng mở gần đầy. Nút tròn góc phải bản đồ bật/tắt vị trí của bạn. Chú giải và ghi nguồn bản đồ luôn nằm trên mép bảng trượt.

Màu danh mục: ăn uống cam, cửa hàng tiện lợi xanh lá, văn phòng phẩm/photocopy tím, nhà trọ xanh dương, trạm xăng hồng đậm, trạm xe buýt xanh ngọc. Số trên marker trùng số thứ tự trong danh sách.

## 3. Tìm kiếm

- Gõ từ khóa vào ô tìm kiếm; kết quả cập nhật sau khoảng 0,3 giây, không cần bấm Enter.
- Có dấu hay không dấu đều được: "văn phòng phẩm", "van phong pham", "VĂN PHÒNG PHẨM" cho cùng kết quả. Chữ "đ" gõ "d" cũng được.
- Một số viết tắt được hiểu sẵn: `vpp` = văn phòng phẩm, `photo` = photocopy, `cafe`/`coffee` = cà phê, `bus` = xe buýt.
- Mọi từ gõ vào đều phải xuất hiện trong tên, danh mục, mô tả hoặc thẻ mô tả của địa điểm (phép AND). Gõ thêm từ thì kết quả hẹp lại.
- Để trống ô tìm kiếm: ứng dụng liệt kê mọi địa điểm trong bán kính, sắp theo khoảng cách ("duyệt theo vị trí").
- Ký tự lạ như `"`, `*`, `<b>` được coi là chữ bình thường, không gây lỗi.
- Hệ thống chỉ hiểu từ khóa. Câu tự nhiên kiểu "quán rẻ đang mở gần trường" sẽ không cho kết quả như mong muốn.

Ví dụ nên thử: `photocopy`, `van phong pham`, `cà phê`, `circle k`, `Demon Kitchen`, `com`, `trà sữa`, `cây xăng`, `xe buýt`, `phòng trọ`, `pizza`.

## 4. Danh mục và bán kính

- **Chip danh mục**: "Tất cả" hoặc một trong 6 nhóm. Chọn danh mục thì chỉ còn địa điểm thuộc nhóm đó.
- **Bán kính**: 300 m, 500 m, 1 km (mặc định), 2 km, tính từ vị trí gốc theo đường chim bay. Đổi bán kính thì vòng tròn trên bản đồ đổi theo và bản đồ phóng vừa vòng tròn.

## 5. Ba cách xếp hạng

| Nút | Sắp theo | Nên dùng khi |
| --- | --- | --- |
| **Gần nhất** (mặc định) | Khoảng cách tăng dần | Mọi kết quả đều dùng được như nhau, chỉ cần chỗ gần nhất (cây xăng, trạm xe buýt, Circle K) |
| **Đúng từ khóa** | Điểm BM25: địa điểm khớp từ khóa rõ nhất lên đầu | Từ khóa mô tả loại quán, dữ liệu gắn nhãn rộng (ví dụ "cà phê", "văn phòng phẩm") |
| **Kết hợp** | 60% điểm văn bản + 40% điểm gần | Muốn cân bằng giữa đúng loại và gần |

Cả ba cách dùng **cùng một tập kết quả**, chỉ khác thứ tự. Khi ô tìm kiếm trống, mọi cách đều sắp theo khoảng cách vì không có điểm văn bản. Rê chuột lên nút để xem mô tả ngắn.

## 6. Vị trí gốc

Thẻ **Vị trí gốc** luôn ghi rõ đang dùng loại vị trí nào:

| Nhãn | Ý nghĩa | Cách bật |
| --- | --- | --- |
| **THAM CHIẾU** (xanh dương) | Tâm khuôn viên cơ sở 280 An Dương Vương theo OpenStreetMap. Không phải cổng, cũng không phải vị trí của bạn | Mặc định, hoặc bấm **Tâm khuôn viên** |
| **VỊ TRÍ THẬT** (xanh ngọc) | Vị trí trình duyệt cung cấp, kèm sai số ±m và giờ cập nhật; bản đồ có vòng sai số | Bấm **Vị trí của tôi**, cho phép quyền vị trí. Bấm lại để tắt |
| **MÔ PHỎNG** (cam) | Vị trí giả lập để trình diễn: bấm vào bản đồ hoặc kéo chấm cam | Bấm **Mô phỏng**. Bấm lại để quay về tham chiếu |

Khi vị trí gốc đổi, khoảng cách và thứ hạng được tính lại ngay. Nếu trình duyệt từ chối quyền vị trí, ứng dụng báo lỗi và **không** tự chuyển sang mô phỏng. Trên máy tính, trình duyệt thường định vị theo Wi-Fi/IP nên sai số có thể hàng trăm mét; khi đó nên trình diễn bằng mô phỏng.

## 7. Thẻ kết quả

Mỗi thẻ gồm: số thứ tự (màu danh mục), tên, khoảng cách đường chim bay, danh mục và địa chỉ, nguồn dữ liệu (bấm để mở trang OpenStreetMap hoặc tin đăng), trạng thái kiểm chứng:

- **chưa đối chiếu**: mới có một nguồn;
- **đã đối chiếu**: đã so với nguồn thứ hai (Foody, bài đăng của quán, Google Maps do người kiểm tra xem);
- **đã kiểm tra thực địa**: có người đến tận nơi.

Bấm vào thẻ thì bản đồ di tới marker và mở popup; bấm marker thì thẻ tương ứng được tô viền và cuộn tới. Rê chuột lên thẻ thì marker phóng to.

## 8. Chỉ đường

1. Chọn vị trí gốc (tham chiếu, thật hoặc mô phỏng).
2. Bấm **Chỉ đường** trên thẻ địa điểm.
3. Thẻ **Chỉ đường đi bộ** nổi ở góc trên trái bản đồ, hiện: quãng đường theo tuyến, số phút máy chủ ước tính, khoảng cách đường chim bay (để so sánh). Bản đồ vẽ tuyến màu xanh bám theo phố. Bấm × để đóng.
4. Nút **Mở Google Maps** mở chỉ đường đi bộ ở trang Google Maps (ngoài ứng dụng), dùng khi cần dẫn đường chi tiết.

Nếu vị trí gốc thay đổi sau khi đã có tuyến, thẻ hiện **Tính lại tuyến**. Nếu máy chủ chỉ đường lỗi hoặc mất mạng, ứng dụng báo lỗi và không vẽ đường giả; vẫn còn nút Google Maps. Tuyến chỉ dành cho người **đi bộ**.

## 9. Geofence (thông báo vào/ra vùng)

1. Bấm **Theo dõi 100 m** trên thẻ địa điểm. Bản đồ vẽ vòng đặc 100 m (vùng vào) và vòng nét đứt 130 m (vùng ra).
2. Bật **Vị trí của tôi** hoặc **Mô phỏng**. Ở chế độ tham chiếu, geofence không chạy vì tâm khuôn viên không di chuyển.
3. Thẻ **Geofence** nổi trên bản đồ hiện trạng thái (Chưa rõ / Ngoài vùng / Trong vùng), khoảng cách, tiến độ xác nhận ("đang xác nhận 1/2") và **Nhật ký sự kiện** (bấm để mở/thu gọn; trên điện thoại mặc định thu gọn). Thẻ chỉ cập nhật khi trạng thái hoặc khoảng cách đổi, nên danh sách và nhật ký không bị giật khi đang cuộn.
4. Khi xác nhận vào hoặc ra vùng, ứng dụng hiện thông báo nổi và ghi nhật ký kèm giờ, tên địa điểm, loại vị trí.

Quy tắc: vào khi cách ≤ 100 m, ra khi cách ≥ 130 m; khoảng giữa 100–130 m giữ trạng thái cũ để không báo liên tục; cần 2 mẫu vị trí liên tiếp; mẫu định vị có sai số > 50 m bị bỏ qua; hai thông báo nổi cách nhau ít nhất 30 giây (sự kiện vẫn được ghi nhật ký). Mẫu đầu tiên chỉ khởi tạo trạng thái, không tính là "vừa vào". Ở chế độ mô phỏng, ứng dụng lấy 1 mẫu mỗi giây tại chấm cam: đặt chấm ngoài vòng, đợi 2 giây, kéo vào trong vòng, khoảng 2 giây sau sẽ có sự kiện "Vào vùng".

Đổi địa điểm theo dõi, đổi loại vị trí hoặc bấm **Dừng theo dõi** thì trạng thái được đặt lại. Geofence chỉ chạy khi trang đang mở.

## 10. Bảng "Giải thích kết quả"

Bấm **Giải thích kết quả** dưới danh sách để mở. Bảng cho thấy hệ thống đã xử lý truy vấn thế nào:

| Dòng | Ý nghĩa |
| --- | --- |
| Query gốc / Query chuẩn hóa | Chuỗi bạn gõ và chuỗi sau khi bỏ dấu, đổi đ→d, chữ thường, mở rộng viết tắt |
| Biểu thức FTS5 | Biểu thức thật gửi vào chỉ mục, ví dụ `"ca" "phe"` (mỗi token trong ngoặc kép, nối AND) |
| Vị trí gốc, Bán kính, Danh mục | Tham số đã dùng |
| Xếp hạng | Cách xếp yêu cầu và cách xếp thực tế (khác nhau khi query rỗng) |
| Khớp văn bản → Sau lọc danh mục → Sau lọc bán kính | Số ứng viên sau từng bước, cùng một lần xử lý |
| Hiển thị | Số kết quả trả về (tối đa 50) |
| Thời gian xử lý server | Chỉ đo phần xử lý trên server |
| Dataset | Phiên bản dữ liệu |

Bảng điểm bên dưới có với từng kết quả: **BM25 thô** (càng âm càng khớp), **text_norm** (điểm văn bản chuẩn hóa 0–1), **khoảng cách (m)**, **geo_norm** (điểm gần 0–1), **điểm kết hợp**. So cột tương ứng để hiểu vì sao một địa điểm đứng trên địa điểm khác.

## 10A. Vì sao không thấy một địa điểm? (why-not)

Bảng giải thích trả lời "vì sao kết quả này ở đây". Chức năng why-not trả lời câu ngược lại: **vì sao chỗ tôi mong đợi không có trong 5 kết quả đầu**.

1. Bấm **Không thấy chỗ bạn cần?** cạnh dòng trạng thái. Khi danh sách rỗng, nút này cũng nằm trong thông báo "Không có kết quả". Thẻ tím mở trên bản đồ.
2. Gõ tên chỗ bạn mong thấy rồi chọn trong danh sách gợi ý. Mỗi gợi ý có địa chỉ và khoảng cách để phân biệt các chi nhánh trùng tên. Chọn xong là ứng dụng phân tích ngay.
3. Bản đồ đánh dấu địa điểm đó bằng vòng tím có dấu "?".
4. **Thanh 4 bước** cho thấy địa điểm đi tới đâu trong quá trình xử lý truy vấn:
   - Các bước: Khớp từ khóa → Danh mục → Bán kính → 5 kết quả đầu.
   - Ký hiệu: ✓ qua, ✗ bị loại ở bước này, – không áp dụng (ví dụ không lọc danh mục), … chưa tới bước này.
5. Bên dưới là **một câu lý do** cho từng bước bị loại, dùng đúng từ bạn đã gõ (có dấu):
   - Thiếu từ khóa: "Dữ liệu của địa điểm không có từ “sáng”". Mở **Dữ liệu của địa điểm** để xem chính văn bản được tìm kiếm.
   - Khác danh mục.
   - Ngoài bán kính (kèm khoảng cách thật).
   - Xếp hạng thấp (vì xa hơn, hay vì khớp từ khóa yếu hơn).
6. **Cách để thấy nó** hiện 3 cách sửa truy vấn ít nhất; các cách còn lại nằm trong **Cách khác**. Mỗi cách nói kết quả sẽ ra sao, ví dụ "Nới bán kính lên 500 m → vào 5 kết quả đầu (hạng 2)". Các loại cách sửa:
   - nới bán kính;
   - bỏ lọc danh mục;
   - bỏ từ;
   - thêm một từ **trong tên** địa điểm;
   - xếp theo cách khác;
   - ưu tiên khoảng cách hoặc từ khóa hơn (chỉnh trọng số α);
   - nếu địa điểm vẫn nằm trong danh sách: **Xem trong danh sách**.
7. Bấm **Áp dụng**: ô tìm kiếm, bộ lọc và α được đặt theo đề xuất. Danh sách chạy lại, địa điểm được chọn trên bản đồ, thẻ tím tự hỏi lại và báo "đã có trong … kết quả đầu".
   - Nếu đề xuất có α, dòng tím phía trên danh sách hiện α đang dùng. Bấm **Về mặc định** để trả về 0,6.
8. **Chi tiết kỹ thuật** (thu gọn) có penalty, Δk, Δq, tỷ lệ giữ kết quả cũ, số phương án đã xét và thời gian xử lý, dùng khi giải thích với giảng viên.

## 10B. Gõ sai, gõ dính, sót chữ Telex

Ứng dụng tự sửa những từ **không có trong dữ liệu** và báo ngay dưới dòng trạng thái:

- Ví dụ: `Đã hiểu “photocoppy” là “photocopy”`.
- Bấm **Tìm đúng như đã gõ** để tắt việc sửa cho câu đang gõ. Gõ câu mới là việc sửa tự bật lại.

| Kiểu lỗi | Ví dụ | Hiểu thành |
| --- | --- | --- |
| Sai, thừa, thiếu, đảo chữ | photocoppy, piza, circel k | photocopy, pizza, circle k |
| Sót chữ Telex | tra suwa, caay xawng, xe buyts | trà sữa, cây xăng, xe buýt |
| Gõ dính | circlek, vanphongpham, xebuyt | circle k, văn phòng phẩm, xe buýt |
| Gõ tách | piz za | pizza |
| Sai dấu | trà sũa | trà sữa (dấu vốn bị bỏ khi chuẩn hóa) |

Ứng dụng **không** sửa các trường hợp sau, để tránh đổi nghĩa câu:

- từ ngắn dưới 4 ký tự (vì vậy "caf phee" vẫn không tìm được);
- số;
- từ là âm tiết tiếng Việt hợp lệ. Ví dụ "ăn sáng" không bị đổi thành "ăn hàng" dù dữ liệu không có từ "sáng". Khi đó hãy dùng why-not để xem dữ liệu thiếu gì.

Bảng **Giải thích kết quả** có dòng "Sửa lỗi gõ" ghi lại các chỗ đã sửa.

## 10C. Tìm bằng giọng nói

1. Bấm biểu tượng **micro** trong ô tìm kiếm. Lần đầu, trình duyệt hỏi quyền micro: chọn Cho phép.
2. Nút chuyển đỏ và nhấp nháy khi đang nghe. Nói ngắn, ví dụ "cây xăng", "trà sữa", "phòng trọ". Chữ hiện dần vào ô tìm kiếm; nói xong vài giây là ứng dụng tự tìm.
3. Dòng xanh **Nghe được “…” (độ tin cậy …)** cho biết câu trình duyệt nhận được. Nếu nghe nhầm, bấm một cách nghe khác trong phần **Hay là:**.
4. Câu nghe được đi qua cùng bước sửa lỗi gõ ở mục 10B. Ví dụ "phô tô cóp pi" được gộp thành "photocopy".
5. **Tải nhật ký giọng nói** lưu các câu đã nói trong phiên ra `voice_log.csv`, dùng làm dữ liệu đánh giá (mục 15C).

Điều kiện để micro hoạt động:

- **Trình duyệt**: Chrome, Edge (máy tính, Android), Safari iOS 14.5 trở lên (cần bật Đọc chính tả/Siri). Firefox không hỗ trợ: nút micro bị ẩn, các chức năng khác vẫn chạy.
- **Internet**: trình duyệt gửi âm thanh tới dịch vụ nhận dạng của hãng (Google với Chrome/Edge, Apple với Safari). Ứng dụng không nhận, không lưu âm thanh.
- **Trang mở qua HTTPS hoặc localhost** và người dùng cho phép micro (mục 10D).

## 10E. Tìm bằng ảnh biển hiệu

**Chuẩn bị một lần** (cần mạng): tải bộ đọc chữ khoảng 12 MB vào `static/vendor/tesseract/`. Các file này không commit.

```powershell
.\.venv\Scripts\python.exe -m scripts.vendor_tesseract
```

**Sử dụng:**

1. Bấm biểu tượng **máy ảnh** trong ô tìm kiếm. Điện thoại mở camera sau (hoặc cho chọn ảnh có sẵn); máy tính mở hộp chọn file.
2. Thẻ cam **Đọc biển hiệu** hiện ảnh và tiến độ. Lần đầu phải nạp bộ đọc chữ và dữ liệu tiếng Việt, tiếng Anh (vài giây); các lần sau nhanh hơn vì trình duyệt đã lưu.
3. Chữ được đọc **ngay trong trình duyệt**, ảnh không gửi đi đâu. Chỉ đoạn chữ đọc được được gửi lên máy chủ để dựng truy vấn:
   - bỏ số (số nhà, điện thoại), từ không có trong dữ liệu, từ quá phổ biến;
   - sửa nhầm ký tự hay gặp của OCR ("C1RCLE" → circle) và lỗi gõ;
   - giữ tối đa 10 từ hiếm nhất.
4. Ứng dụng tự tìm theo kiểu **khớp bất kỳ từ nào** (OR), xếp theo độ khớp từ khóa, bán kính 2 km, bỏ lọc danh mục. Thẻ hiện **Có thể là:** 3 địa điểm đầu và tự chọn địa điểm đầu trên bản đồ.
5. Mở **Chữ đọc được** để xem đoạn chữ gốc. Mở **Đã bỏ … từ** để xem lý do bỏ từng từ.
6. Dòng cam phía trên danh sách nhắc đang tìm theo chữ trên ảnh; bấm **Tìm như bình thường** để về kiểu nối AND. Gõ câu mới cũng tự về kiểu thường.
7. **Tải nhật ký ảnh** lưu chữ đọc được và kết quả của các lần chụp (không lưu ảnh), dùng để đánh giá (mục 15D).

Mẹo chụp: đứng thẳng trước biển, chữ chiếm phần lớn khung hình, đủ sáng. Biển có chữ cách điệu, chữ nghiêng hoặc đèn LED thường đọc kém.

## 10F. Lập lộ trình nhiều chặng

Ví dụ nhu cầu: "có 5 giờ, muốn đi cà phê → ăn tối → xem phim, tổng quãng đường dưới một mức nào đó". Đây **không phải** tìm kiếm top-k như các mục trên: là bài toán chọn một địa điểm cho **mỗi** chặng, theo đúng thứ tự, sao cho tổng quãng đường di chuyển nằm trong một ngân sách. Khác với bài toán "điểm hẹn cho nhiều người" (nhiều người, một điểm gặp): ở đây chỉ có một người, nhiều điểm dừng nối tiếp.

1. Bấm **Lập lộ trình nhiều chặng** cạnh dòng trạng thái.
2. Gõ từ khóa cho mỗi chặng, theo đúng thứ tự sẽ đi qua (gợi ý sẵn: cà phê → cơm → phim). Bấm **+ Thêm chặng** / **− Bớt chặng** để đổi số chặng (2–4). Mỗi chặng dùng đúng bộ tìm kiếm và sửa lỗi gõ như ô tìm kiếm chính.
3. Chọn **tổng quãng đường tối đa** và **thời gian dự kiến ở mỗi chặng** (phút, áp dụng cho mọi chặng), rồi bấm **Lập lộ trình**.
4. Ứng dụng thử **mọi tổ hợp** địa điểm khớp từ khóa từng chặng (giới hạn 8 ứng viên khớp tốt nhất mỗi chặng), tính tổng quãng đường bằng **đường chim bay nhân hệ số quanh co 1,3** (ước tính đường phố không đi thẳng, đặt tay — không phải quãng đường thật), loại tổ hợp vượt ngân sách và tổ hợp dùng lại cùng một địa điểm ở hai chặng.
5. Hiện tối đa 3 lộ trình, xếp theo `0,5 × độ khớp từ khóa trung bình + 0,5 × độ ngắn`. Nếu không có lộ trình nào lọt ngân sách, ứng dụng báo lộ trình ngắn nhất tìm được để bạn nới ngân sách.
6. Bấm **Xem trên bản đồ** trên một lộ trình để đánh số các chặng và vẽ đường ước tính (nét đứt hồng).
7. Bấm **Chỉ đường thật cho lộ trình đang xem** để tính lại **từng chặng bằng máy chủ chỉ đường thật (OSRM)** — gọi lại đúng API chỉ đường đã dùng cho một địa điểm, không thêm máy chủ ngoài nào. Quãng đường thật hiện riêng, không thay số ước tính phía trên.
8. Nếu bạn nhớ một chỗ khác mà không thấy ở một chặng, bấm **Vì sao thiếu chỗ khác ở chặng này?** dưới chặng đó: mở đúng thẻ **Vì sao không thấy?** (mục 10A) nhưng theo từ khóa và bán kính của chặng, không theo ô tìm kiếm chính.

**Không xử lý**: giờ chiếu phim, giờ mở cửa, tình trạng còn phòng/còn chỗ. "5 giờ" hay bất kỳ ngân sách thời gian nào chỉ là đi bộ ước tính cộng thời gian ở mỗi chặng do bạn tự nhập — không tra được từ dữ liệu hiện có.

**Vì sao gợi ý sẵn chặng "phim" luôn báo không khớp:** corpus không có danh mục rạp phim (mục Không xử lý ở trên); đây là kết quả **đúng**, không phải lỗi — hệ thống trả lời trung thực là chưa có dữ liệu, không đoán bừa. Với gợi ý sẵn (cà phê → cơm → phim) sẽ không có lộ trình nào vì thiếu đúng một chặng. Để xem đủ lộ trình 3 chặng thật, đổi chặng "phim" sang một từ khóa có trong dữ liệu, ví dụ "xe buýt", trong mục **Đổi chặng hoặc ngân sách** rồi bấm lại **Lập lộ trình**.

## 10D. Dùng trên điện thoại

Giao diện đã làm cho màn hình hẹp:

- bản đồ toàn màn hình, danh sách là bảng trượt;
- thẻ why-not, chỉ đường, geofence nổi phía trên bản đồ, không bị bảng che;
- nút và ô nhập đủ lớn để chạm; ô nhập 16px nên iOS không tự phóng to.

Điểm khó là **micro và định vị chỉ chạy trong môi trường an toàn** (HTTPS hoặc `localhost`). Mở từ điện thoại qua địa chỉ mạng LAN `http://192.168.x.x:5000` thì trình duyệt chặn cả hai. Có hai cách:

**Cách 1: Android + cáp USB (không đưa trang ra Internet).**

1. Trên điện thoại: bật Tùy chọn nhà phát triển → Gỡ lỗi USB, cắm cáp vào máy tính.
2. Trên máy tính: Chrome → `chrome://inspect/#devices` → **Port forwarding…** → thêm `5000` → `localhost:5000`, tích **Enable port forwarding**.
3. Trên điện thoại: Chrome mở `http://localhost:5000`. Đây là localhost nên micro và định vị dùng được.

**Cách 2: đường hầm HTTPS tạm (Android và iPhone).**

Cách này đưa trang ra Internet qua một địa chỉ ngẫu nhiên. **Ai có địa chỉ đều mở được trong lúc lệnh còn chạy.** Tắt lệnh (Ctrl+C) ngay sau khi demo. Cài một lần:

```powershell
winget install --id Cloudflare.cloudflared
```

Mỗi lần demo, chạy app ở một cửa sổ PowerShell, rồi chạy đường hầm ở cửa sổ thứ hai:

```powershell
.\.venv\Scripts\python.exe app.py
cloudflared tunnel --url http://127.0.0.1:5000
```

Mở địa chỉ `https://….trycloudflare.com` mà lệnh in ra trên điện thoại. Đây là Quick Tunnel miễn phí của Cloudflare, không cần tài khoản. Mức 0 trong `docs/planning/07_KE_HOACH_APP.md`.

Kiểm tra trên điện thoại theo `MANUAL_CHECKS.md` phần E (ca E11, E12).

## 11. Kịch bản demo 5–7 phút

1. Giới thiệu bài toán và cơ sở; chỉ phiên bản dữ liệu ở góc trên.
2. Gõ "văn phòng phẩm", rồi "van phong pham": cùng kết quả; chỉ marker và danh sách khớp số.
3. Mời người xem tự chọn một tên quán trên bản đồ và gõ tìm (không dùng query chuẩn bị sẵn).
4. Gõ "cà phê", chuyển Gần nhất → Đúng từ khóa → Kết hợp; mở **Giải thích kết quả**, chỉ số ứng viên và cột điểm giải thích vì sao thứ tự đổi.
4a. **Why-not** (phần mới): vẫn "cà phê" 500 m, chế độ Gần nhất. Bấm **Không thấy chỗ bạn cần?**, gõ "Thềm Xưa": thanh 4 bước dừng ở "5 kết quả đầu", lý do "xa hơn". Bấm **Áp dụng** cách đầu tiên: quán vào 5 kết quả đầu. Tiếp theo chọn "Ăn uống", gõ "circle k" 300 m (không có kết quả), hỏi Circle K: bước **Danh mục** bị ✗. Gõ "ăn sáng", hỏi Canteen SGU: bước **Khớp từ khóa** bị ✗; mở "Dữ liệu của địa điểm" thấy OSM chỉ ghi "breakfast" (một lỗi dữ liệu mà why-not làm lộ ra).
4b. **Sửa lỗi gõ**: gõ "photocoppy", rồi "tra suwa", "circlek": dòng xanh báo đã hiểu thành gì; bấm **Tìm đúng như đã gõ** để thấy kết quả rỗng khi không sửa.
4c. **Giọng nói**: bấm micro, nói "cây xăng", rồi "phòng trọ": câu nghe được hiện ở dòng xanh và được tìm ngay. Nếu có điện thoại (mục 10D), làm lại trên điện thoại.
4d. **Ảnh biển hiệu**: bấm máy ảnh, chọn ảnh biển Circle K (hoặc chụp thật bằng điện thoại). Thẻ cam hiện chữ đọc được, các từ đã bỏ (số điện thoại, "www"…) và "Có thể là: Circle K". Mở `eval/ocr_summary.md` để so cách A (dán nguyên văn, AND) với cách C (hệ thống) trên ảnh thật đã chụp.
5. Bấm **Vị trí của tôi** nếu phòng cho phép, sau đó chuyển sang **Mô phỏng**, kéo chấm cam: khoảng cách và thứ hạng đổi theo.
6. Chọn một quán, bấm **Chỉ đường**: chỉ quãng đường theo tuyến và khoảng cách đường chim bay.
7. Bấm **Theo dõi 100 m**, kéo chấm cam vào rồi ra khỏi vòng: một sự kiện vào, một sự kiện ra, không báo lặp khi kéo quanh mép.
8. Import `data\updates\them_poi_osm.csv`, tìm "pho bac hai": địa điểm mới xuất hiện mà không sửa mã, không khởi động lại.
9. Mở `eval/summary.md`: Precision@5, Recall@5 của ba cách xếp hạng.
10. Nêu giới hạn: corpus nhỏ, dữ liệu snapshot, nhà trọ ít, geofence chỉ khi trang mở, bản đồ và chỉ đường cần mạng.

## 12. Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
| --- | --- | --- |
| "DB chưa sẵn sàng" | Chưa import dữ liệu | Chạy lệnh import ở mục 1 |
| Bản đồ xám hoặc báo lỗi tile | Mất mạng, hoặc trình duyệt giữ file cũ | Kiểm tra Internet, tải lại bằng Ctrl+F5. Tìm kiếm vẫn chạy khi không có bản đồ nền |
| "Bạn đã từ chối quyền vị trí" | Quyền vị trí bị chặn | Bấm biểu tượng ổ khóa trên thanh địa chỉ → Vị trí → Cho phép, tải lại; hoặc dùng Mô phỏng |
| Vị trí thật lệch nhiều | Máy tính định vị theo Wi-Fi/IP | Dùng điện thoại hoặc Mô phỏng |
| Không lấy được tuyến | Máy chủ chỉ đường công cộng bận hoặc mất mạng | Thử lại sau, hoặc bấm Mở Google Maps |
| Không có kết quả | Thiếu một từ trong dữ liệu (phép AND), bán kính nhỏ, đang lọc danh mục | Bớt từ, tăng bán kính, chọn "Tất cả" |
| PowerShell chặn `Activate.ps1` | Chính sách chạy script | Gọi thẳng `.\.venv\Scripts\python.exe` |
| CSV mở bằng Excel bị lỗi dấu | Excel lưu sai mã hóa | Lưu bằng định dạng **CSV UTF-8**, hoặc sửa bằng VS Code |

---

# Phần B — Quản lý dữ liệu và đánh giá

## 13. Luồng dữ liệu

```text
Overpass API (OSM) ──fetch_osm──► data/raw/osm_<giờ>.json (+ .meta.json: truy vấn, thời điểm, sha256)
                                     │
data/manual/*.csv (nhà trọ) ─────────┤
                                     ▼
                     build_draft (luật chọn trong config/osm_corpus.json)
                                     │
                                     ▼
                           data/pois_draft.csv
                                     │
data/review_sheet.csv ──apply_review─┤   (tên thật, địa chỉ, tọa độ đúng, trạng thái kiểm chứng)
                                     ▼
                              data/pois.csv   ◄── nguồn duy nhất của corpus
                                     │
                          import_pois (kiểm tra → upsert → dựng lại chỉ mục)
                                     ▼
                  data/georank.db (bảng pois + chỉ mục FTS5 + meta)
```

Lệnh đầy đủ:

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_osm            # tải snapshot mới (cần mạng)
.\.venv\Scripts\python.exe -m scripts.build_draft          # dựng bản nháp
.\.venv\Scripts\python.exe -m scripts.apply_review         # áp kết quả duyệt → data/pois.csv
.\.venv\Scripts\python.exe -m scripts.import_pois data\pois.csv --replace
.\.venv\Scripts\python.exe -m scripts.make_review_sheet    # thêm địa điểm mới vào bảng duyệt
.\.venv\Scripts\python.exe -m scripts.make_label_sheet     # thêm dòng nhãn cho địa điểm mới
```

**Luật chọn corpus** (tránh chọn tay theo ý): chỉ nhận địa điểm có tên (thiếu tên thì lấy thương hiệu; địa điểm không tên trong 300 m được nhận với nhãn tạm "(chưa rõ tên)" để người kiểm tra điền); lấy hết địa điểm trong 500 m; xa hơn thì giới hạn số lượng mỗi vòng 1 km và 2 km, ưu tiên bản ghi có địa chỉ, loại món, giờ mở cửa; gộp bản ghi trùng tên trong 30 m.

**Bảng duyệt** `data/review_sheet.csv`: mỗi dòng một địa điểm, có link nguồn, link OpenStreetMap và Google Maps đúng tọa độ. Người kiểm tra điền `ket_qua` (`dung`, `dung_tai_cho`, `sai`, `dong_cua`, `khong_ro`), tên/địa chỉ/danh mục/tọa độ đúng nếu sai, ghi chú nguồn, tên và ngày. `apply_review` biến kết quả thành trạng thái kiểm chứng; `dong_cua` bị loại khỏi corpus.

## 14. Thêm hoặc sửa một địa điểm

- **Sửa nhanh**: sửa dòng trong `data/pois.csv`, chạy lại import. Lưu ý: lần chạy `apply_review` sau sẽ ghi đè `pois.csv` từ bản nháp; muốn sửa bền vững thì ghi vào `data/review_sheet.csv` hoặc thêm file vào `data/manual/`.
- **Thêm nguồn thủ công**: tạo CSV cùng cột với `pois.csv` trong `data/manual/`, chạy `build_draft` → `apply_review` → import.
- **Thử nhanh không sửa mã**: `import_pois data\updates\them_poi_osm.csv` thêm quán Phở Bắc Hải; tìm "pho bac hai" thấy ngay. Lần import `--replace` kế tiếp sẽ xóa nó vì không có trong `pois.csv`.

Import từ chối cả file nếu có một dòng lỗi (thiếu nguồn, tọa độ sai, ngoài 2 km, danh mục lạ, có cột lạ như điểm BM25…). Chạy lặp cùng file không sinh bản ghi trùng. Ứng dụng đang chạy thấy dữ liệu mới ở request kế tiếp.

## 15. Đánh giá IR

1. `eval/queries.csv`: 12 truy vấn, mỗi truy vấn có nhu cầu cụ thể, vị trí gốc, bán kính, danh mục.
2. `make_label_sheet` tạo `eval/qrels.csv`: mọi địa điểm trong phạm vi (danh mục + bán kính) của từng truy vấn, sắp theo ID.
3. Gán nhãn `relevance` 1/0 và lý do, dựa trên nhu cầu và nguồn, **không** nhìn kết quả xếp hạng.
4. Người duyệt xem hết rồi ký: `scripts.sign_labels --reviewer "Họ tên" --confirm-reviewed`.
5. `scripts.evaluate --check-only` kiểm nhãn đủ và đã ký; `scripts.evaluate` ghi `eval/results.csv` (thứ hạng từng chế độ), `eval/metrics.csv` (chỉ số từng truy vấn), `eval/summary.md` (tóm tắt, hash cấu hình và nhãn).

Nếu nhãn thiếu hoặc chưa ký, script báo **R5 BLOCKED** và không ghi kết quả. Không chỉnh trọng số xếp hạng theo bộ truy vấn này rồi gọi là đánh giá độc lập.

## 15A. Đánh giá why-not

Hai nguồn câu hỏi:

1. **Từ nhãn R5 (tự động)**: với mỗi truy vấn và mỗi chế độ xếp hạng, mỗi địa điểm liên quan (nhãn 1) nằm ngoài top 5 là một câu hỏi "vì sao không có?". Không cần gán nhãn mới.
2. **Soạn tay** `eval/whynot_questions.csv`: 15 câu, mỗi câu chỉ ra truy vấn, địa điểm mong đợi và **lý do dự kiến** (`TEXT`, `CATEGORY`, `RADIUS`, `RANK`, có thể ghép bằng `+`). Lý do dự kiến dùng để đo độ đúng của chẩn đoán. Claude soạn nháp (`labeled_by = claude-draft`); người duyệt đọc hết, sửa nếu cần, rồi ký.

```powershell
.\.venv\Scripts\python.exe -m scripts.eval_whynot --allow-draft                                     # chạy thử khi câu hỏi soạn tay chưa ký (kết quả ghi NHÁP)
.\.venv\Scripts\python.exe -m scripts.eval_whynot --reviewer "Họ tên người duyệt" --confirm-reviewed  # ký câu hỏi soạn tay
.\.venv\Scripts\python.exe -m scripts.eval_whynot                                                   # chạy chính thức
```

Kết quả ghi vào các file sau:

- `eval/whynot_results.csv`: từng câu hỏi (lý do, đề xuất tốt nhất, penalty, tỷ lệ giữ kết quả cũ, thời gian).
- `eval/whynot_strategies.csv`: từng câu × từng chiến lược sửa.
- `eval/whynot_summary.md`: bảng tổng hợp.
- `eval/whynot_cases.md`: 5 ca dùng cho khảo sát.

**Khảo sát người dùng (thăm dò)**: cho 5–8 bạn xem 5 ca trong `eval/whynot_cases.md` (hoặc xem trình diễn), điền vào `eval/whynot_survey.csv`:

- `nguoi_tra_loi`: tên hoặc biệt danh;
- `case_id`: mã ca;
- `hieu_ly_do_1_5` và `de_xuat_huu_ich_1_5`: điểm 1–5;
- `ghi_chu`: nhận xét tùy ý.

Chạy lại `scripts.eval_whynot` để có bảng điểm trung bình trong `whynot_summary.md`.

## 15B. Đánh giá sửa lỗi gõ

`eval/typo_queries.csv` có 21 biến thể gõ sai của các truy vấn R5. Có 4 loại lỗi: sai chữ, sót chữ Telex, gõ dính, sai dấu. Một biến thể được cố ý giữ để thất bại ("caf phee").

Mỗi biến thể dùng lại vị trí, bán kính, danh mục và **nhãn** của truy vấn gốc, nên không cần gán nhãn mới. Biến thể chạy ở chế độ BM25 hai lần, tắt và bật sửa lỗi gõ.

```powershell
.\.venv\Scripts\python.exe -m scripts.eval_spell    # ghi eval/spell_results.csv, eval/spell_summary.md
```

Các chỉ số cho từng loại lỗi:

- tỷ lệ 5 kết quả đầu **giống truy vấn gõ đúng**;
- tỷ lệ **rỗng**;
- P@5 và nDCG@5.

## 15C. Đánh giá tìm bằng giọng nói

1. **Thu dữ liệu**: mỗi người nói (2–4 người, nếu được thì cả máy tính và điện thoại) mở ứng dụng, bấm micro và đọc lần lượt 12 truy vấn trong `eval/queries.csv`. Nói tự nhiên, mỗi câu một lần. Đọc xong, bấm **Tải nhật ký giọng nói**.
2. **Điền** `eval/voice_queries.csv`, mỗi lần đọc một dòng:
   - `variant_id`: ví dụ V01;
   - `base_query_id`: truy vấn đã đọc, ví dụ Q08;
   - `speaker`: tên hoặc biệt danh người nói;
   - `device`: ví dụ "laptop Chrome", "Android Chrome";
   - `transcript`, `confidence`: chép từ nhật ký;
   - `note`: ghi chú (phòng ồn…).

   Ghi đúng những gì trình duyệt nghe được, **không sửa tay**.
3. Chạy:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.eval_voice    # ghi eval/voice_results.csv, eval/voice_summary.md
   ```

Chỉ số:

- **WER** (tỷ lệ lỗi từ) của câu nghe được so với truy vấn gốc, trước và sau bước sửa lỗi gõ;
- tỷ lệ 5 kết quả đầu giống truy vấn gõ đúng, tỷ lệ rỗng, P@5, nDCG@5 (chế độ BM25, nhãn R5 của truy vấn gốc).

Kết quả được chia theo thiết bị và người nói.

## 15D bis. Kiểm tra nhanh lộ trình nhiều chặng (thăm dò)

Lộ trình nhiều chặng **không đánh giá được bằng P@5/Recall@5/nDCG@5** như R5: đây là bài toán chọn địa điểm theo chuỗi trong một ngân sách, không có khái niệm "địa điểm liên quan" trên từng truy vấn đơn. Thay vào đó, chạy kiểm tra nhanh trên dữ liệu thật:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_itinerary    # in ra màn hình + ghi eval/itinerary_examples.md
```

In ra, với vài bộ chặng ví dụ (3 chặng mặc định, ngân sách hẹp, 2 chặng, 4 chặng): số ứng viên mỗi chặng, số tổ hợp đã xét/lọt ngân sách, lộ trình tốt nhất. Dùng để soát bằng mắt rằng số liệu hợp lý (ví dụ ngân sách hẹp hơn thì ít hoặc không có lộ trình) trước khi kiểm trên giao diện.

## 15D. Đánh giá tìm bằng ảnh biển hiệu

1. **Thu dữ liệu**: chụp 15–20 biển hiệu thật quanh cơ sở bằng nút máy ảnh trong ứng dụng.
   - Phần lớn là quán **có** trong dữ liệu, ví dụ Circle K, GS25, Passio, Pizza Hut, Nhà Hàng Phúc An Khang, Petrolimex.
   - Thêm 3–5 quán **không có** trong dữ liệu (ca âm).
   - Chụp xong bấm **Tải nhật ký ảnh**.
2. **Điền** `eval/ocr_cases.csv`, mỗi ảnh một dòng:
   - `case_id`: ví dụ P01;
   - `target_poi_id`: id của quán đúng trong `data/pois.csv`; **để trống** nếu quán không có trong dữ liệu;
   - `device`: ví dụ "Android Chrome";
   - `ocr_text`, `ocr_confidence`: chép **nguyên văn** từ nhật ký, không sửa tay;
   - `note`: ghi chú, ví dụ "biển LED, chụp buổi tối".
3. Chạy:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.eval_ocr    # ghi eval/ocr_results.csv, eval/ocr_summary.md
   ```

Script so sánh ba cách dựng truy vấn từ cùng một đoạn chữ:

- **A. Gõ nguyên văn**: nối AND, như dán cả đoạn chữ vào ô tìm kiếm.
- **B. OR, không lọc.**
- **C. Cách của hệ thống**: sửa, lọc rồi nối OR.

Chỉ số:

- **Ca dương**: Hit@1, Hit@3, MRR (hạng của quán đúng) và tỷ lệ rỗng.
- **Ca âm**: tỷ lệ "vẫn trả về một quán".
- **Chất lượng OCR**: tỷ lệ từ trong tên quán đúng có mặt trong chữ đọc được, tách riêng khỏi phần truy xuất.

## 16. Xuất source

```powershell
.\.venv\Scripts\python.exe -m scripts.export_source --release v1.0-giuaky
```

Tạo `exports/georank-hcmue-source.zip` chỉ gồm file cần để cài, chạy, test, đánh giá, kèm `MANIFEST.txt` (mã sha256 từng file). Không kèm DB, venv, snapshot thô, bản nháp, file nội bộ. Hướng dẫn đưa lên GitHub: `README.md` mục 10.

---

# Phần C — Giải thích kỹ thuật

## 17. Kiến trúc

```text
Trình duyệt (static/)                                   Flask (app.py) — một tiến trình, chỉ nghe 127.0.0.1
┌──────────────────────────────┐   GET /api/search    ┌──────────────────────────────────────────────┐
│ app.js  điều phối, tìm kiếm  │ ───────────────────► │ search.py  chuẩn hóa → FTS5/BM25 → lọc danh  │
│ map.js  Leaflet, marker      │   GET /api/pois/<id> │            mục → Haversine → 3 cách xếp hạng │
│ location.js  Geolocation     │   GET /api/route     │ routing.py adapter OSRM (FOSSGIS, đi bộ)     │
│ geofence.js  máy trạng thái  │   GET /api/config    │ db.py      SQLite: pois, poi_fts, meta        │
│ api.js  gọi JSON             │ ◄─────────────────── │                                              │
└──────────────────────────────┘                      └───────────────┬──────────────────────────────┘
        │ tile bản đồ                                                  │ chỉ khi bấm Chỉ đường
        ▼                                                              ▼
 tile.openstreetmap.org                                   routing.openstreetmap.de/routed-foot
```

Script dòng lệnh (`scripts/`) làm việc với dữ liệu và đánh giá: `fetch_osm`, `build_draft`, `apply_review`, `import_pois`, `make_review_sheet`, `make_label_sheet`, `sign_labels`, `evaluate`, `export_source`, `vendor_leaflet`, `init_db`.

Mã nguồn chính:

| File | Vai trò |
| --- | --- |
| `src/config.py` | Đọc `config/campus.json`, `app.json`, `aliases.json`, `osm_corpus.json` |
| `src/normalize.py` | Chuẩn hóa và tách token, mở rộng viết tắt |
| `src/geo.py` | Haversine, kiểm tra tọa độ |
| `src/db.py` | Schema SQLite, kết nối, bảng meta, biểu thức `bm25()` |
| `src/importer.py` | Kiểm tra CSV, upsert, dựng lại chỉ mục, tính `dataset_version` |
| `src/review.py` | Áp bảng duyệt lên bản nháp |
| `src/search.py` | Luồng truy vấn và ba cách xếp hạng |
| `src/routing.py` | Gọi máy chủ chỉ đường, liên kết Google Maps |
| `src/evaluation.py` | Chỉ số P@5, R@5, nDCG@5; phạm vi gán nhãn; kiểm tra nhãn |

## 18. Mô hình dữ liệu

Mỗi địa điểm (POI) là một dòng trong `data/pois.csv`: `id` ổn định (ví dụ `osm-node-2614395027`), tên, danh mục, địa chỉ, tọa độ WGS84, mô tả, thẻ mô tả (`tags`), nguồn (`source_url`, `source_type`, `source_id`, `retrieved_at`), trạng thái kiểm chứng (`source_only`, `cross_checked`, `field_checked`), ngày và ghi chú kiểm chứng, link tin đăng cho nhà trọ, giờ mở cửa (chỉ hiển thị).

Văn bản hiển thị giữ nguyên dấu; văn bản đưa vào chỉ mục là bản đã chuẩn hóa. `tags` được sinh từ thẻ OSM theo một bảng dịch công khai (ví dụ `amenity=cafe` → "quán cà phê", `cuisine=rice` → "cơm"), không đặt riêng cho từng quán.

`dataset_version` = `ds-` + 10 ký tự đầu của SHA-256 toàn bộ nội dung bảng `pois`: cùng dữ liệu thì cùng phiên bản, dữ liệu đổi thì phiên bản đổi. Kết quả đánh giá ghi kèm phiên bản này.

## 19. Tiền xử lý văn bản

Áp dụng giống hệt cho dữ liệu khi lập chỉ mục và cho truy vấn:

1. Chuẩn hóa Unicode NFKD, bỏ dấu thanh và dấu mũ ("Phòng" → "Phong").
2. Chữ thường, đổi `đ` → `d` (chữ đ không tách dấu được nên phải đổi riêng).
3. Mọi ký tự không phải chữ cái a–z hoặc số thành khoảng trắng; gộp khoảng trắng.
4. Tách token theo khoảng trắng.
5. Mở rộng viết tắt theo `config/aliases.json` (`vpp` → `van phong pham`…).

Ví dụ: `'Cơm-tấm "Ba Ghiền"!!'` → `com tam ba ghien`; `VPP Hồng Hà` → `van phong pham hong ha`. Tách token theo khoảng trắng là mức cơ bản: "văn phòng phẩm" là 3 token, chưa được ghép thành một từ tiếng Việt.

## 20. Chỉ mục đảo với SQLite FTS5

**Chỉ mục đảo** lưu, cho mỗi token, danh sách tài liệu chứa token đó (và vị trí, số lần xuất hiện). Tìm "ca phe" thì chỉ cần lấy giao của danh sách "ca" và danh sách "phe", không phải đọc hết mọi tài liệu.

SQLite FTS5 là module tìm kiếm toàn văn có sẵn trong SQLite, cung cấp chỉ mục đảo và hàm xếp hạng BM25. Bảng `poi_fts` có 4 cột được lập chỉ mục: tên, danh mục (nhãn tiếng Việt của danh mục), mô tả, tags; cột `poi_id` chỉ để nối với bảng `pois`. Mỗi lần import, chỉ mục được xóa và dựng lại toàn bộ trong cùng một transaction với dữ liệu, nên dữ liệu và chỉ mục không bao giờ lệch nhau.

Truy vấn được dựng thành biểu thức như `"van" "phong" "pham"`: mỗi token đã chuẩn hóa nằm trong ngoặc kép (FTS5 coi là chữ, không phải toán tử), các token cách nhau bằng khoảng trắng nghĩa là AND. Biểu thức được truyền qua tham số SQL, người dùng không thể chèn cú pháp FTS hay SQL.

## 21. BM25

BM25 chấm điểm mức độ một tài liệu khớp truy vấn:

```text
score(D, Q) = Σ_q IDF(q) × f(q, D) × (k1 + 1) / ( f(q, D) + k1 × (1 − b + b × |D| / avgdl) )
IDF(q)      = log( (N − n(q) + 0,5) / (n(q) + 0,5) )
```

- `f(q, D)`: số lần token q xuất hiện trong tài liệu D; ở FTS5, số lần trong mỗi cột được nhân với trọng số của cột.
- `|D|`, `avgdl`: độ dài tài liệu và độ dài trung bình; tài liệu dài bị phạt nhẹ.
- `N`: số tài liệu; `n(q)`: số tài liệu chứa q. Token hiếm có IDF cao, token phổ biến có IDF thấp.
- FTS5 dùng `k1 = 1,2`, `b = 0,75`. Khi IDF ≤ 0 (token xuất hiện trong hơn nửa corpus), FTS5 thay bằng 10⁻⁶.
- **Quy ước dấu**: hàm `bm25()` của FTS5 trả về giá trị **âm**, càng âm càng khớp. Vì vậy "Đúng từ khóa" sắp BM25 tăng dần.

Trọng số cột trong hệ thống: tên 2,0; danh mục, mô tả, tags 1,0 (đặt tay). Từ khóa khớp ở tên được coi quan trọng gấp đôi.

Ví dụ trong đánh giá: với "cà phê", Cafe Thềm Xưa có BM25 −5,49 còn Mía Crush −4,95. Cả hai đều khớp vì OSM gắn Mía Crush là quán cà phê, nhưng tên Thềm Xưa chứa "cafe" nên điểm cao hơn.

## 22. Xử lý không gian

Khoảng cách giữa hai tọa độ tính bằng công thức Haversine trên mặt cầu bán kính R = 6 371 008,8 m:

```text
a = sin²(Δφ/2) + cos φ1 × cos φ2 × sin²(Δλ/2)
d = 2R × arcsin(√a)
```

φ là vĩ độ, λ là kinh độ (radian). Đây là khoảng cách **đường chim bay**, khác quãng đường đi thật (xem mục 27).

Lọc bán kính giữ địa điểm có `d ≤ bán kính`. Lọc được làm trên **toàn bộ** ứng viên khớp văn bản, rồi mới xếp hạng và cắt số lượng, để không bỏ sót địa điểm gần nhưng điểm văn bản thấp. Với khoảng 100 địa điểm, tính Haversine cho từng ứng viên đủ nhanh nên chưa cần chỉ mục không gian (R-tree, PostGIS, H3).

## 23. Luồng truy vấn và xếp hạng

1. Kiểm tra tham số: query ≤ 120 ký tự; tọa độ hữu hạn, đúng miền; bán kính thuộc {300, 500, 1000, 2000}; danh mục hợp lệ; cách xếp hợp lệ; số kết quả 1–100. Sai thì trả lỗi 400.
2. Query có nội dung sau chuẩn hóa: tìm trong chỉ mục FTS5 trên toàn corpus, lấy điểm BM25. Query rỗng: lấy mọi địa điểm, không có điểm văn bản.
3. Lọc danh mục.
4. Tính khoảng cách, lọc bán kính.
5. Tính cho **mọi** ứng viên còn lại:
   - `text_norm = (−BM25) / max(−BM25)` trong lần truy vấn này (địa điểm khớp tốt nhất = 1);
   - `geo_norm = max(0, 1 − khoảng cách / bán kính)` (ngay tại gốc = 1, ở mép vòng = 0);
   - `điểm kết hợp = 0,6 × text_norm + 0,4 × geo_norm`.
6. Sắp theo cách được chọn; hòa thì xét khoảng cách, rồi ID, nên thứ tự luôn ổn định.
7. Cắt theo số lượng, trả kết quả kèm siêu dữ liệu giải thích.

Trọng số 0,6/0,4 và trọng số cột BM25 là **đặt tay**, không học từ dữ liệu. Vì vậy đây là "xếp hạng kết hợp có trọng số đặt tay", **không phải Learning to Rank**. Điểm chuẩn hóa chỉ so sánh được trong cùng một lần truy vấn.

## 24. API

| Endpoint | Chức năng |
| --- | --- |
| `GET /api/health` | Trạng thái, số địa điểm, phiên bản dữ liệu |
| `GET /api/config` | Cơ sở, danh mục, cấu hình tìm kiếm, geofence, bản đồ (không lộ địa chỉ máy chủ chỉ đường) |
| `GET /api/search?q=&lat=&lon=&origin_mode=&radius_m=&category=&sort=&limit=` | Kết quả (`items`: id, tên, danh mục, tọa độ, `distance_m`, `bm25_raw`, `text_norm`, `geo_norm`, `score`, nguồn, `rank`) và `meta` (query chuẩn hóa, biểu thức FTS5, số ứng viên từng bước, cách xếp yêu cầu/thực tế, thời gian xử lý, phiên bản dữ liệu) |
| `GET /api/pois/<id>` | Toàn bộ thông tin một địa điểm |
| `GET /api/pois` | Danh sách gọn mọi địa điểm (id, tên, danh mục, địa chỉ, tọa độ) cho ô chọn của why-not |
| Tham số chung `alpha=`, `spell=`, `match=` | `alpha` (0–1): trọng số văn bản của chế độ kết hợp; `spell=0`: tắt sửa lỗi gõ; `match=any`: nối từ bằng OR (mặc định `all` = AND). Dùng cho cả `/api/search` và `/api/whynot` |
| `GET /api/ocr-query?text=` | Dựng truy vấn từ chữ đọc trên ảnh (≤ 2000 ký tự): `query`, `kept` (từ giữ lại, DF), `dropped` (từ bỏ và lý do), `corrections` |
| `GET /api/whynot?<tham số như /api/search>&poi_id=&k=` | Why-not: `reasons` (lý do theo bước), `suggestions` (truy vấn sửa đã xác nhận, `params` để áp dụng, `rank`, `penalty`, `retained`), `original_top_k`, `indexed_text` của địa điểm |
| `GET /api/route?from_lat=&from_lon=&poi_id=` | Tuyến đi bộ (`path`, `distance_m`, `duration_s`), khoảng cách đường chim bay, liên kết Google Maps |
| `GET /api/itinerary?stop=&stop=…&lat=&lon=&origin_mode=&max_distance_m=&dwell_min=&limit=` | Lộ trình nhiều chặng (2–4 `stop`): `legs` (mỗi chặng: token, chỗ đã sửa, số ứng viên, `whynot_params`), `routes` (tối đa `limit`, mỗi lộ trình có `stops`, `total_distance_m` ước tính, `total_time_min`), `combos_considered`, `min_total_distance_m` khi không có lộ trình nào lọt ngân sách |

Mã lỗi: 400 tham số sai; 404 không có địa điểm; 422 không có tuyến; 502 máy chủ chỉ đường lỗi; 504 máy chủ chỉ đường không phản hồi kịp; 503 chưa import dữ liệu. Mỗi request mở kết nối SQLite mới nên dữ liệu vừa import có hiệu lực ngay.

## 25. Giao diện web

- HTML/CSS và JavaScript thuần chia module (`static/js/`), không cần bước build.
- Bản đồ dùng **Leaflet 1.9.4**, đặt sẵn trong `static/vendor/leaflet/` (đã kiểm mã SRI chính thức), không phụ thuộc CDN.
- **An toàn hiển thị**: mọi dữ liệu nguồn được gắn bằng `textContent`, không dùng `innerHTML`, nên tên quán chứa `<script>` chỉ hiện ra như chữ. Header **Content-Security-Policy** chỉ cho chạy script của chính ứng dụng và chỉ tải ảnh từ ứng dụng và tile OpenStreetMap.
- **Referrer-Policy** `strict-origin-when-cross-origin`: gửi địa chỉ gốc của trang khi tải tile, như chính sách tile của OpenStreetMap yêu cầu, không gửi từ khóa đang tìm.
- **Chống kết quả cũ**: gõ phím được gộp sau 0,3 giây; request cũ bị hủy (`AbortController`) và mỗi request có số thứ tự, phản hồi đến muộn của truy vấn cũ bị bỏ qua.
- **Bố cục đáp ứng**: dưới 900 px, `static/js/sheet.js` biến cột trái thành bảng trượt ba mức; chiều cao bảng được ghi vào biến CSS `--sheet-h` để chú giải, ghi nguồn bản đồ và nút định vị luôn nằm trên bảng, và bản đồ căn vòng bán kính, tuyến đường, marker vào phần còn nhìn thấy.
- **Hướng dẫn trong ứng dụng**: hộp thoại `<dialog>` gốc của trình duyệt (đóng bằng ×, Esc hoặc bấm ra ngoài), nội dung tĩnh trong `index.html`.

## 26. Định vị

Dùng Geolocation API của trình duyệt: `watchPosition` nhận vị trí liên tục (vĩ độ, kinh độ, sai số `accuracy`, thời điểm), `clearWatch` dừng khi người dùng tắt. Trình duyệt chỉ cho phép trong môi trường an toàn (HTTPS hoặc localhost) và khi người dùng đồng ý. Lượt tìm kiếm theo vị trí thật được giới hạn khoảng 1 lần/giây. Ứng dụng không lưu lịch sử vị trí.

Ba loại vị trí (tham chiếu, thật, mô phỏng) đều đi qua cùng một hàm xử lý (`handlePositionUpdate`), nên tìm kiếm, chỉ đường và geofence dùng chung một logic, chỉ khác nhãn.

## 27. Chỉ đường

- **OSRM** (Open Source Routing Machine) tìm đường ngắn nhất trên mạng đường OpenStreetMap. Ứng dụng dùng máy chủ công cộng của FOSSGIS e.V. với cấu hình **đi bộ** (`routed-foot`).
- Backend là nơi duy nhất gọi máy chủ này, tới địa chỉ cố định trong cấu hình; trình duyệt không truyền URL. Request gửi User-Agent riêng, giãn tối thiểu 1 giây/lần theo điều khoản FOSSGIS, chờ tối đa 6 giây.
- OSRM nhận tọa độ theo thứ tự **kinh độ, vĩ độ**; Leaflet dùng **vĩ độ, kinh độ**. Backend đổi thứ tự trước khi trả về.
- Không có tuyến, hết giờ chờ hay lỗi máy chủ đều trả mã lỗi riêng; giao diện không vẽ đường thẳng thay thế. Liên kết Google Maps (`api=1`, `travelmode=walking`) luôn có sẵn để mở chỉ đường ngoài ứng dụng.

## 28. Geofence

Máy trạng thái cho một địa điểm, viết thuần JavaScript (`static/js/geofence.js`), có test riêng:

```text
            mẫu đầu, d ≤ 100 m                    mẫu đầu, d > 100 m
 CHƯA RÕ ─────────────────────► TRONG VÙNG    CHƯA RÕ ─────────────────────► NGOÀI VÙNG

 NGOÀI VÙNG ── 2 mẫu liên tiếp d ≤ 100 m ──► TRONG VÙNG   (sự kiện "vào")
 TRONG VÙNG ── 2 mẫu liên tiếp d ≥ 130 m ──► NGOÀI VÙNG   (sự kiện "ra")
 100 m < d < 130 m: giữ nguyên trạng thái, xóa tiến độ xác nhận
 mẫu có sai số > 50 m: bỏ qua, xóa tiến độ xác nhận
```

Hai ngưỡng khác nhau (vùng trễ) tránh báo liên tục khi đứng quanh mép vùng. Cần 2 mẫu liên tiếp để một mẫu nhiễu không gây sự kiện giả. Cooldown 30 giây chỉ chặn thông báo nổi, sự kiện vẫn được ghi nhật ký. Các ngưỡng này là lựa chọn cho demo, đặt trong `config/app.json`, chưa được kiểm ngoài thực địa.

## 29. Chỉ số đánh giá và kết quả

### Công thức

- **Precision@5** = số địa điểm liên quan trong 5 kết quả đầu / 5. Trả về ít hơn 5 kết quả thì vị trí trống tính là không liên quan.
- **Recall@5** = số địa điểm liên quan trong 5 kết quả đầu / tổng số địa điểm liên quan trong nhãn của **cả phạm vi** truy vấn (kể cả địa điểm mà tìm kiếm không lấy ra). Truy vấn không có địa điểm liên quan: N/A, loại khỏi trung bình.
- **nDCG@5** = DCG@5 / IDCG@5, với `DCG@5 = Σ (2^rel_i − 1) / log2(i + 1)`, i = 1..5; IDCG là DCG của thứ tự lý tưởng. Đo xem địa điểm liên quan có nằm ở đầu danh sách không.

Ba chế độ dùng cùng tập ứng viên nên chênh lệch giữa chúng chỉ do thứ tự.

### Kết quả (dataset `ds-7ac47a589e`, 12 truy vấn, 232 nhãn, người duyệt: Tran Dat, 18/09/2026)

| Chế độ | P@5 | R@5 | nDCG@5 |
| --- | ---: | ---: | ---: |
| A: BM25 | 0,5833 | 0,8654 | 1,0000 |
| B: khoảng cách | 0,5167 | 0,8048 | 0,8806 |
| C: kết hợp | 0,5667 | 0,8553 | 0,9838 |

### Đọc kết quả

- **P@5 thấp không có nghĩa là tìm kiếm kém.** Nhiều truy vấn có ít hơn 5 địa điểm liên quan (Demon Kitchen chỉ có 1, Circle K có 2), nên P@5 tối đa của chúng là 0,2–0,4. Tính theo nhãn, P@5 trung bình **cao nhất có thể đạt là 0,5833** và R@5 cao nhất có thể đạt là **0,8654** (Recall@5 bị giới hạn khi một truy vấn có hơn 5 địa điểm liên quan, như 20 trạm xe buýt). Chế độ BM25 đạt đúng hai mức trần này trên bộ truy vấn này.
- **Tìm kiếm không bỏ sót địa điểm liên quan nào** ở cả 12 truy vấn. Truy vấn không có đáp án ("sửa xe máy") trả về rỗng, không có kết quả sai.
- **Chênh lệch chỉ đến từ 4 truy vấn**; 8 truy vấn còn lại cho kết quả như nhau ở cả ba chế độ vì mọi kết quả đều liên quan hoặc có ≤ 5 kết quả:
  - *"van phong pham"*: nhãn danh mục "Văn phòng phẩm / photocopy" nằm trong chỉ mục, nên mọi tiệm photocopy cũng khớp. BM25 đẩy 3 cửa hàng văn phòng phẩm thật lên đầu (P@5 0,6, nDCG 1,0); xếp theo khoảng cách để tiệm photocopy gần hơn đứng trước (P@5 0,4, nDCG 0,42).
  - *"cà phê"*: OSM gắn cả quán trà sữa, quán nước mía và căng tin là "quán cà phê", nên chúng cũng khớp. BM25 đưa các quán có "cà phê/cafe/coffee" trong tên lên đầu (P@5 1,0); xếp theo khoảng cách để MayCha, Canteen SGU, Mía Crush gần trường đứng trước (P@5 0,4); kết hợp ở giữa (P@5 0,8).
  - *"photocopy"*, *"trà sữa"*: chỉ khác vị trí của một kết quả không liên quan (nDCG 0,92–0,97 ở chế độ khoảng cách).
- **Kết luận có giới hạn**: trên corpus nhỏ này, BM25 xếp tốt nhất khi từ khóa mô tả loại địa điểm mà dữ liệu gắn nhãn rộng; khi mọi kết quả đều dùng được như nhau (cây xăng, trạm xe buýt, pizza) thì ba chế độ ngang nhau và "Gần nhất" là lựa chọn tự nhiên. Chế độ kết hợp đổi một phần độ chính xác văn bản lấy độ gần.

### Giới hạn của đánh giá

- 12 truy vấn, không có ý nghĩa thống kê; không kết luận chế độ nào vượt trội nói chung.
- Nhãn và chỉ mục cùng dựa trên tên và thẻ OSM, nên kết quả có phần lạc quan. Quy ước gán nhãn chặt (chỉ gán 1 khi có bằng chứng) cũng làm các truy vấn như "com" dễ đạt điểm cao: nhà hàng có thể bán cơm nhưng không có bằng chứng thì được gán 0.
- Nhãn do Claude soạn nháp và một người duyệt.
- Trọng số giữ nguyên như trước khi đánh giá; không chỉnh theo kết quả này. Hướng cải thiện (chưa làm): tách nhãn danh mục ghép "văn phòng phẩm / photocopy", tách quán trà sữa khỏi quán cà phê trong dữ liệu, sửa thẻ cũ "Coffee Urban Station" của Mía Crush. Làm các việc này thì phải đánh giá lại với bộ truy vấn mới.

## 29A. Why-not: mô hình và thuật toán

**Bài toán** (He & Lo, ICDE 2012; Chen, Lin, Hu, Jensen, Xu, ICDE 2015):

- Cho truy vấn không gian–từ khóa top-k `Q = (từ khóa, vị trí, bán kính, danh mục, cách xếp, α, k)` và một địa điểm `m` người dùng mong đợi nhưng không có trong top-k.
- Hệ thống giải thích vì sao `m` vắng mặt.
- Hệ thống tìm truy vấn sửa `Q'` gần `Q` nhất sao cho `m` nằm trong top-k' của `Q'`.

**Chẩn đoán** đi theo đúng các bước của `src/search.py` (`retrieve → score_items → rank_items`):

1. Từng từ của truy vấn được kiểm riêng trên chỉ mục FTS5 của `m`.
2. Kiểm danh mục.
3. Kiểm khoảng cách Haversine so với bán kính.
4. Nếu qua cả ba bước lọc: tìm hạng thật của `m` trên toàn bộ ứng viên (không cắt `limit`) và so các thành phần điểm với kết quả hạng k.

**Không gian sửa truy vấn** (vét cạn, vì corpus nhỏ):

- **Từ khóa**: bỏ tập con các từ; thêm 1 trong 2 từ hiếm nhất (DF nhỏ nhất, tương đương IDF lớn nhất) có trong **tên** của `m`. Chỉ lấy từ trong tên vì tag nguồn thường là tiếng Anh (ví dụ "brunch"), người dùng khó hiểu vì sao lại được gợi ý; hoặc thay các từ `m` thiếu bằng từ đó (keyword adaption, Chen et al., ICDE 2016).
- **Bán kính**: các mức lớn hơn bán kính hiện tại.
- **Danh mục**: bỏ lọc.
- **Cách xếp**: 3 chế độ.
- **Trọng số α**: xem đoạn "Tính α" bên dưới.
- **Giới hạn**: tối đa 2 thay đổi (không tính k). Khi `m` bị nhiều bộ lọc chặn cùng lúc, giới hạn nới bằng số bộ lọc chặn.
- **k**: mỗi `Q'` tự nhận `k' = max(k, hạng của m trong Q')`.

**Tính α**: điểm kết hợp `α·t + (1 − α)·g` tuyến tính theo α.

- Hạng của `m` chỉ đổi khi đường thẳng của `m` cắt đường của một địa điểm khác, tại `α = −(g_i − g_m) / [(t_i − g_i) − (t_m − g_m)]`.
- Thuật toán quét các giao điểm ra hai phía của α hiện tại. Mỗi khi số địa điểm đứng trên `m` giảm xuống mức thấp mới, lấy một α ngay bên trong khoảng kế tiếp (làm tròn 3 chữ số nếu vẫn nằm trong khoảng).
- Kết quả là các α **chính xác**, không phải dò lưới.

**Penalty** (He & Lo; Chen et al.):

```text
penalty = λ·Δk + (1 − λ)·Δq,   λ = 0,5
Δk = (k' − k) / (r_m − k)        r_m: hạng của m trong Q (không có trong ứng viên thì dùng số địa điểm − k); chỉ tăng k thì Δk = 1
Δq = min(1, tổng chi phí thay đổi)
     bỏ từ: số từ bỏ / số từ; thêm từ: 1 / (số từ + 1); bán kính: số bậc tăng / 3;
     bỏ danh mục: 0,5; đổi cách xếp: 0,5; α: |α' − α| / max(α, 1 − α)
```

Chi phí và λ **đặt tay** trong `config/app.json` (khối `whynot`), chưa tối ưu.

**Chọn và hiển thị đề xuất**:

- Sắp các phương án theo penalty; hòa thì ưu tiên giữ nhiều kết quả cũ hơn, rồi ít thay đổi hơn.
- Mỗi loại (họ) thay đổi lấy phương án tốt nhất, hiện tối đa 5 đề xuất.
- **Xác nhận**: từng đề xuất được chạy lại bằng `search()` của API. Chỉ hiện đề xuất có `m` đúng hạng đã tính. Số đề xuất bị loại vì không khớp (`unverified_dropped`) phải bằng 0 và có test kiểm tra.

**Thời gian**: mỗi tổ hợp (từ khóa, bán kính, danh mục) truy xuất một lần; đổi cách xếp và α chỉ sắp lại trong bộ nhớ. Trên corpus ~100 địa điểm, một câu hỏi xét vài trăm phương án. Thời gian thực đo bằng `scripts.eval_whynot` (cột `elapsed_ms`).

**Khác với tìm "điểm hẹn" nhiều người**: bài toán điểm hẹn tối ưu vị trí cho nhiều điểm xuất phát (group nearest neighbor). Why-not giữ một người dùng, một vị trí, và giải thích, sửa **truy vấn và hàm xếp hạng**. Đây là bài toán của truy xuất thông tin có giải thích (explainable IR).

## 29B. Sửa lỗi gõ: thuật toán

Code: `src/spell.py`. Sửa lỗi gõ chạy sau bước chuẩn hóa và mở rộng viết tắt, trước khi tạo biểu thức FTS5. Tìm kiếm và why-not dùng chung bước này qua `query_tokens()`.

0. Câu từ giọng nói (mục 10C) đi qua đúng các bước này, không có xử lý riêng.
1. **Từ vựng** lấy thẳng từ chỉ mục qua bảng ảo `fts5vocab` của SQLite (từ và số tài liệu chứa từ), cache theo `dataset_version`. Dữ liệu đổi thì từ vựng đổi theo.
2. Chỉ xét token **không có** trong từ vựng. Token không sửa:
   - token dưới 4 ký tự;
   - số;
   - **âm tiết tiếng Việt hợp lệ**, kiểm bằng biểu thức chính quy phụ âm đầu + vần + phụ âm cuối. Nhờ vậy "sáng", "siêu thị" không bị đổi thành từ khác chỉ vì dữ liệu không có.
3. **Gộp** 2–4 token liền nhau có ít nhất một token lạ:
   - Phần ghép trùng đúng một từ hoặc viết tắt thì gộp ("piz za" → "pizza", "phô tô" → "photo" → "photocopy").
   - Với 3–4 token và phần ghép dài ≥ 6 ký tự, cho phép gần đúng. Bước này dành cho câu nhận từ giọng nói, vì bộ nhận dạng hay tách từ mượn thành âm tiết ("phô tô cóp pi" → "photocopy").
4. **Tách** token dính thành ít phần nhất, mỗi phần có trong từ vựng ("vanphongpham" → "van phong pham"), bằng quy hoạch động kiểu word break.
5. **Sửa chữ**: chọn từ gần nhất theo khoảng cách Damerau–Levenshtein dạng OSA (thêm, bớt, thay, đảo hai chữ liền nhau).
   - Tối đa 1 lỗi cho từ 4 ký tự, 2 lỗi từ 5 ký tự trở lên.
   - Hòa thì chọn từ xuất hiện trong nhiều tài liệu hơn.
   - Danh sách viết tắt cũng là ứng viên ("cofee" → "coffee" → "cà phê").
6. API trả `meta.corrections` (chỗ sửa, loại sửa) và `meta.query_as_typed`. Tham số `spell=0` tắt việc sửa.

Chỉ số R5 không đổi vì mọi từ trong 12 truy vấn đều có trong từ vựng hoặc ngắn hơn 4 ký tự. Cách kiểm: chạy lại `scripts.evaluate`, `eval/metrics.csv` phải giữ nguyên.

## 29C. Tìm bằng ảnh: truy vấn dài và nhiễu

**Nhận dạng chữ (OCR)** chạy trong trình duyệt bằng Tesseract.js 5.1.1:

- Worker `worker.min.js` và lõi WebAssembly chỉ LSTM; có bản SIMD và bản thường, bộ nạp tự chọn theo máy.
- Dữ liệu `vie` và `eng` loại best_int. Tiếng Anh cần cho tên thương hiệu như Circle K, Coffee.
- Ảnh được thu nhỏ còn cạnh dài 1600 px và xoay theo EXIF trước khi đọc.
- Toàn bộ file đặt trong `static/vendor/tesseract/` và nạp khi người dùng chọn ảnh lần đầu. Không dùng CDN, nên vẫn giữ CSP `script-src 'self'`. CSP chỉ thêm `'wasm-unsafe-eval'` (cho phép biên dịch WebAssembly, **không** mở `eval` cho JavaScript) và `blob:` cho ảnh xem trước.

**Dựng truy vấn** (`src/ocr_query.py`, API `GET /api/ocr-query?text=`). Chữ trên biển hiệu là một **truy vấn dài và nhiễu**: tên quán lẫn số điện thoại, địa chỉ, khẩu hiệu và lỗi nhận dạng. Đây là bài toán *query-by-document* hay *verbose query reduction* trong IR:

1. Chuẩn hóa như truy vấn thường.
2. Với token lẫn chữ và số, thử đổi các ký tự hay nhầm (0→o, 1→i, 5→s…). Chỉ nhận khi kết quả có trong từ vựng.
3. Sửa lỗi gõ (mục 29B).
4. Bỏ token là số, token không có trong từ vựng (không thể khớp), và token có trong hơn 50% địa điểm. FTS5 cũng kẹp IDF của các từ đó về gần 0.
5. Giữ tối đa 10 token hiếm nhất (DF nhỏ, IDF lớn), theo thứ tự xuất hiện.

**Truy xuất**: tham số mới `match=any` nối các token bằng `OR` trong FTS5. BM25 tự ưu tiên địa điểm khớp **nhiều** từ và từ **hiếm**, nên tên quán thắng khẩu hiệu chung chung. Nối AND như truy vấn gõ tay thì một từ nhiễu là đủ làm kết quả rỗng; mục 15D đo đúng sự khác biệt này (cách A với cách C).

Why-not vẫn dùng được khi đang tìm theo ảnh: với kiểu OR, địa điểm chỉ bị loại ở bước khớp từ khóa khi thiếu **mọi** từ.

## 29D. Lộ trình nhiều chặng: mô hình

**Bài toán**: cho một chuỗi chặng có thứ tự `(q1, q2, …, qN)` và một điểm gốc, chọn một địa điểm cho mỗi chặng sao cho tổng quãng đường di chuyển (gốc → chặng 1 → … → chặng N) nằm trong một ngân sách, ưu tiên độ khớp từ khóa và độ ngắn. Đây là **tối ưu không gian theo chuỗi** (sequenced route planning trên một người dùng), khác họ với truy vấn **nhiều người, một điểm gặp** (group nearest neighbor) — nhóm khác trong lớp làm hướng đó; hai bài không trùng nhau về mô hình lẫn cách giải.

**Phần IR**: mỗi chặng là một truy vấn từ khóa độc lập, lấy ứng viên bằng đúng `src.search.retrieve` (chỉ mục đảo FTS5 + BM25) và `src.search.query_tokens` (sửa lỗi gõ, mục 29B) — không có pipeline riêng cho từng chặng.

**Không gian tìm kiếm** (`src/itinerary.py`, vét cạn vì corpus nhỏ):

1. Mỗi chặng lấy toàn bộ ứng viên khớp AND trong `itinerary.search_radius_m` (2 km, quanh điểm gốc), sắp theo BM25 rồi khoảng cách, giữ top `max_candidates_per_leg` (8).
2. Vét cạn tích Descartes giữa các chặng (tối đa 8^N tổ hợp, N ≤ 4); bỏ tổ hợp dùng lại cùng một địa điểm ở hai chặng.
3. Với mỗi tổ hợp còn lại: quãng đường mỗi đoạn = Haversine × `detour_factor` (1,3 — hệ số quy đổi đường chim bay sang đường phố, **đặt tay**, chưa đo trên OSRM thật); tổng vượt `max_distance_m` thì loại, còn không thì tính điểm.
4. Điểm = `weights.text × text_norm trung bình các chặng + weights.geo × max(0, 1 − tổng quãng đường / max_distance_m)` (0,5/0,5, đặt tay, cùng dạng với điểm kết hợp của tìm kiếm thường). Giữ top `max_results` (3), mỗi tổ hợp cắt cùng thứ tự chặng nên không cần xử lý riêng thứ tự điểm dừng (bài toán không phải TSP: thứ tự đã cố định theo yêu cầu người dùng).
5. Khi không có tổ hợp nào lọt ngân sách nhưng vẫn có tổ hợp hợp lệ (không trùng địa điểm), API trả `min_total_distance_m` — quãng đường ngắn nhất tìm được — để gợi ý nới ngân sách; không cố "sửa truy vấn" như why-not vì đây là bài toán chọn tổ hợp, không phải xếp hạng lại một tập ứng viên cố định.

**Ngân sách thời gian**: `walking_speed_mps` (1,24 m/s) lấy từ tốc độ đo được trên một tuyến OSRM thật khi chọn nhà cung cấp chỉ đường (D-05), **không đo lại riêng cho tính năng này**. Thời gian ở mỗi chặng (`dwell_min`, mặc định 45 phút, người dùng tự đổi) là giả định — hệ thống không có giờ chiếu phim, giờ mở cửa hay tình trạng còn chỗ để tính đúng.

**Chỉ đường thật**: không thêm lệnh gọi máy chủ ngoài. Khi người dùng bấm **Chỉ đường thật**, giao diện gọi lại đúng `GET /api/route` (đã có, dùng cho một địa điểm) tuần tự cho từng chặng; backend vẫn giãn ≥ 1 giây/lần như mọi lệnh gọi OSRM khác (D-06, D-23).

**Tái dùng why-not**: mỗi chặng có `radius_m` nằm trong `search.allowed_radii_m`, nên nút "Vì sao thiếu chỗ khác ở chặng này?" gọi thẳng `/api/whynot` với `q`/`radius_m` của chặng, không cần đường dẫn riêng.

## 30. Kiểm thử

| Nhóm | Công cụ | Nội dung |
| --- | --- | --- |
| Python (136 test) | `pytest` | Chuẩn hóa có/không dấu, đ, viết tắt; Haversine; cấu hình; schema và BM25; import (lặp, sửa, lỗi thì không ghi, cột lạ, `--replace`); dựng corpus; áp bảng duyệt; tìm kiếm (3 chế độ cùng tập ứng viên, biên bán kính, ký tự lạ, hòa điểm); API (400/404/503, dữ liệu mới thấy ngay, header bảo mật); chỉ đường (giả lập máy chủ, 8 tình huống lỗi); chỉ số đánh giá; xuất ZIP |
| JavaScript (9 test) | `node --test` | Geofence: khởi tạo, xác nhận 2 mẫu, vùng trễ, cooldown, mẫu sai số lớn, đặt lại |
| Thủ công | `MANUAL_CHECKS.md` | Giao diện, định vị thật, chỉ đường thật, geofence, mất mạng, điện thoại |

Test dùng dữ liệu tổng hợp trong `tests/fixtures/`, không trộn vào corpus.

## 31. Bảng công nghệ

| Thành phần | Công nghệ (phiên bản đã thử) | Vai trò | Lý do chọn |
| --- | --- | --- | --- |
| Ngôn ngữ backend | Python 3.13.13 | Toàn bộ xử lý dữ liệu, tìm kiếm, API | Phổ biến trong môn học, thư viện chuẩn có SQLite |
| Web server | Flask 3.1.3 (Werkzeug 3.1.8) | Phục vụ giao diện và API trong một tiến trình | Nhẹ, không cần cấu hình CORS |
| Lưu trữ + chỉ mục | SQLite 3.50.4, module FTS5 | Bảng dữ liệu, chỉ mục đảo, hàm BM25 | Có sẵn trong Python, BM25 thật, không cần máy chủ riêng |
| Không gian | Haversine tự viết | Khoảng cách, lọc bán kính | Đủ cho ~100 địa điểm |
| Nguồn dữ liệu | OpenStreetMap qua Overpass API; tin đăng phongtro123 | Địa điểm và vị trí cơ sở | Dữ liệu mở, có giấy phép ODbL, kiểm chứng được |
| Bản đồ | Leaflet 1.9.4 + tile OpenStreetMap | Marker, vòng tròn, tuyến đường | Mã nguồn mở, không cần API key |
| Chỉ đường | OSRM của FOSSGIS (`routed-foot`); Google Maps URL dự phòng | Tuyến đi bộ | Miễn phí, không cần API key |
| Định vị | Geolocation API của trình duyệt | Vị trí thật | Có sẵn trong trình duyệt |
| Geofence | Máy trạng thái JavaScript | Vào/ra vùng khi trang mở | Chạy phía trình duyệt, test độc lập được |
| HTTP client | requests 2.34.2 | Gọi Overpass, máy chủ chỉ đường | Phổ biến, dễ giả lập trong test |
| Kiểm thử | pytest 9.1.1; Node.js 22 `node:test` | Test tự động | Không cần thư viện test JS bên ngoài |

## 32. Đã cài, chỉ là lý thuyết, hướng phát triển

| Thành phần trong sơ đồ kiến trúc LBS của môn | Trong GeoRank |
| --- | --- |
| Tiền xử lý, chỉ mục đảo, BM25 | **Đã cài** (SQLite FTS5) |
| Elasticsearch / OpenSearch | Thay bằng SQLite FTS5; chưa cài |
| PostGIS, R-tree, H3, chỉ mục không gian | Thay bằng Haversine trên tập nhỏ; chưa cài |
| Xếp hạng kết hợp văn bản–khoảng cách | **Đã cài**, trọng số đặt tay |
| Learning to Rank, Feature Store | Chưa cài: không có dữ liệu huấn luyện |
| Mô hình neural, vector, ANN | Chưa cài |
| Redis, Kafka/Flink, xử lý luồng | Chưa cài |
| SDK bản đồ, marker, danh sách theo khoảng cách | **Đã cài** (Leaflet) |
| Chỉ đường | **Đã cài** (OSRM qua FOSSGIS, đi bộ) |
| Geofence và thông báo | **Đã cài**, chỉ khi trang mở; chưa có thông báo nền |
| Đánh giá IR | **Đã cài**: P@5, R@5, nDCG@5, 12 truy vấn |
| Giải thích kết quả vắng mặt (why-not) và sửa truy vấn | **Đã cài** (phần mới cuối kỳ): chẩn đoán theo bước, đề xuất truy vấn sửa có penalty, đánh giá riêng |
| Lập lộ trình nhiều chặng có ràng buộc quãng đường | **Đã cài** (phần mới cuối kỳ, "bản nhẹ"): vét cạn tổ hợp, ước tính bằng Haversine × hệ số quanh co; **chưa** xử lý giờ chiếu/giờ mở cửa, tối ưu tổ hợp lớn (TSP) |

## 33. Thuật ngữ

| Thuật ngữ | Nghĩa |
| --- | --- |
| POI | Point of Interest, địa điểm quan tâm (quán ăn, cửa hàng, trạm xe…) |
| Corpus | Tập tài liệu được tìm kiếm; ở đây là tập địa điểm |
| Token | Đơn vị từ sau khi tách, ví dụ "ca", "phe" |
| Chỉ mục đảo | Bảng từ token → danh sách tài liệu chứa token |
| BM25 | Hàm chấm điểm văn bản dựa trên tần suất từ, độ hiếm của từ và độ dài tài liệu |
| IDF | Inverse Document Frequency, độ hiếm của một token trong corpus |
| Haversine | Công thức khoảng cách trên mặt cầu |
| Qrels | Nhãn liên quan (query, địa điểm, 0/1) dùng để đánh giá |
| P@5, R@5, nDCG@5 | Precision, Recall và Normalized Discounted Cumulative Gain tính trên 5 kết quả đầu |
| OSM, Overpass | OpenStreetMap (bản đồ mở) và API truy vấn dữ liệu OSM |
| OSRM | Open Source Routing Machine, máy tìm đường |
| Geofence | Vùng địa lý ảo; hệ thống báo khi thiết bị vào/ra vùng |
| Vùng trễ | Hai ngưỡng vào/ra khác nhau để tránh báo liên tục ở mép vùng |
| Mô phỏng | Vị trí giả lập có nhãn, dùng để trình diễn |
| dataset_version | Mã phiên bản dữ liệu tính từ nội dung, gắn vào kết quả tìm kiếm và đánh giá |
