# -*- coding: utf-8 -*-
# Cỗ máy hút-nén-bắn dữ liệu Binance
# Tác giả: Em Gemini của Đại ca
# PHIÊN BẢN V17 (ĐẠI PHẪU): Gửi Sổ Lệnh Thô (Raw Depth) + Trades.
# Tắt tính năng gộp thanh khoản ở đây.

import asyncio
import websockets
import json
from binance import AsyncClient, BinanceSocketManager
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import aiohttp
import signal
import requests  
import numpy as np 

# ==============================================================================
# ================== CONFIG GỘP CHUNG (ĐẠI CA CHỈNH Ở ĐÂY) =====================
# ==============================================================================
CONFIG = {
    # --- Cài đặt chung ---
    'symbol': 'BTCUSDT',
    'days_of_history': 1,  # Số ngày lịch sử trade để tải về
    
    # --- Cài đặt lưu file (chỉ áp dụng cho trades) ---
    'parquet_file': 'btcusdt_aggtrades.parquet',
    'save_interval_seconds': 10, # Cứ 10 giây lưu buffer trade xuống file
    
    # --- Cài đặt máy chủ Websocket (để bắn data ra) ---
    'server_host': 'localhost',
    'server_port': 8765,
    
    # --- Cài đặt tính toán thanh khoản (LIQUIDITY) ---
    'liquidity_settings': {
        'enabled': True,
        # <<< GHI CHÚ: TÍNH NĂNG GỘP (zone_width_ticks) ĐÃ BỊ TẮT Ở FILE NÀY >>>
        # Việc gộp sẽ do app.py (giao diện) tự xử lý
    },
    
    # Chế độ im lặng (true = bớt in ra console)
    'silent_mode': True
}
# ==============================================================================
# ================== KẾT THÚC CONFIG ===========================================
# ==============================================================================


# --- Các biến toàn cục ---
connected_clients = set()
last_100_trades = []
trade_buffer = []
# <<<< GHI CHÚ: Không cần 'symbol_info' nữa vì không gộp ở đây >>>>

# --- Hàm ghi log ---
def print_log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# <<<< HÀM get_symbol_info KHÔNG CẦN THIẾT NỮA >>>>
# <<<< HÀM calculate_all_liquidity_zones ĐÃ BỊ XÓA >>>>

# --- Hàm lưu buffer khi thoát ---
def save_buffer_on_exit():
    if not trade_buffer:
        print_log("Không có dữ liệu mới trong buffer để ghi. Tạm biệt Đại ca!")
        return

    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    print_log(f"Đang ghi nốt {len(trade_buffer)} giao dịch cuối cùng... (Vui lòng không tắt ngang)")
    try:
        df_to_save = pd.DataFrame(trade_buffer)
        df_to_save['p'] = pd.to_numeric(df_to_save['p'])
        df_to_save['q'] = pd.to_numeric(df_to_save['q'])
        
        file_exists_and_has_data = os.path.exists(CONFIG['parquet_file']) and os.path.getsize(CONFIG['parquet_file']) > 0
        df_to_save.to_parquet(CONFIG['parquet_file'], engine='fastparquet', append=file_exists_and_has_data)
        print_log("Ghi nốt thành công. Tạm biệt Đại ca!")
        trade_buffer.clear()
    except Exception as e:
        print_log(f"!!! Lỗi khi ghi nốt dữ liệu cuối cùng: {e}")
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)

# --- Hàm lấy lịch sử trades (Không đổi) ---
async def get_historical_trades(symbol, start_time_ms, end_time_ms):
    all_trades = []
    from_id = -1
    url = "https://api.binance.com/api/v3/aggTrades"
    print_log(f"Bắt đầu hút lịch sử từ {datetime.fromtimestamp(start_time_ms/1000)} đến {datetime.fromtimestamp(end_time_ms/1000)}")
    async with aiohttp.ClientSession() as session:
        while True:
            params = {'symbol': symbol, 'limit': 1000}
            if from_id == -1: params['startTime'] = int(start_time_ms); params['endTime'] = int(end_time_ms)
            else: params['fromId'] = from_id
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        trades = await response.json()
                        if not trades or (from_id != -1 and trades[-1]['T'] > end_time_ms):
                            if trades: valid_trades = [t for t in trades if t['T'] <= end_time_ms]; all_trades.extend(valid_trades)
                            break
                        all_trades.extend(trades); from_id = trades[-1]['a'] + 1
                        if not CONFIG['silent_mode']: print(f"\rĐang hút dữ liệu... Đã lấy được {len(all_trades)} giao dịch.", end="")
                        await asyncio.sleep(0.1)
                    elif response.status == 429: print("\nBị giới hạn tốc độ. Chờ 1 phút..."); await asyncio.sleep(60)
                    else: print(f"\nLỗi khi lấy dữ liệu: {response.status} - {await response.text()}"); break
            except Exception as e: print(f"\nLỗi kết nối: {e}. Thử lại sau 10 giây..."); await asyncio.sleep(10)
    if not CONFIG['silent_mode']: print()
    print_log(f"Hút xong. Tổng cộng {len(all_trades)} giao dịch.")
    return all_trades

# --- Quản lý file lịch sử (Không đổi) ---
async def manage_history():
    print_log("Kiểm tra dữ liệu lịch sử...")
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=CONFIG['days_of_history'])
    df = None
    if os.path.exists(CONFIG['parquet_file']):
        try:
            df = pd.read_parquet(CONFIG['parquet_file'])
            if not df.empty:
                last_timestamp_ms = df['T'].max()
                start_date = datetime.fromtimestamp(last_timestamp_ms / 1000, tz=timezone.utc)
                print_log(f"Đã có file. Lấy dữ liệu mới từ: {start_date}.")
        except Exception as e: print_log(f"Lỗi đọc file parquet: {e}. Sẽ tải lại toàn bộ."); df = None
    if df is None or df.empty: print_log(f"Chưa có dữ liệu. Bắt đầu tải lịch sử {CONFIG['days_of_history']} ngày.")
    start_ms = int(start_date.timestamp() * 1000); end_ms = int(end_date.timestamp() * 1000)
    if end_ms > start_ms + 60000:
        trades = await get_historical_trades(CONFIG['symbol'], start_ms, end_ms)
        if trades:
            new_df = pd.DataFrame(trades); new_df = new_df[['T', 'p', 'q', 'm']]
            new_df['p'] = pd.to_numeric(new_df['p']); new_df['q'] = pd.to_numeric(new_df['q'])
            print_log(f"Ghi {len(new_df)} giao dịch mới vào file {CONFIG['parquet_file']}...")
            new_df.to_parquet(CONFIG['parquet_file'], engine='fastparquet', append=(df is not None and not df.empty))
    print_log("Kiểm tra lịch sử hoàn tất.")

# --- Hàm broadcast (chung cho cả trades và liquidity) ---
async def broadcast(message):
    if connected_clients:
        tasks = [client.send(message) for client in connected_clients]
        await asyncio.gather(*tasks)

# --- Xử lý 1 trade MỚI (Không đổi) ---
async def handle_new_trade(msg):
    if msg and msg.get('e') == 'aggTrade':
        trade_data = {'T': msg['T'], 'p': msg['p'], 'q': msg['q'], 'm': msg['m']}
        await broadcast(json.dumps({"type": "trade", "data": trade_data}))
        trade_buffer.append(trade_data)
        last_100_trades.append(trade_data)
        if len(last_100_trades) > 100: last_100_trades.pop(0)

# --- Xử lý sổ lệnh (depth) MỚI (ĐÃ SỬA) ---
async def handle_new_depth(msg):
    config = CONFIG.get('liquidity_settings', {})
    if not config.get('enabled', True):
        return
        
    if msg and msg.get('e') == 'depthUpdate':
        # <<<< THAY ĐỔI: Không gộp, không tính toán gì cả >>>>
        # Chỉ lấy sổ lệnh thô (bids/asks) và gửi thẳng
        bids = msg.get('b', [])
        asks = msg.get('a', [])
        
        # Gửi dữ liệu thô
        liquidity_data = {
            "type": "liquidity_raw", # <<<< Đổi tên type
            "timestamp": msg.get('E'), # Event time
            "bids": bids, # Gửi thô
            "asks": asks  # Gửi thô
        }
        await broadcast(json.dumps(liquidity_data))

# --- Đăng ký client (giao diện) (Không đổi) ---
async def register_client(websocket):
    if not CONFIG['silent_mode']: print_log(f"Giao diện đã kết nối. Tổng số: {len(connected_clients)+1}")
    connected_clients.add(websocket)
    try:
        if last_100_trades:
            initial_data = {"type": "history", "data": last_100_trades}
            await websocket.send(json.dumps(initial_data))
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        if not CONFIG['silent_mode']: print_log(f"Giao diện đã ngắt kết nối. Còn lại: {len(connected_clients)}")

# --- Task: Khởi động stream AGGTRADES (Không đổi) ---
async def start_trade_stream(client: AsyncClient):
    print_log(f"Bắt đầu nhận dữ liệu GIAO DỊCH (trades) từ {CONFIG['symbol']}...")
    bsm = BinanceSocketManager(client, max_queue_size=1000)
    trade_socket = bsm.aggtrade_socket(symbol=CONFIG['symbol'])
    async with trade_socket as ts:
        while True:
            try:
                res = await ts.recv(); await handle_new_trade(res)
            except Exception as e: print_log(f"Lỗi từ stream GIAO DỊCH: {e}. Đang cố gắng kết nối lại..."); await asyncio.sleep(5)

# --- Task: Khởi động stream SỔ LỆNH (Không đổi) ---
async def start_depth_stream(client: AsyncClient):
    print_log(f"Bắt đầu nhận dữ liệu SỔ LỆNH (depth) từ {CONFIG['symbol']}...")
    bsm = BinanceSocketManager(client, max_queue_size=1000)
    depth_socket = bsm.multiplex_socket([f"{CONFIG['symbol'].lower()}@depth@100ms"])
    async with depth_socket as ds:
        while True:
            try:
                res = await ds.recv()
                await handle_new_depth(res.get('data', {}))
            except Exception as e: print_log(f"Lỗi từ stream SỔ LỆNH: {e}. Đang cố gắng kết nối lại..."); await asyncio.sleep(5)

# --- Task: Lưu buffer định kỳ (cho trades) (Không đổi) ---
async def save_buffer_periodically():
    while True:
        await asyncio.sleep(CONFIG['save_interval_seconds'])
        if trade_buffer:
            trades_to_save = trade_buffer.copy(); trade_buffer.clear()
            try:
                if not CONFIG['silent_mode']: print_log(f"Chuẩn bị ghi {len(trades_to_save)} giao dịch từ buffer vào file...")
                df_to_save = pd.DataFrame(trades_to_save)
                df_to_save['p'] = pd.to_numeric(df_to_save['p']); df_to_save['q'] = pd.to_numeric(df_to_save['q'])
                df_to_save.to_parquet(CONFIG['parquet_file'], engine='fastparquet', append=True)
                if not CONFIG['silent_mode']: print_log(f"Ghi thành công!")
            except Exception as e: print_log(f"!!! Lỗi nghiêm trọng khi ghi buffer vào file: {e}")

# --- Hàm MAIN (Tổng hành dinh) (Đã sửa) ---
async def main():
    # <<<< BƯỚC 1: Tải lịch sử trades (Không cần lấy tick_size nữa) >>>>
    await manage_history()
    try:
        df = pd.read_parquet(CONFIG['parquet_file'])
        if not df.empty:
            df = df.sort_values(by='T', ascending=False).head(100)
            global last_100_trades
            last_100_trades = df.to_dict('records'); last_100_trades.reverse()
            print_log(f"Đã tải {len(last_100_trades)} giao dịch cuối cùng để khởi tạo.")
    except Exception as e: print_log(f"Không tải được dữ liệu khởi tạo từ file: {e}")

    # BƯỚC 2: Khởi động các dịch vụ
    binance_client = await AsyncClient.create()
    try:
        server_task = websockets.serve(register_client, CONFIG['server_host'], CONFIG['server_port'])
        trade_stream_task = start_trade_stream(binance_client)
        depth_stream_task = start_depth_stream(binance_client)
        saver_task = save_buffer_periodically()
        
        print_log("="*50)
        print_log("HỆ THỐNG ĐÃ ONLINE (Gửi Trades + Raw Liquidity)")
        print_log(f"Đang bắn data tới: ws://{CONFIG['server_host']}:{CONFIG['server_port']}")
        print_log("="*50)

        await asyncio.gather(server_task, trade_stream_task, depth_stream_task, saver_task)
    finally:
        print_log("Đang đóng kết nối tới Binance..."); await binance_client.close_connection(); save_buffer_on_exit()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_log("\nĐã nhận lệnh dừng từ Đại ca. Đang dọn dẹp...")