Footprint Chart & Liquidity Heatmap Pro
Chào mừng Đại ca đến với dự án Footprint Chart và Heatmap Thanh khoản, một công cụ phân tích thị trường tài chính hiệu suất cao được xây dựng hoàn toàn bằng Python.
Dự án này cung cấp một cái nhìn sâu sắc về dòng lệnh (order flow) bằng cách hiển thị dữ liệu Footprint (khối lượng mua/bán tại từng mức giá) và một bản đồ nhiệt (heatmap) về thanh khoản (liquidity) trong sổ lệnh, tất cả đều được cập nhật theo thời gian thực.
Tính Năng Nổi Bật
Biểu đồ Footprint (Nến Dấu Chân): Hiển thị chi tiết khối lượng Mua (Ask) và Bán (Bid) tại từng mức giá bên trong mỗi cây nến.
Heatmap Thanh Khoản (Live): Trực quan hóa sổ lệnh (order book) theo thời gian thực. Các lệnh lớn sẽ có màu sắc nổi bật và mờ dần theo thời gian (15 phút) nếu chúng bị hủy hoặc khớp.
Heatmap Thanh Khoản (Lịch sử): (Chỉ cho 1M, 5M) Tải và hiển thị lịch sử thanh khoản đã được lưu trữ trong cơ sở dữ liệu DuckDB, cho phép Đại ca xem lại các vùng thanh khoản quan trọng trong quá khứ.
Volume Profile (VPVR): Biểu đồ khối lượng theo giá cho toàn bộ phạm vi dữ liệu đang xem.
Current Order Block (COB): Một thanh khoản kế (DOM) đơn giản hiển thị thanh khoản sổ lệnh hiện tại ngay bên cạnh biểu đồ.
Đa Khung Thời Gian: Hỗ trợ nhiều timeframe (1M, 5M, 15M, 1H, 4H, 1D).
Kiến trúc 3 Lớp (Multi-Process):
Cỗ máy Hút (Data Collector): Thu thập dữ liệu thô từ Binance.
Cỗ máy Chế Biến (Backend Processor): Xử lý, tổng hợp nến, và lưu trữ dữ liệu.
Giao diện (Frontend UI): Hiển thị dữ liệu một cách mượt mà.
Lưu trữ Lịch sử: Tự động lưu trữ lịch sử giao dịch vào file Parquet và lịch sử thanh khoản vào file DuckDB.
Tùy chỉnh cao: Giao diện cho phép tùy chỉnh màu sắc, phông chữ, và các tham số gộp giá (grouping).
Kiến Trúc Hệ Thống
Hệ thống được thiết kế theo mô hình 3 thành phần riêng biệt để đảm bảo hiệu suất và độ ổn định:
data_collector.py (Cỗ máy Hút - Nén - Bắn)
Chức năng: Kết nối trực tiếp tới API WebSocket của Binance.
Stream: Lắng nghe 2 stream: aggTrade (giao dịch) và depthUpdate (sổ lệnh).
Nhiệm vụ: Lấy dữ liệu thô (raw data) và "bắn" ngay lập tức ra một máy chủ WebSocket nội bộ (trên cổng 8765).
Lưu trữ: Ghi lại lịch sử giao dịch (trades) vào file btcusdt_aggtrades.parquet.
backend_processor.py (Cỗ máy Chế Biến)
Chức năng: Là bộ não của hệ thống. Nó chạy trên một luồng (thread) riêng biệt.
Input: Kết nối và nhận dữ liệu thô từ data_collector.py (từ cổng 8765).
Nhiệm vụ:
Xử lý Trades: Tổng hợp các giao dịch thô thành các nến Footprint theo từng khung thời gian (1M, 5M, 15M...).
Xử lý Thanh khoản: Nhận dữ liệu sổ lệnh thô và quẳng vào một hàng đợi (Queue).
Lưu trữ CSDL: Một luồng (thread) "Nhân Viên Kho" (db_writer_thread) riêng biệt sẽ lấy dữ liệu từ hàng đợi và ghi vào cơ sở dữ liệu DuckDB (heatmap_history.duckdb).
Output: Mở một máy chủ WebSocket khác (trên cổng 8766) để "bắn" dữ liệu đã được chế biến (nến Footprint, heatmap lịch sử, heatmap live) cho giao diện.
frontend_ui.py & main_app.py (Giao diện Người dùng)
Chức năng: Là ứng dụng Giao diện Đồ họa (GUI) mà Đại ca nhìn thấy.
Công nghệ: PySide6 (Qt for Python).
Input: Kết nối và nhận dữ liệu đã xử lý từ backend_processor.py (từ cổng 8766).
Nhiệm vụ:
Vẽ biểu đồ nến Footprint, VPVR, COB bằng QPainter.
Quản lý các trạng thái (auto-scroll, zoom, pan).
Gửi các yêu cầu (ví dụ: đổi timeframe, thay đổi cài đặt) về cho backend_processor.
main_app.py: Là file khởi động, có nhiệm vụ chạy backend_processor trong luồng nền và sau đó khởi động frontend_ui ở luồng chính.
Cài Đặt (Thư viện cần thiết)
Để chạy dự án, Đại ca cần cài đặt các thư viện Python sau. Đại ca có thể tạo một file requirements.txt với nội dung bên dưới và chạy pip install -r requirements.txt.
Nội dung requirements.txt:
PySide6
websockets
python-binance
pandas
numpy
aiohttp
requests
fastparquet
duckdb
Hoặc  có thể cài đặt thủ công:
Bash
pip install PySide6
pip install websockets
pip install python-binance
pip install pandas
pip install numpy
pip install aiohttp
pip install requests
pip install fastparquet
pip install duckdb
Cách Chạy Ứng Dụng
Đại ca cần chạy 2 file trong 2 cửa sổ Terminal (hoặc Command Prompt) riêng biệt. Thứ tự chạy rất quan trọng.
Terminal 1: Chạy data_collector.py (Cỗ máy Hút)
Bash
python data_collector.py
Đại ca sẽ thấy các log thông báo đã kết nối tới Binance và sẵn sàng bắn data qua cổng 8765.
Terminal 2: Chạy main_app.py (Ứng dụng chính)
Bash
python main_app.py
Sau khi chạy lệnh này, ứng dụng backend_processor sẽ tự động khởi động trong nền và giao diện (frontend) sẽ hiện lên. Giao diện sẽ tự động kết nối với backend, và backend sẽ kết nối với data collector.
Chờ vài giây để dữ liệu bắt đầu chảy về và biểu đồ sẽ tự động được vẽ.
Cấu Trúc File
.
├── main_app.py           # (File chạy chính) Khởi động Backend và Frontend
├── backend_processor.py  # (Lớp 2) Xử lý dữ liệu, tạo nến Footprint, quản lý CSDL
├── frontend_ui.py        # (Lớp 3) Toàn bộ code Giao diện (PySide6)
├── data_collector.py     # (Lớp 1) Hút dữ liệu thô từ Binance
│
├── heatmap_history.duckdb  # (Tự tạo) Cơ sở dữ liệu lưu lịch sử thanh khoản
├── btcusdt_aggtrades.parquet # (Tự tạo) File lưu lịch sử giao dịch
└── chart_settings.json       # (Tự tạo) File lưu cài đặt giao diện (màu sắc, v.v.)
