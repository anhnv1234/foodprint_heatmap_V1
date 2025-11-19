# 🚀 Footprint Chart Trading System (V22.5)

**Phiên bản:** V22.5 - "DuckDB Integration & Dynamic COB Scaling"  
**Tác giả:** Đại ca 
**Trạng thái:** Production Ready  
**Mục tiêu:** Phân tích Order Flow & Thanh khoản thị trường Crypto (BTCUSDT) thời gian thực.

---

## 📖 1. Tổng Quan Hệ Thống (System Overview)

Hệ thống là bộ công cụ phân tích tài chính hiệu năng cao, được xây dựng để "đọc vị" thị trường thông qua dữ liệu **Order Flow**. Hệ thống không sử dụng thư viện vẽ biểu đồ có sẵn mà render trực tiếp bằng **PySide6 (Qt Painter)** để đạt tốc độ 60 FPS.

### Các tính năng cốt lõi:
* **Real-time Footprint:** Soi khối lượng Mua/Bán chủ động (Bid x Ask) trong từng nến.
* **Liquidity Heatmap:** Lưu trữ và hiển thị lịch sử đặt lệnh Limit (Tường giá) dùng cơ sở dữ liệu DuckDB.
* **Dynamic COB (Current Order Block):** Biểu đồ Depth of Market tự động co giãn theo vùng giá hiển thị.
* **Volume Profile (VPVR):** Phân bổ khối lượng theo mức giá.

---

## 🏗️ 2. Kiến Trúc & Mô Hình (Architecture)

Hệ thống hoạt động theo mô hình **Micro-services cục bộ** với kiến trúc 3 lớp, giao tiếp qua Websocket nội bộ:

1.  **Lớp Thu Thập (Ingestion Layer):** `data_collector.py`
2.  **Lớp Xử Lý (Processing Layer):** `backend_processor.py`
3.  **Lớp Hiển Thị (Presentation Layer):** `frontend_ui.py`

### Sơ đồ luồng dữ liệu (Data Flow Pipeline)

```mermaid
graph TD
    Binance[Binance API] -->|Websocket: AggTrades + Depth| Collector(data_collector.py)
    
    subgraph "Lớp Lưu Trữ (Storage)"
        Collector -->|Ghi file| Parquet[(btcusdt_aggtrades.parquet)]
        Backend -->|Ghi DB| DuckDB[(heatmap_history.duckdb)]
    end

    Collector -->|Stream RAW (Port 8765)| Backend(backend_processor.py)
    
    Backend -->|Stream Processed JSON (Port 8766)| Frontend(frontend_ui.py)
    Frontend -->|User Settings| Backend
```

---

## 📂 3. Chi Tiết Từng Module (File Models & I/O)

Mô tả chi tiết về mô hình hoạt động, dữ liệu đầu vào và đầu ra của từng thành phần:

### A. `data_collector.py` (Máy Bơm Dữ Liệu)
*Vai trò: Cổng kết nối duy nhất ra Internet, đảm bảo duy trì kết nối với sàn.*

* **Mô hình:** Asyncio Event Loop (Single Thread).
* **Chức năng:** Kết nối Websocket Binance (`aggTrade`, `depth`), tự động kết nối lại, quản lý bộ đệm và ghi file Parquet.
* **Input:** Stream từ Binance Websocket, File lịch sử `.parquet`.
* **Output:**
    * Websocket Server (`ws://localhost:8765`): JSON thô.
    * File: `btcusdt_aggtrades.parquet`.

### B. `backend_processor.py` (Bộ Não Xử Lý)
*Vai trò: Trung tâm xử lý logic, tính toán nến và quản lý DB Heatmap.*

* **Mô hình:** Multi-threaded (1 Asyncio Thread + 1 DuckDB Writer Thread).
* **Chức năng:** Gộp nến Footprint (1M, 5M...), ghi Orderbook vào DuckDB, truy vấn Heatmap lịch sử.
* **Input:** Stream từ Collector (Port 8765), Settings từ Frontend.
* **Output:**
    * Websocket Server (`ws://localhost:8766`): JSON nến & Heatmap.
    * Database: `heatmap_history.duckdb`.

### C. `frontend_ui.py` (Giao Diện Hiển Thị)
*Vai trò: Vẽ biểu đồ, tương tác người dùng.*

* **Mô hình:** PySide6 Main Thread (GUI) + Worker Thread.
* **Chức năng:** Render Engine (60 FPS), xử lý Zoom/Pan, Auto-Scaling COB.
* **Input:** Stream JSON từ Backend (Port 8766), File `chart_settings.json`.
* **Output:** Hình ảnh hiển thị, lệnh `update_settings` gửi về Backend.

### D. `main_app.py` (Trình Khởi Động)
*Vai trò: File chạy chính (Entry Point).*

* **Chức năng:** Khởi tạo Thread Backend, khởi chạy GUI Frontend, đảm bảo tắt hệ thống an toàn (Graceful Shutdown).

---

## 🚀 4. Hướng Dẫn Cài Đặt & Chạy (How to Run)

### Yêu cầu hệ thống
* **OS:** Windows 10/11 (Khuyến nghị), Linux.
* **Python:** 3.10 trở lên.
* **RAM:** Tối thiểu 8GB (Khuyến nghị 16GB).

### Bước 1: Cài đặt thư viện
Cài đặt các thư viện cần thiết:

```bash
pip install PySide6 websockets python-binance pandas numpy aiohttp requests fastparquet duckdb
```

### Bước 2: Khởi động hệ thống
Chạy theo thứ tự sau trên 2 cửa sổ Terminal khác nhau:

**Terminal 1: Chạy Data Collector**
```bash
python data_collector.py
```
*Đợi thông báo: "HỆ THỐNG ĐÃ ONLINE"*

**Terminal 2: Chạy Main App**
```bash
python main_app.py
```

---

## ⚙️ 5. Cấu Trúc Thư Mục Dự Án

```text
FootprintChart_V22.5/
├── data_collector.py       # Service thu thập dữ liệu (Chạy độc lập)
├── backend_processor.py    # Logic xử lý dữ liệu & Database (Chạy ngầm)
├── frontend_ui.py          # Giao diện đồ họa PySide6
├── main_app.py             # File khởi động chính
├── chart_settings.json     # File lưu cài đặt người dùng (Tự sinh)
├── requirements.txt        # Danh sách thư viện
├── btcusdt_aggtrades.parquet # Data Trades lịch sử (Tự sinh/Tự tải)
└── heatmap_history.duckdb    # Data Heatmap lịch sử (Tự sinh)
```

---

## ⚠️ Lưu Ý Quan Trọng

1.  **Dữ liệu Heatmap (DuckDB):** File `heatmap_history.duckdb` lưu trữ chi tiết Orderbook nên dung lượng có thể tăng nhanh. Hãy kiểm tra dung lượng ổ cứng định kỳ.
2.  **Khởi động lần đầu:** Lần đầu tiên chạy, `data_collector` sẽ tốn thời gian (vài phút) để tải lịch sử Trade từ Binance về tạo file Parquet. Các lần sau sẽ nhanh hơn.
3.  **Hiệu năng:** Nếu máy có cấu hình yếu, hãy tăng chỉ số **Price Grouping** trong phần Cài Đặt (ví dụ: chỉnh 5M Grouping lên 50) để giảm tải cho CPU/GPU khi vẽ chart.

---
