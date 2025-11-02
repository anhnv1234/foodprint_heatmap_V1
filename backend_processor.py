# -*- coding: utf-8 -*-
# FILE: backend_processor.py
# Chứa toàn bộ logic xử lý dữ liệu: Websocket, DuckDB, Quản lý nến Footprint.

# --- Imports cần thiết ---
import sys
import json
import os
from collections import deque, defaultdict
from datetime import datetime, timedelta, timezone 
import threading 
import time 
import queue 

import asyncio
import websockets
import pandas as pd
import math

# <<<< MỚI: Import CSDL >>>>
try:
    import duckdb
except ImportError:
    print("LỖI: Chưa cài 'duckdb'. Đại ca vui lòng chạy: pip install duckdb")
    sys.exit()

# ==============================================================================
# CẤU HÌNH VÀ CONSTANTS
# ==============================================================================

DATA_COLLECTOR_URI = "ws://localhost:8765"
SERVER_HOST = "localhost"
SERVER_PORT = 8766
SYMBOL = 'BTCUSDT'
CANDLE_DISPLAY_LIMIT = 200 
TIMEFRAMES_PANDAS = { '1M': '1min', '5M': '5min', '15M': '15min', '1H': '1h', '4H': '4h', '1D': '1D' }
DEFAULT_PRICE_GROUPING = {'1M':5, '5M':15, '15M':25, '1H':35, '4H':100, '1D':250}

# Cấu hình cho Heatmap Fading
HEATMAP_FADE_DURATION_MS = 15 * 60 * 1000 # 15 phút
HEATMAP_REFRESH_RATE_MS = 50 # 50ms (20 FPS)

# ==============================================================================
# CƠ SỞ DỮ LIỆU (DUCKDB)
# ==============================================================================
DB_FILE = 'heatmap_history.duckdb'
DB_BATCH_SIZE = 2000 
db_queue = queue.Queue() # Queue dùng để giao tiếp giữa Asyncio và Thread DuckDB
db_thread = None 

def print_log(message):
    """Ghi log với timestamp cho backend."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [PROCESSOR-RT] {message}")

def db_writer_thread():
    """Hàm 'Nhân Viên Kho' (Chạy trên Thread riêng) - Ghi vào DuckDB"""
    print_log(f"Luồng Ghi CSDL (DuckDB) đã khởi động. Đang kết nối tới {DB_FILE}...")
    db_conn = None
    try:
        db_conn = duckdb.connect(DB_FILE)
        db_conn.execute("""
            CREATE TABLE IF NOT EXISTS liquidity_updates (
                timestamp_ms BIGINT,
                price REAL,
                quantity REAL,
                side VARCHAR
            )
        """)
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON liquidity_updates (timestamp_ms)")
        print_log("Luồng CSDL kết nối thành công. Bắt đầu vòng lặp...")
        
        local_buffer = []
        last_commit_time = time.time()
        
        while True:
            try:
                data = db_queue.get(timeout=0.1) 
                
                if data is None: 
                    print_log("Luồng CSDL nhận tín hiệu tắt máy...")
                    break 
                    
                local_buffer.append(data)
                
                if len(local_buffer) >= DB_BATCH_SIZE:
                    db_conn.executemany("INSERT INTO liquidity_updates VALUES (?, ?, ?, ?)", local_buffer)
                    db_conn.commit()
                    db_conn.execute("CHECKPOINT")
                    local_buffer.clear()
                    last_commit_time = time.time()
                
            except queue.Empty:
                pass 
                
            current_time = time.time()
            if local_buffer and (current_time - last_commit_time > 5.0): # 5 giây
                db_conn.executemany("INSERT INTO liquidity_updates VALUES (?, ?, ?, ?)", local_buffer)
                db_conn.commit()
                db_conn.execute("CHECKPOINT")
                local_buffer.clear()
                last_commit_time = current_time

    except Exception as e:
        print_log(f"!!! Lỗi nghiêm trọng trong Luồng CSDL: {e}")
    finally:
        if db_conn:
            try:
                if local_buffer:
                    print_log(f"Ghi nốt {len(local_buffer)} dữ liệu cuối cùng...")
                    db_conn.executemany("INSERT INTO liquidity_updates VALUES (?, ?, ?, ?)", local_buffer)
                    db_conn.commit()
                    db_conn.execute("CHECKPOINT")
                print_log("Luồng CSDL đang đóng kết nối...")
                db_conn.close()
            except Exception as e:
                print_log(f"Lỗi khi đóng CSDL: {e}")
        print_log("Luồng CSDL đã dừng.")

# ==============================================================================
# LOGIC BACKEND
# ==============================================================================

# --- Biến toàn cục cho backend ---
connected_clients = set()
recent_candles = {tf: deque(maxlen=CANDLE_DISPLAY_LIMIT) for tf in TIMEFRAMES_PANDAS.keys()}
current_candles = {}
last_candle_close_prices = {}
current_price_grouping = DEFAULT_PRICE_GROUPING.copy()

def group_price(price, timeframe):
    global current_price_grouping 
    group_val = current_price_grouping.get(timeframe, DEFAULT_PRICE_GROUPING.get(timeframe, 10))
    if group_val <= 0: group_val = 1 
    return int(price / group_val) * group_val

def format_candle(candle):
    if not candle: return None
    levels_list = sorted([[p, round(vols['b'], 4), round(vols['a'], 4)] for p, vols in candle['levels'].items()], key=lambda x: x[0], reverse=True)
    formatted = candle.copy()
    formatted['timestamp'] = int(candle['timestamp'].timestamp() * 1000)
    formatted['levels'] = levels_list
    formatted['totalVolume'] = round(candle['totalVolume'], 4)
    return formatted

async def broadcast_to_frontend(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients], return_exceptions=True)

async def process_trade(trade):
    """Xử lý trade mới và cập nhật nến footprint hiện tại."""
    try:
        trade_time = pd.to_datetime(trade['T'], unit='ms', utc=True)
        trade_price = float(trade['p']); trade_qty = float(trade['q']); is_buyer_maker = trade['m']
        
        updated_tf = []
        for tf_key, tf_pandas in TIMEFRAMES_PANDAS.items():
            candle_timestamp = trade_time.floor(tf_pandas)
            
            if tf_key not in current_candles or current_candles[tf_key]['timestamp'] != candle_timestamp:
                if tf_key in current_candles and current_candles[tf_key]:
                    finished_candle = format_candle(current_candles[tf_key])
                    recent_candles[tf_key].append(finished_candle)
                
                last_close = last_candle_close_prices.get(tf_key, trade_price)
                current_candles[tf_key] = {
                    "timestamp": candle_timestamp, 
                    "time": candle_timestamp.strftime('%H:%M'), 
                    "open": last_close, "high": trade_price, "low": trade_price, 
                    "close": trade_price, "totalVolume": 0, "levels": {},
                }
            
            candle = current_candles[tf_key]
            candle.update(high=max(candle['high'], trade_price), low=min(candle['low'], trade_price), close=trade_price, totalVolume=candle['totalVolume'] + trade_qty)
            last_candle_close_prices[tf_key] = trade_price
            
            grouped_p = group_price(trade_price, tf_key)
            if grouped_p not in candle['levels']: candle['levels'][grouped_p] = {'b': 0, 'a': 0}
            if is_buyer_maker: candle['levels'][grouped_p]['b'] += trade_qty 
            else: candle['levels'][grouped_p]['a'] += trade_qty 
            updated_tf.append(tf_key)
            
        if updated_tf:
            message_to_send = {"type": "update", "data": {tf: format_candle(current_candles[tf]) for tf in updated_tf if tf in current_candles}}
            await broadcast_to_frontend(json.dumps(message_to_send))
    except Exception as e:
        print_log(f"Lỗi khi xử lý trade: {e}")

async def collector_subscriber():
    """Chạy trên luồng Asyncio, nhận data từ data_collector và quẳng vào Queue CSDL."""
    global db_queue
    while True:
        try:
            async with websockets.connect(DATA_COLLECTOR_URI) as websocket:
                print_log(f"Đã kết nối tới 'Tổng đài' {DATA_COLLECTOR_URI} để nhận dữ liệu trực tiếp.")
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if not isinstance(data, dict): continue
                        msg_type = data.get('type')
                        
                        if msg_type == 'liquidity_raw':
                            event_time = data.get('timestamp')
                            if not event_time: continue 
                            bids = data.get('bids', []); asks = data.get('asks', [])
                            # Gửi data liquidity vào queue cho luồng DuckDB
                            for p, q in bids: db_queue.put((event_time, float(p), float(q), 'bid'))
                            for p, q in asks: db_queue.put((event_time, float(p), float(q), 'ask'))
                            await broadcast_to_frontend(message) # Vẫn broadcast live

                        elif msg_type == 'trade':
                            trade_data = data.get('data') 
                            if trade_data: await process_trade(trade_data) 
                             
                    except json.JSONDecodeError: pass 
                    except Exception as e:
                        print_log(f"Lỗi khi xử lý tin nhắn từ collector: {e} - Tin nhắn (200 ký tự đầu): {message[:200]}...")
        except Exception as e:
            print_log(f"Mất kết nối với 'Tổng đài' data_collector: {e}. Thử lại sau 5 giây...")
            await asyncio.sleep(5) 

# ==============================================================================
# HÀM Truy vấn CSDL
# ==============================================================================
def _blocking_db_query(start_time_ms, price_grouping, min_liquidity):
    """Hàm I/O Chặn, chạy trên thread pool của asyncio."""
    
    with duckdb.connect(DB_FILE) as conn:
        query = f"""
            SELECT 
                (timestamp_ms / 1000) * 1000 AS time_bucket,
                CAST(price / {price_grouping} AS INTEGER) * {price_grouping} AS price_bucket,
                side,
                SUM(quantity) AS total_quantity
            FROM liquidity_updates
            WHERE 
                timestamp_ms >= {start_time_ms}
                AND quantity >= {min_liquidity}
            GROUP BY 
                time_bucket, price_bucket, side
            ORDER BY
                time_bucket, price_bucket
        """
        return conn.execute(query).df()

async def query_historical_heatmap(start_time_ms, price_grouping, min_liquidity):
    """Hàm Async (không chặn) để gọi hàm I/O Chặn."""
    loop = asyncio.get_event_loop()
    try:
        df = await loop.run_in_executor(None, _blocking_db_query, start_time_ms, price_grouping, min_liquidity)
        return df.to_dict('records')
    except Exception as e:
        print_log(f"Lỗi khi truy vấn CSDL heatmap: {e}")
        return []

async def serve_frontend_client(websocket, *args):
    """Xử lý kết nối từ Giao diện (PySide6 app)."""
    global current_price_grouping 
    
    connected_clients.add(websocket)
    print_log(f"Giao diện của Đại ca đã kết nối. Tổng số: {len(connected_clients)}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')

                if msg_type == 'request_timeframe':
                    tf = data.get('timeframe')
                    if tf in TIMEFRAMES_PANDAS:
                        # 1. Gửi nến
                        full_data_list = list(recent_candles[tf])
                        if tf in current_candles and current_candles[tf]:
                            full_data_list.append(format_candle(current_candles[tf]))
                        await websocket.send(json.dumps({ "type": "full_data", "timeframe": tf, "data": full_data_list }))
                        
                        # 2. Gửi Heatmap Lịch Sử
                        if tf in ['1M', '5M']: 
                            max_candles = data.get('max_candles', 200)
                            min_liq = data.get('min_liquidity', 0.1)
                            grouping_val = current_price_grouping.get(tf, 10)
                            if grouping_val <= 0: grouping_val = 1
                            
                            tf_duration_ms = pd.to_timedelta(TIMEFRAMES_PANDAS[tf]).total_seconds() * 1000
                            total_duration_ms = max_candles * tf_duration_ms
                            end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                            # Lùi lại 5 nến dự phòng
                            start_time_ms = end_time_ms - total_duration_ms - (tf_duration_ms * 5) 
                            
                            print_log(f"Đang truy vấn CSDL heatmap cho {tf} từ {datetime.fromtimestamp(start_time_ms/1000)}...")
                            heatmap_data = await query_historical_heatmap(start_time_ms, grouping_val, min_liq)
                            print_log(f"Truy vấn xong, gửi {len(heatmap_data)} điểm dữ liệu heatmap.")
                            
                            await websocket.send(json.dumps({
                                "type": "full_heatmap",
                                "timeframe": tf,
                                "data": heatmap_data
                            }))
                
                elif msg_type == 'update_settings': 
                    new_grouping = data.get('price_grouping')
                    if isinstance(new_grouping, dict):
                        current_price_grouping.update(new_grouping) # Chỉ update, không replace toàn bộ
                        print_log(f"Backend đã cập nhật PRICE_GROUPING: {current_price_grouping}")
                        
            except json.JSONDecodeError:
                print_log(f"Nhận được tin nhắn rác (không phải JSON): {message}")
            except Exception as e:
                print_log(f"Lỗi khi xử lý tin nhắn từ client: {e}")
                    
    except Exception as e:
        print_log(f"Lỗi giao tiếp với client: {e}")
    finally:
        connected_clients.remove(websocket)
        print_log(f"Giao diện đã ngắt kết nối. Còn lại: {len(connected_clients)}")


async def start_backend_server(): 
    """Hàm main_async của backend, khởi động server cho frontend và subscriber."""
    print_log("Cỗ máy CHẾ BIẾN đang khởi động...")
    server = await websockets.serve(serve_frontend_client, SERVER_HOST, SERVER_PORT)
    print_log(f"Server cho giao diện đã sẵn sàng tại ws://{SERVER_HOST}:{SERVER_PORT}")
    
    subscriber_task = asyncio.create_task(collector_subscriber())
    await asyncio.gather(subscriber_task, server.wait_closed())

# ==============================================================================
# HÀM KHỞI ĐỘNG BACKEND TRONG THREAD MỚI
# (Cần dùng trong main_app.py)
# ==============================================================================

def run_backend_in_thread():
    """Thiết lập và chạy event loop của asyncio trong một thread riêng biệt."""
    global db_thread
    
    # 1. Khởi động "Nhân Viên Kho" (Luồng CSDL)
    print_log("Khởi tạo luồng (thread) mới cho CSDL DuckDB...")
    db_thread = threading.Thread(target=db_writer_thread, daemon=True) 
    db_thread.start()
    
    # 2. Khởi động Luồng Asyncio (Websocket, Trades)
    print_log("Khởi tạo luồng (thread) mới cho backend asyncio...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_backend_server())
    except asyncio.CancelledError:
        print_log("Luồng backend đã bị hủy.")
    finally:
        loop.close()
        print_log("Đã đóng event loop của luồng backend.")

# Exports cần thiết cho main_app.py:
# run_backend_in_thread, db_queue, db_thread, SERVER_HOST, SERVER_PORT
# Exports cần thiết cho frontend_ui.py:
# HEATMAP_FADE_DURATION_MS, HEATMAP_REFRESH_RATE_MS, TIMEFRAMES_PANDAS, DEFAULT_PRICE_GROUPING