# Các ca why-not dùng cho khảo sát

Người tham gia đọc từng ca (hoặc xem trình diễn trên ứng dụng) rồi chấm vào `eval/whynot_survey.csv`:
`hieu_ly_do_1_5` (1 = không hiểu vì sao địa điểm vắng mặt, 5 = hiểu rõ) và `de_xuat_huu_ich_1_5`
(1 = đề xuất vô ích, 5 = sẽ dùng ngay). Không ghi thông tin cá nhân ngoài tên/biệt danh người trả lời.

## W01

- Truy vấn: “chỗ in tài liệu”, bán kính 1000 m, danh mục vpp_photocopy, xếp hạng combined.
- Địa điểm mong đợi: **Tiệm Photocopy Ngọc Lan** (Văn phòng phẩm / photocopy).
- Hệ thống giải thích:
  - Văn bản được lập chỉ mục của địa điểm không có từ “chỗ”, “tài”, “liệu”. Các từ trong truy vấn nối bằng AND nên thiếu một từ là bị loại ngay ở bước khớp văn bản (FTS5).
- Đề xuất sửa truy vấn:
  1. Bỏ từ “chỗ”, “tài”, “liệu” → hạng 3 trong top 5
  2. Bỏ từ “chỗ”, “tài”, “liệu” + Thêm từ “Lan” (có trong tên) → hạng 1 trong top 5
  3. Bỏ từ “chỗ”, “tài”, “liệu” + Ưu tiên khoảng cách hơn (trọng số từ khóa 0.6 → 0.457) → hạng 2 trong top 5

## W04

- Truy vấn: “circle k”, bán kính 300 m, danh mục an_uong, xếp hạng distance.
- Địa điểm mong đợi: **Circle K** (Cửa hàng tiện lợi).
- Hệ thống giải thích:
  - Địa điểm thuộc danh mục “Cửa hàng tiện lợi”, còn bạn đang lọc “Ăn uống”.
- Đề xuất sửa truy vấn:
  1. Bỏ lọc “Ăn uống” → hạng 1 trong top 5
  2. Nới bán kính lên 500 m + Bỏ lọc “Ăn uống” → hạng 1 trong top 5
  3. Bỏ lọc “Ăn uống” + Xếp theo “Đúng từ khóa” → hạng 1 trong top 5

## W06

- Truy vấn: “pizza”, bán kính 300 m, danh mục an_uong, xếp hạng distance.
- Địa điểm mong đợi: **Pizza Hut** (Ăn uống).
- Hệ thống giải thích:
  - Địa điểm cách vị trí gốc 317 m (đường chim bay), ngoài bán kính 300 m.
- Đề xuất sửa truy vấn:
  1. Nới bán kính lên 500 m → hạng 1 trong top 5
  2. Nới bán kính lên 500 m + Xếp theo “Đúng từ khóa” → hạng 1 trong top 5
  3. Nới bán kính lên 500 m + Bỏ lọc “Ăn uống” → hạng 1 trong top 5

## W09

- Truy vấn: “cà phê”, bán kính 500 m, danh mục an_uong, xếp hạng distance.
- Địa điểm mong đợi: **Cafe Thềm Xưa** (Ăn uống).
- Hệ thống giải thích:
  - Địa điểm có khớp nhưng đứng hạng 12/13 theo chế độ Gần nhất: cách 437 m, trong khi hạng 5 (Mía Crush) chỉ cách 275 m.
- Đề xuất sửa truy vấn:
  1. Thêm từ “Thềm” (có trong tên) → hạng 1 trong top 5
  2. Xếp theo “Đúng từ khóa” → hạng 1 trong top 5
  3. Thêm từ “Thềm” (có trong tên) + Nới bán kính lên 1 km → hạng 1 trong top 5

## W13

- Truy vấn: “ăn sáng”, bán kính 500 m, danh mục an_uong, xếp hạng combined.
- Địa điểm mong đợi: **Canteen SGU** (Ăn uống).
- Hệ thống giải thích:
  - Văn bản được lập chỉ mục của địa điểm không có từ “sáng”. Các từ trong truy vấn nối bằng AND nên thiếu một từ là bị loại ngay ở bước khớp văn bản (FTS5).
- Đề xuất sửa truy vấn:
  1. Bỏ từ “sáng” + Xem 8 kết quả đầu thay vì 5 → hạng 8 trong top 8
  2. Bỏ từ “sáng” + Ưu tiên khoảng cách hơn (trọng số từ khóa 0.6 → 0.484) + Xem 7 kết quả đầu thay vì 5 → hạng 7 trong top 7
  3. Bỏ từ “sáng” + Thêm từ “Canteen” (có trong tên) → hạng 1 trong top 5

