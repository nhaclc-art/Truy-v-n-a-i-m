# Giới hạn đã biết

## Dữ liệu

- Corpus nhỏ (93 địa điểm) chọn theo luật cố định từ snapshot OpenStreetMap ngày 18/09/2026, không phải toàn bộ địa điểm trong 2 km. OSM có thể thiếu, cũ hoặc sai: một nhà hàng từng bị đặt sai vị trí khoảng 500 m và đã được sửa bằng nguồn khác.
- Chỉ 16 địa điểm đã đối chiếu với nguồn thứ hai (Foody, bài đăng của quán, người dùng tra Google Maps); còn lại là `source_only`. Chưa có địa điểm nào được khảo sát tại chỗ. Tên của 6 địa điểm OSM không có tên do người dùng tra Google Maps bổ sung.
- Một số tọa độ là gần đúng: tâm hình học của building/way thay vì lối vào; nhà trọ theo tâm hẻm; Cơm Tấm 419 theo địa chỉ nhà bên cạnh.
- Nhà trọ chỉ có 2 tin đăng; tin còn hiển thị không chứng minh còn phòng, tin hết hạn không chứng minh đã ngừng cho thuê. Giá, giờ mở cửa, đánh giá không dùng để xếp hạng.
- Trạm xe buýt lấy từ OSM, chưa đối chiếu với dữ liệu chính thức của thành phố; tuyến chỉ có khi OSM ghi `route_ref`.

## Tìm kiếm

- Chỉ tìm theo từ khóa, danh mục và vị trí. Không hiểu câu tự nhiên như "quán rẻ đang mở gần trường".
- Tách từ theo khoảng trắng, chưa tách từ tiếng Việt; các token nối AND nên thiếu một từ là không khớp. Alias chỉ có 5 mục.
- FTS5 kẹp IDF về gần 0 cho từ xuất hiện trong hơn nửa corpus.
- Trọng số BM25 theo cột và trọng số chế độ kết hợp đặt tay, chưa tối ưu; điểm chuẩn hóa chỉ so sánh được trong cùng một lần truy vấn.
- `elapsed_ms` chỉ đo xử lý phía server, không phải độ trễ toàn hệ thống.

## Đánh giá

- 12 truy vấn, nhãn nhị phân, một người duyệt; nhãn do Claude soạn nháp. Kết quả chỉ mang tính thăm dò, không có ý nghĩa thống kê và không chứng minh chế độ nào vượt trội chung.
- Với truy vấn có hơn 5 địa điểm liên quan, Recall@5 không thể đạt 1.

## Why-not (vì sao không có?)

- Không gian sửa truy vấn giới hạn: tối đa 2 thay đổi (nới khi nhiều bộ lọc cùng chặn), chỉ thêm 1 trong 2 từ hiếm nhất của địa điểm, bán kính chỉ theo các mức 300/500/1000/2000 m. Vét cạn chỉ phù hợp corpus nhỏ; corpus lớn cần kỹ thuật cắt tỉa như trong Chen et al. (ICDE 2015).
- λ và chi phí từng loại thay đổi đặt tay; "ít thay đổi nhất" là theo hàm penalty này, không phải theo cảm nhận của mọi người dùng.
- Đề xuất "thêm từ" có thể thu hẹp kết quả rất mạnh (giữ ít kết quả cũ); ứng dụng hiện tỷ lệ giữ kết quả cũ để người dùng tự cân nhắc.
- Chẩn đoán dựa trên văn bản đã lập chỉ mục; nếu dữ liệu nguồn thiếu (ví dụ chỉ có tag tiếng Anh "breakfast"), why-not chỉ ra chỗ thiếu chứ không tự sửa dữ liệu.
- Đánh giá why-not: bộ câu hỏi nhỏ, câu soạn tay do Claude nháp và một người duyệt; khảo sát người dùng là thăm dò.

## Sửa lỗi gõ

- Từ điển là từ vựng của chính corpus nhỏ (vài trăm từ). Từ đúng nhưng không có trong dữ liệu không được sửa, và cũng không tự tìm được.
- Không sửa từ dưới 4 ký tự và âm tiết tiếng Việt hợp lệ, nên lỗi như "caf" (cà) hoặc gõ nhầm sang một âm tiết khác có nghĩa vẫn không được sửa.
- Chọn từ sửa theo khoảng cách chữ và số tài liệu chứa từ, không hiểu ngữ cảnh câu; có thể sửa sai khi hai từ gần nhau cùng có trong dữ liệu. Giao diện luôn báo chỗ đã sửa và cho tìm đúng như đã gõ.
- Biến thể gõ sai để đánh giá do Claude soạn, không lấy từ nhật ký truy vấn thật.

## Giọng nói

- Nhận dạng do dịch vụ của trình duyệt đảm nhiệm (Google với Chrome/Edge, Apple với Safari). Âm thanh rời thiết bị, cần Internet, và chất lượng không do hệ thống kiểm soát. Firefox không hỗ trợ.
- Chỉ chạy qua HTTPS hoặc localhost; trên điện thoại cần cáp USB (Android) hoặc đường hầm HTTPS tạm.
- Từ mượn tiếng Anh (Circle K, GS25) hay bị nghe thành âm tiết tiếng Việt; bước gộp chỉ cứu được khi phần ghép gần một từ trong dữ liệu.
- Đánh giá giọng nói là thăm dò: ít người nói, môi trường ghi không kiểm soát.

## Tìm bằng ảnh biển hiệu

- Tesseract đọc tốt chữ in rõ, thẳng; kém với chữ cách điệu, chữ nghiêng, biển LED, ảnh tối hoặc chụp xa. Chưa tìm vùng chữ hay nắn phối cảnh trước khi đọc.
- Lần đầu phải nạp khoảng 5–8 MB (lõi + dữ liệu ngôn ngữ); máy yếu có thể mất vài giây mỗi ảnh.
- Tìm kiểu OR gần như luôn trả về một địa điểm nào đó, kể cả khi quán không có trong dữ liệu; giao diện ghi "Có thể là" và cho xem chữ đọc được để người dùng tự kiểm.
- Bộ đọc chữ không commit; bản clone mới phải chạy `scripts.vendor_tesseract` (cần mạng một lần). SHA-256 khóa theo lần tải đầu (trust on first use).

## Lộ trình nhiều chặng

- **Không xử lý giờ chiếu phim, giờ mở cửa hay tình trạng còn phòng/còn chỗ.** Corpus cũng không có danh mục rạp phim. "Ngân sách thời gian" chỉ là đi bộ ước tính cộng thời gian ở mỗi chặng do người dùng tự nhập (giả định).
- Quãng đường giữa các chặng là Haversine × hệ số quanh co 1,3 (đặt tay, chưa đo trên OSRM thật cho nhiều tuyến); có thể lệch khá xa quãng đường phố thật, đặc biệt qua khu vực có vật cản (trường học, sông, đường một chiều).
- Mỗi chặng chỉ xét tối đa 8 ứng viên khớp từ khóa tốt nhất; địa điểm đúng nhưng xếp ngoài top 8 của chặng đó sẽ không xuất hiện trong bất kỳ lộ trình nào (dùng "Vì sao thiếu chỗ khác ở chặng này?" để kiểm).
- Không đánh giá được bằng P@5/Recall@5/nDCG@5 như R5 (không có "địa điểm liên quan" cho bài toán chọn tổ hợp theo chuỗi); chỉ có kiểm tra thăm dò trên dữ liệu thật (`scripts.check_itinerary`), không phải đánh giá IR có ý nghĩa thống kê.
- Trọng số xếp hạng lộ trình (0,5 văn bản / 0,5 khoảng cách) và mọi hằng số khác đều đặt tay, chưa tối ưu.

## Định vị, chỉ đường, geofence

- Định vị trên máy tính thường theo Wi-Fi/IP, sai số lớn. Định vị trên điện thoại qua địa chỉ IP LAN (HTTP) có thể bị trình duyệt chặn; demo dùng localhost hoặc chế độ mô phỏng có nhãn.
- Chỉ đường phụ thuộc máy chủ OSRM công cộng của FOSSGIS, không có cam kết sẵn sàng; chỉ có tuyến đi bộ, không có xe máy.
- Geofence chỉ chạy khi trang đang mở và nhận được mẫu vị trí; không có thông báo nền. Ngưỡng 100/130 m, 2 mẫu, 30 giây là lựa chọn demo, chưa kiểm ngoài thực địa.

## Hạ tầng

- Nền bản đồ cần Internet; không có bản đồ offline. Chạy bằng Flask development server trên localhost, không phải cấu hình triển khai production.
- Không dùng Elasticsearch/OpenSearch, PostGIS, H3, Redis, Kafka/Flink, Learning to Rank hay mô hình neural; các thành phần này chỉ thuộc phần lý thuyết/hướng phát triển.
