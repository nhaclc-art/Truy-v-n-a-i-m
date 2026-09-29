# Kết quả đánh giá IR

- Thời điểm chạy (UTC): 2026-09-27T13:43:35+00:00
- Dataset: `ds-e4698de9ca`; hash cấu hình tìm kiếm: `deb364e2af24`; hash queries: `e0d390d9c4b5`; hash qrels: `e14ea1588df5`
- Người duyệt nhãn: Tran Dat
- 12 truy vấn; nhãn gán cho toàn bộ POI trong phạm vi (danh mục + bán kính) của từng truy vấn.
- Ba chế độ dùng cùng tập ứng viên truy xuất; Recall@5 chia cho tổng POI liên quan trong nhãn của cả phạm vi.

## Trung bình theo chế độ

| Chế độ | P@5 (mọi truy vấn) | P@5 (truy vấn có đáp án) | R@5 | Loại khỏi R@5 | nDCG@5 | Loại khỏi nDCG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A: BM25 | 0.5833 | 0.6364 | 0.8654 | 1 | 1.0000 | 1 |
| B: khoảng cách | 0.5167 | 0.5636 | 0.8048 | 1 | 0.8806 | 1 |
| C: kết hợp | 0.5667 | 0.6182 | 0.8553 | 1 | 0.9838 | 1 |

## Từng truy vấn

| Query | Nội dung | Chế độ | Trả về | Liên quan | P@5 | R@5 | nDCG@5 | Ghi chú tự động |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q01 | photocopy | A: BM25 | 4 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q01 | photocopy | B: khoảng cách | 4 | 3 | 0.6000 | 1.0000 | 0.9675 |  |
| Q01 | photocopy | C: kết hợp | 4 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q02 | van phong pham | A: BM25 | 7 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q02 | van phong pham | B: khoảng cách | 7 | 3 | 0.4000 | 0.6667 | 0.4162 |  |
| Q02 | van phong pham | C: kết hợp | 7 | 3 | 0.6000 | 1.0000 | 0.9675 |  |
| Q03 | cà phê | A: BM25 | 13 | 9 | 1.0000 | 0.5556 | 1.0000 | 9 POI liên quan > 5: Recall@5 tối đa 5/9 |
| Q03 | cà phê | B: khoảng cách | 13 | 9 | 0.4000 | 0.2222 | 0.3836 | 9 POI liên quan > 5: Recall@5 tối đa 5/9 |
| Q03 | cà phê | C: kết hợp | 13 | 9 | 0.8000 | 0.4444 | 0.8539 | 9 POI liên quan > 5: Recall@5 tối đa 5/9 |
| Q04 | circle k | A: BM25 | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q04 | circle k | B: khoảng cách | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q04 | circle k | C: kết hợp | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q05 | Demon Kitchen | A: BM25 | 1 | 1 | 0.2000 | 1.0000 | 1.0000 |  |
| Q05 | Demon Kitchen | B: khoảng cách | 1 | 1 | 0.2000 | 1.0000 | 1.0000 |  |
| Q05 | Demon Kitchen | C: kết hợp | 1 | 1 | 0.2000 | 1.0000 | 1.0000 |  |
| Q06 | com | A: BM25 | 3 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q06 | com | B: khoảng cách | 3 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q06 | com | C: kết hợp | 3 | 3 | 0.6000 | 1.0000 | 1.0000 |  |
| Q07 | trà sữa | A: BM25 | 3 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q07 | trà sữa | B: khoảng cách | 3 | 2 | 0.4000 | 1.0000 | 0.9197 |  |
| Q07 | trà sữa | C: kết hợp | 3 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q08 | cây xăng | A: BM25 | 7 | 7 | 1.0000 | 0.7143 | 1.0000 | 7 POI liên quan > 5: Recall@5 tối đa 5/7 |
| Q08 | cây xăng | B: khoảng cách | 7 | 7 | 1.0000 | 0.7143 | 1.0000 | 7 POI liên quan > 5: Recall@5 tối đa 5/7 |
| Q08 | cây xăng | C: kết hợp | 7 | 7 | 1.0000 | 0.7143 | 1.0000 | 7 POI liên quan > 5: Recall@5 tối đa 5/7 |
| Q09 | xe buýt | A: BM25 | 20 | 20 | 1.0000 | 0.2500 | 1.0000 | 20 POI liên quan > 5: Recall@5 tối đa 5/20 |
| Q09 | xe buýt | B: khoảng cách | 20 | 20 | 1.0000 | 0.2500 | 1.0000 | 20 POI liên quan > 5: Recall@5 tối đa 5/20 |
| Q09 | xe buýt | C: kết hợp | 20 | 20 | 1.0000 | 0.2500 | 1.0000 | 20 POI liên quan > 5: Recall@5 tối đa 5/20 |
| Q10 | phòng trọ | A: BM25 | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q10 | phòng trọ | B: khoảng cách | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q10 | phòng trọ | C: kết hợp | 2 | 2 | 0.4000 | 1.0000 | 1.0000 |  |
| Q11 | sửa xe máy | A: BM25 | 0 | 0 | 0.0000 | N/A | N/A | không có POI liên quan: Recall/nDCG N/A |
| Q11 | sửa xe máy | B: khoảng cách | 0 | 0 | 0.0000 | N/A | N/A | không có POI liên quan: Recall/nDCG N/A |
| Q11 | sửa xe máy | C: kết hợp | 0 | 0 | 0.0000 | N/A | N/A | không có POI liên quan: Recall/nDCG N/A |
| Q12 | pizza | A: BM25 | 4 | 4 | 0.8000 | 1.0000 | 1.0000 |  |
| Q12 | pizza | B: khoảng cách | 4 | 4 | 0.8000 | 1.0000 | 1.0000 |  |
| Q12 | pizza | C: kết hợp | 4 | 4 | 0.8000 | 1.0000 | 1.0000 |  |

## Giới hạn

- Đánh giá thăm dò trên corpus nhỏ và 12 truy vấn; không có ý nghĩa thống kê, không kết luận chế độ nào vượt trội chung.
- Nhãn nhị phân theo nhu cầu của từng truy vấn; nDCG không phản ánh mức hữu ích hay khoảng cách chi tiết.
- Trọng số chế độ kết hợp đặt tay, không chỉnh theo bộ truy vấn này.
- Nhận xét từng truy vấn của người đánh giá: bổ sung bên dưới.

## Nhận xét của người đánh giá

