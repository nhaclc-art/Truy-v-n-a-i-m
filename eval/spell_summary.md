# Kết quả đánh giá sửa lỗi gõ

- Thời điểm chạy (UTC): 2026-09-23T15:42:05+00:00
- Dataset: `ds-7ac47a589e`; hash cấu hình: `9bebb53163b1`; hash biến thể: `7e49cc0bdc4d`
- 21 biến thể gõ sai của các truy vấn R5; dùng nhãn `eval/qrels.csv` của truy vấn gốc; chế độ xếp hạng BM25.
- "Giống truy vấn gốc": 5 kết quả đầu trùng khớp (cùng thứ tự) với truy vấn gõ đúng. "Rỗng": không trả về kết quả nào.

## Theo loại lỗi

| Loại lỗi | Số biến thể | Sửa lỗi gõ | Giống truy vấn gốc | Rỗng | P@5 | nDCG@5 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Sai chữ / đảo chữ | 12 | tắt | 0.0% | 100.0% | 0.0000 | 0.0000 |
| Sai chữ / đảo chữ | 12 | bật | 100.0% | 0.0% | 0.6000 | 1.0000 |
| Sót chữ Telex | 5 | tắt | 0.0% | 100.0% | 0.0000 | 0.0000 |
| Sót chữ Telex | 5 | bật | 80.0% | 20.0% | 0.5600 | 0.8000 |
| Gõ dính | 3 | tắt | 0.0% | 100.0% | 0.0000 | 0.0000 |
| Gõ dính | 3 | bật | 100.0% | 0.0% | 0.6667 | 1.0000 |
| Sai dấu | 1 | tắt | 100.0% | 0.0% | 0.4000 | 1.0000 |
| Sai dấu | 1 | bật | 100.0% | 0.0% | 0.4000 | 1.0000 |
| **Tất cả** | 21 | tắt | 4.8% | 95.2% | 0.0190 | 0.0476 |
| **Tất cả** | 21 | bật | 95.2% | 4.8% | 0.5905 | 0.9524 |

## Từng biến thể (sửa lỗi gõ bật)

| ID | Gốc | Gõ | Đã hiểu thành | Chỗ sửa | Giống gốc | nDCG@5 |
| --- | --- | --- | --- | --- | ---: | ---: |
| T01 | photocopy | photocoppy | photocopy | photocoppy → photocopy | có | 1.0000 |
| T02 | photocopy | photocopi | photocopy | photocopi → photocopy | có | 1.0000 |
| T03 | van phong pham | van phong phamm | van phong pham | phamm → pham | có | 1.0000 |
| T04 | van phong pham | vanphongpham | van phong pham | vanphongpham → van phong pham | có | 1.0000 |
| T05 | cà phê | ca phee | ca phe | phee → phe | có | 1.0000 |
| T06 | cà phê | caf phee | caf phe | phee → phe | không | 0.0000 |
| T07 | circle k | circlek | circle k | circlek → circle k | có | 1.0000 |
| T08 | circle k | circel k | circle k | circel → circle | có | 1.0000 |
| T09 | Demon Kitchen | demon kitchn | demon kitchen | kitchn → kitchen | có | 1.0000 |
| T10 | Demon Kitchen | deamon kitchen | demon kitchen | deamon → demon | có | 1.0000 |
| T11 | com | comm | com | comm → com | có | 1.0000 |
| T12 | trà sữa | tra suwa | tra sua | suwa → sua | có | 1.0000 |
| T13 | trà sữa | trà sũa | tra sua | — | có | 1.0000 |
| T14 | cây xăng | caay xawng | cay xang | caay → cay; xawng → xang | có | 1.0000 |
| T15 | cây xăng | cay xnag | cay xang | xnag → xang | có | 1.0000 |
| T16 | xe buýt | xe buyts | xe buyt | buyts → buyt | có | 1.0000 |
| T17 | xe buýt | xebuyt | xe buyt | xebuyt → xe buyt | có | 1.0000 |
| T18 | phòng trọ | phongf trooj | phong tro | phongf → phong; trooj → tro | có | 1.0000 |
| T19 | phòng trọ | phong troo | phong tro | troo → tro | có | 1.0000 |
| T20 | pizza | piza | pizza | piza → pizza | có | 1.0000 |
| T21 | pizza | pizzza | pizza | pizzza → pizza | có | 1.0000 |

## Giới hạn

- Biến thể do Claude soạn để phủ các kiểu lỗi thường gặp, không lấy từ nhật ký truy vấn thật; tỷ lệ lỗi thật chưa biết.
- Từ dưới 4 ký tự và từ là âm tiết tiếng Việt hợp lệ không được sửa (tránh đổi nghĩa), nên các lỗi như "caf" vẫn thất bại.
- Từ điển sửa lỗi là từ vựng của chính corpus nhỏ; từ đúng nhưng không có trong dữ liệu không được "sửa" thành từ khác.

