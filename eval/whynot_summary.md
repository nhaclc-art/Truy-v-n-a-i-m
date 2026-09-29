# Kết quả đánh giá why-not

- Thời điểm chạy (UTC): 2026-09-23T15:42:05+00:00
- Dataset: `ds-7ac47a589e`; hash cấu hình: `9bebb53163b1`; k = 5; λ = 0.5; tối đa 2 thay đổi (nới khi POI bị nhiều bộ lọc chặn).
- Nguồn câu hỏi: 68 câu suy ra từ nhãn R5 (12 truy vấn × 3 chế độ); 15 câu soạn tay (whynot_questions.csv)
- "Trả lời được": có ít nhất một truy vấn sửa đưa POI vào top-k' và đã được chạy lại bằng search() để xác nhận. "Giữ nguyên k": truy vấn sửa đưa POI vào đúng top-k ban đầu.
- Penalty = λ·Δk + (1 − λ)·Δq (He & Lo, ICDE 2012; Chen et al., ICDE 2015). Giữ kết quả cũ = tỷ lệ top-k ban đầu còn trong top-k' của truy vấn sửa.
- Câu hỏi không hợp lệ (POI thật ra đã nằm trong top-k) được loại khỏi trung bình: 0.
- Đề xuất bị loại vì chạy lại không khớp: 0 (phải bằng 0).

## Tổng quan

| Tập câu hỏi | Số câu | Hợp lệ | Trả lời được | Trả lời được, giữ nguyên k | Penalty nhỏ nhất (TB) | Giữ kết quả cũ (TB) | Chẩn đoán đúng | Median / p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tất cả | 83 | 83 | 100.0% | 100.0% | 0.187 | 13.4% | 100.0% (15 câu) | 9.2 / 10.8 |
| Từ nhãn R5 | 68 | 68 | 100.0% | 100.0% | 0.171 | 12.1% | — | 9.2 / 10.8 |
| Từ nhãn R5, bỏ Q09 (xe buýt) | 23 | 23 | 100.0% | 100.0% | 0.179 | 26.1% | — | 7.2 / 8.3 |
| Soạn tay | 15 | 15 | 100.0% | 100.0% | 0.259 | 32.0% | 100.0% (15 câu) | 7.1 / 10.1 |

## So sánh chiến lược sửa (mọi câu hỏi hợp lệ)

| Chiến lược | Trả lời được (cho phép tăng k) | Trả lời được, giữ nguyên k | Penalty nhỏ nhất (TB, câu trả lời được) | Giữ kết quả cũ (TB) |
| --- | ---: | ---: | ---: | ---: |
| S1: Tăng k | 86.7% | 0.0% | 0.500 | 100.0% |
| S2: Đổi chế độ xếp hạng | 86.7% | 31.3% | 0.488 | 69.4% |
| S3: Chỉnh trọng số α | 69.9% | 28.9% | 0.537 | 75.5% |
| S4: Nới bán kính | 89.2% | 6.0% | 0.621 | 99.2% |
| S5: Bỏ lọc danh mục | 89.2% | 2.4% | 0.736 | 100.0% |
| S6: Bỏ từ khóa | 92.8% | 12.0% | 0.686 | 92.8% |
| S7: Thêm/thay từ trong tên | 89.2% | 84.3% | 0.211 | 11.3% |
| ALL: Kết hợp theo penalty | 100.0% | 100.0% | 0.187 | 13.4% |

## Phân bố lý do (câu hỏi hợp lệ)

| Lý do | Số câu |
| --- | ---: |
| xếp hạng thấp | 72 |
| thiếu từ khóa | 5 |
| ngoài bán kính | 3 |
| khác danh mục | 2 |
| thiếu từ khóa + ngoài bán kính | 1 |

## Câu hỏi soạn tay

| ID | Truy vấn | POI mong đợi | Lý do dự kiến | Lý do hệ thống | Đề xuất tốt nhất | Hạng mới / k' | Penalty |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| W01 | chỗ in tài liệu · 1000 m · combined | Tiệm Photocopy Ngọc Lan | thiếu từ khóa | thiếu từ khóa ✓ | Bỏ từ “chỗ”, “tài”, “liệu” | 3 / 5 | 0.375 |
| W02 | đổ xăng · 1000 m · distance | Petrolimex | thiếu từ khóa | thiếu từ khóa ✓ | Bỏ từ “đổ” | 1 / 5 | 0.25 |
| W03 | cà phê sữa đá · 500 m · combined | Cà Phê Rita Võ | thiếu từ khóa | thiếu từ khóa ✓ | Bỏ từ “sữa”, “đá” | 2 / 5 | 0.25 |
| W04 | circle k · 300 m · distance | Circle K | khác danh mục | khác danh mục ✓ | Bỏ lọc “Ăn uống” | 1 / 5 | 0.25 |
| W05 | gs25 · 300 m · distance | GS25 | khác danh mục | khác danh mục ✓ | Bỏ lọc “Ăn uống” | 1 / 5 | 0.25 |
| W06 | pizza · 300 m · distance | Pizza Hut | ngoài bán kính | ngoài bán kính ✓ | Nới bán kính lên 500 m | 1 / 5 | 0.1667 |
| W07 | cây xăng · 500 m · distance | Cửa Hàng Xăng Dầu Petrolimex | ngoài bán kính | ngoài bán kính ✓ | Nới bán kính lên 1 km | 2 / 5 | 0.1667 |
| W08 | photocopy · 500 m · distance | Tiệm Photocopy Ngọc Lan | ngoài bán kính | ngoài bán kính ✓ | Nới bán kính lên 1 km | 2 / 5 | 0.1667 |
| W09 | cà phê · 500 m · distance | Cafe Thềm Xưa | xếp hạng thấp | xếp hạng thấp ✓ | Thêm từ “Thềm” (có trong tên) | 1 / 5 | 0.1667 |
| W10 | cà phê · 500 m · bm25 | Cà phê Nha | xếp hạng thấp | xếp hạng thấp ✓ | Thêm từ “Nha” (có trong tên) | 1 / 5 | 0.1667 |
| W11 | cà phê · 500 m · combined | Coffee 161 | xếp hạng thấp | xếp hạng thấp ✓ | Xếp theo “Đúng từ khóa” | 5 / 5 | 0.25 |
| W12 | xe buýt · 500 m · distance | Chợ Bầu Sen | xếp hạng thấp | xếp hạng thấp ✓ | Thêm từ “Bầu” (có trong tên) | 1 / 5 | 0.1667 |
| W13 | ăn sáng · 500 m · combined | Canteen SGU | thiếu từ khóa | thiếu từ khóa ✓ | Bỏ từ “sáng” + Xem 8 kết quả đầu thay vì 5 | 8 / 8 | 0.267 |
| W14 | siêu thị · 500 m · distance | GS25 | thiếu từ khóa | thiếu từ khóa ✓ | Bỏ từ “siêu”, “thị” | 1 / 5 | 0.5 |
| W15 | đổ xăng · 300 m · distance | Cửa Hàng Xăng Dầu Petrolimex | thiếu từ khóa + ngoài bán kính | thiếu từ khóa + ngoài bán kính ✓ | Bỏ từ “đổ” + Nới bán kính lên 1 km | 2 / 5 | 0.5 |

## Khảo sát người dùng (thăm dò)

Chưa có câu trả lời khảo sát trong `eval/whynot_survey.csv`.

## Giới hạn

- Tập câu hỏi nhỏ; nhãn R5 do một người duyệt. Kết quả chỉ mang tính thăm dò, không có ý nghĩa thống kê.
- λ và chi phí từng loại thay đổi đặt tay, chưa tối ưu; penalty chỉ so sánh được giữa các đề xuất cho cùng một câu hỏi.
- Câu hỏi từ nhãn R5 chủ yếu thuộc loại "xếp hạng thấp" vì truy xuất hiện không bỏ sót POI liên quan; câu hỏi soạn tay bổ sung các loại còn lại.

