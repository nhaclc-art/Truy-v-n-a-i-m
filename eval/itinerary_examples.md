# Ví dụ lập lộ trình nhiều chặng (thăm dò, không phải đánh giá IR)

Dataset: `ds-e4698de9ca`.

## Ba chặng mặc định (giống giao diện): cà phê → cơm → phim (ngân sách 3.00 km)

- Tổ hợp đã xét: 0; trong ngân sách: 0.
- Không có lộ trình nào lọt ngân sách (một chặng rỗng hoặc trùng địa điểm).

## Ba chặng có thật trong dữ liệu: cà phê → cơm → xe buýt (ngân sách 3.00 km)

- Tổ hợp đã xét: 192; trong ngân sách: 107.
- Lộ trình tốt nhất: Cà Phê Rita Võ → Cơm Tấm Nguyễn Văn Cừ → Phan Văn Trị — tổng 673 m, ~144 phút.
- Số lộ trình trả về: 3.

## Ngân sách hẹp: cà phê → cơm → phim (ngân sách 1.50 km)

- Tổ hợp đã xét: 0; trong ngân sách: 0.
- Không có lộ trình nào lọt ngân sách (một chặng rỗng hoặc trùng địa điểm).

## Hai chặng: photocopy → cây xăng (ngân sách 2.00 km)

- Tổ hợp đã xét: 56; trong ngân sách: 8.
- Lộ trình tốt nhất: Huỳnh Trí → Petrolimex — tổng 1.24 km, ~107 phút.
- Số lộ trình trả về: 3.

## Bốn chặng: cà phê → photocopy → cây xăng → xe buýt (ngân sách 5.00 km)

- Tổ hợp đã xét: 3584; trong ngân sách: 1614.
- Lộ trình tốt nhất: Coffee 161 → Huỳnh Trí → Petrolimex → Huỳnh Mẫn Đạt — tổng 1.86 km, ~205 phút.
- Số lộ trình trả về: 3.

