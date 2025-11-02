# -*- coding: utf-8 -*-
# FILE: main_app.py
# Khối khởi động ứng dụng: Khởi chạy Backend và Frontend.

import sys
import threading
import time

# Import từ các file đã tách
try:
    from frontend_ui import MainWindow
    from backend_processor import run_backend_in_thread, db_queue, db_thread
    from PySide6.QtWidgets import QApplication
except ImportError as e:
    print(f"LỖI: Không tìm thấy module cần thiết. Đại ca kiểm tra lại đã lưu 2 file kia chưa: {e}")
    sys.exit()

if __name__ == "__main__":
    try:
        # 1. Khởi động backend server (asyncio + CSDL) trong một luồng (thread) riêng
        # Hàm run_backend_in_thread sẽ tự khởi động luồng DuckDB bên trong nó.
        print("Đang khởi tạo luồng Backend (Xử lý Footprint & CSDL)...")
        backend_thread = threading.Thread(target=run_backend_in_thread, daemon=True)
        backend_thread.start()
        
        # Cho backend một chút thời gian để khởi động server websocket
        time.sleep(2) 
        
        # 2. Khởi động ứng dụng PySide6 (frontend) trên luồng chính
        print("Đang khởi động giao diện (frontend) PySide6...")
        app = QApplication(sys.argv)
        
        # Truyền tham chiếu db_queue và db_thread cho MainWindow để nó có thể đóng gọn gàng
        window = MainWindow(db_queue, db_thread) 
        
        window.show()
        sys.exit(app.exec())
        
    except KeyboardInterrupt:
        print("Đã dừng ứng dụng theo lệnh Đại ca.")
        # Gửi tín hiệu dừng cho luồng DuckDB
        db_queue.put(None)
        time.sleep(1) 
        sys.exit(0)