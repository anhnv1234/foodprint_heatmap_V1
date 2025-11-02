# -*- coding: utf-8 -*-
# FILE: frontend_ui.py
# Chứa toàn bộ logic Giao diện (PySide6)

# --- Imports từ app.py ---
import sys
import json
import os
import importlib.util
from collections import deque, defaultdict
from datetime import datetime, timezone 
import inspect
import math

# --- Imports từ PySide6 (app.py) ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QCheckBox, QButtonGroup, QGridLayout,
    QSplitter, QDialog, QColorDialog, QFontDialog, QFormLayout, QSpinBox,
    QMenuBar, QFileDialog, QSizePolicy, QDoubleSpinBox
)
from PySide6.QtCore import (
    Qt, QUrl, QTimer, Slot, QRectF, QSize, Signal, QPoint, QObject, QThread, QPointF
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QFontMetrics, QAction
)
from PySide6.QtWebSockets import QWebSocket

# --- Imports Constants từ backend_processor (Định nghĩa lại các hằng số cần thiết) ---
SERVER_HOST = "localhost"
SERVER_PORT = 8766
DEFAULT_PRICE_GROUPING = {'1M':5, '5M':15, '15M':25, '1H':35, '4H':100, '1D':250}
TIMEFRAMES_PANDAS = { '1M': '1min', '5M': '5min', '15M': '15min', '1H': '1h', '4H': '4h', '1D': '1D' }

TIMEFRAME_MS = {
    '1M': 60 * 1000,
    '5M': 5 * 60 * 1000,
    '15M': 15 * 60 * 1000,
    '1H': 60 * 60 * 1000,
    '4H': 4 * 60 * 60 * 1000,
    '1D': 24 * 60 * 60 * 1000
}

HEATMAP_FADE_DURATION_MS = 15 * 60 * 1000 # 15 phút
HEATMAP_REFRESH_RATE_MS = 50 # 50ms (20 FPS)
# ---------------------------------------------------------------------------------

# ==============================================================================
# Lớp CÀI ĐẶT GIAO DIỆN (SETTINGS)
# ==============================================================================
class AppSettings:
    def __init__(self):
        self.BG_COLOR = QColor("#0e1116")
        self.TEXT_COLOR = QColor("#cbd5e1")
        self.GRID_COLOR = QColor("#1f2937")
        self.BULL_COLOR = QColor("#34d399")
        self.BEAR_COLOR = QColor("#f87171")
        self.WICK_COLOR = QColor("#334155") 
        self.POC_HIGHLIGHT_COLOR = QColor("#eab308")
        self.DELTA_POS_COLOR = QColor(52, 211, 153, 128)
        self.DELTA_NEG_COLOR = QColor(248, 113, 113, 128)
        self.LAST_PRICE_LINE_COLOR = QColor(203, 213, 225, 200)
        self.CROSSHAIR_LINE_COLOR = QColor(203, 213, 225, 200)
        self.CROSSHAIR_LABEL_BG_COLOR = QColor("#1f2937") 
        self.CROSSHAIR_LABEL_TEXT_COLOR = QColor("#cbd5e1") 
        self.VP_BAR_COLOR = QColor(51, 65, 85, 80)
        self.VWAP_COLOR = QColor("#FFFFFF") 

        # Cài đặt Heatmap Thanh Khoản
        self.LIQ_COLOR_LOW = QColor("#FFFF00")  # Vàng
        self.LIQ_COLOR_HIGH = QColor("#FF0000") # Đỏ
        self.LIQ_ALPHA_MIN = 0.1  # 10%
        self.LIQ_ALPHA_MAX = 1.0  # 100%
        self.SHOW_LIQ_TEXT = True
        self.LIQ_PRICE_GROUPING = 10 
        self.LIQ_TEXT_COLOR = QColor("#FFFFFF") 
        
        # Cài đặt Current Order Block (COB)
        self.SHOW_COB_PANE = True
        self.COB_BID_COLOR = QColor(150, 0, 0, 128) # Đỏ (Giống Bookmap Bids - Bên Phải)
        self.COB_ASK_COLOR = QColor(0, 150, 0, 128) # Xanh (Giống Bookmap Asks - Bên Trái)
        self.COB_TEXT_COLOR = QColor("#FFFFFF")
        
        self.MAIN_FONT = QFont("Roboto Mono", 8)
        
        self.SHOW_CANDLE_BODY = True
        self.SHOW_CANDLE_WICK = True
        self.SHOW_CANDLE_PROFILE = True
        self.SHOW_INFO_PANE = True 
        self.SHOW_VPVR_PANE = True
        self.SHOW_PANE_3 = True 
        
        self.MIN_LIQUIDITY_TO_SHOW = 0.1 
        
        self.MAX_CANDLES_TO_LOAD_1M = 60
        self.MAX_CANDLES_TO_LOAD_5M = 200
        self.MAX_CANDLES_TO_LOAD_DEFAULT = 200
        
        self.timeframe = '5M'
        self.PRICE_GROUPING = DEFAULT_PRICE_GROUPING.copy()
    
    def get_max_candles(self, timeframe):
        if timeframe == '1M': return self.MAX_CANDLES_TO_LOAD_1M
        elif timeframe == '5M': return self.MAX_CANDLES_TO_LOAD_5M
        else: return self.MAX_CANDLES_TO_LOAD_DEFAULT

# ==============================================================================
# Lớp HỘP THOẠI CÀI ĐẶT
# ==============================================================================
class SettingsDialog(QDialog):
    settingsApplied = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt giao diện")
        self.settings = settings
        
        self.main_layout = QVBoxLayout(self)
        self.content_layout = QHBoxLayout()
        self.main_layout.addLayout(self.content_layout)
        
        left_column_widget = QWidget()
        left_layout = QFormLayout(left_column_widget)
        self.content_layout.addWidget(left_column_widget)
        
        right_column_widget = QWidget()
        right_layout = QFormLayout(right_column_widget)
        self.content_layout.addWidget(right_column_widget)
        
        # === CỘT TRÁI ===
        left_layout.addRow(QLabel("--- Cài đặt Nhóm Giá (Price Grouping) ---"))
        self.grouping_spinboxes = {} 
        for tf in ['1M', '5M', '15M', '1H', '4H', '1D']:
            current_val = self.settings.PRICE_GROUPING.get(tf, 10)
            self.add_spinbox_setting(left_layout, f"Grouping {tf}:", tf, current_val)
        
        left_layout.addRow(QLabel("--- Cài đặt Hiển Thị & Lịch Sử ---"))
        
        self.double_spinboxes = {} 
        self.add_double_spinbox_setting(
            left_layout,
            "Lọc thanh khoản nhỏ (BTC):", 
            "MIN_LIQUIDITY_TO_SHOW", 
            self.settings.MIN_LIQUIDITY_TO_SHOW,
            0.1,
            0.0, 10000.0 # Range min/max
        )
        
        self.generic_spinboxes = {} 
        self.add_generic_spinbox_setting(left_layout, "Số nến (1 Phút):", "MAX_CANDLES_TO_LOAD_1M", self.settings.MAX_CANDLES_TO_LOAD_1M)
        self.add_generic_spinbox_setting(left_layout, "Số nến (5 Phút):", "MAX_CANDLES_TO_LOAD_5M", self.settings.MAX_CANDLES_TO_LOAD_5M)

        self.add_checkbox_setting(left_layout, "Hiển thị Info Pane (Dưới đáy)", "SHOW_INFO_PANE")
        self.add_checkbox_setting(left_layout, "Hiển thị Nhãn Info (Bên phải)", "SHOW_PANE_3") 
        self.add_checkbox_setting(left_layout, "Hiển thị Volume Profile (VPVR)", "SHOW_VPVR_PANE")
        self.add_checkbox_setting(left_layout, "Hiển thị Current Order Block (COB)", "SHOW_COB_PANE")
        self.add_checkbox_setting(left_layout, "Hiển thị Thân nến", "SHOW_CANDLE_BODY")
        self.add_checkbox_setting(left_layout, "Hiển thị Râu nến", "SHOW_CANDLE_WICK")
        self.add_checkbox_setting(left_layout, "Hiển thị Profile trong nến", "SHOW_CANDLE_PROFILE")
        
        # === CỘT PHẢI ===
        right_layout.addRow(QLabel("--- Cài đặt Heatmap Thanh Khoản ---"))
        self.add_color_setting(right_layout, "Màu thanh khoản (Thấp)", "LIQ_COLOR_LOW")
        self.add_color_setting(right_layout, "Màu thanh khoản (Cao)", "LIQ_COLOR_HIGH")
        self.add_double_spinbox_setting(right_layout, "Độ mờ (Thấp)", "LIQ_ALPHA_MIN", self.settings.LIQ_ALPHA_MIN, 0.1, 0.0, 1.0)
        self.add_double_spinbox_setting(right_layout, "Độ mờ (Cao)", "LIQ_ALPHA_MAX", self.settings.LIQ_ALPHA_MAX, 0.1, 0.0, 1.0)
        self.add_checkbox_setting(right_layout, "Hiển thị số Hợp đồng", "SHOW_LIQ_TEXT")
        self.add_color_setting(right_layout, "Màu chữ Hợp đồng", "LIQ_TEXT_COLOR") 
        
        self.liq_grouping_spinbox = QSpinBox()
        self.liq_grouping_spinbox.setRange(1, 2000); self.liq_grouping_spinbox.setSingleStep(1)
        self.liq_grouping_spinbox.setValue(self.settings.LIQ_PRICE_GROUPING)
        right_layout.addRow("Gộp giá thanh khoản (Ticks):", self.liq_grouping_spinbox)

        right_layout.addRow(QLabel("--- Cài đặt Current Order Block (COB) ---"))
        self.add_color_setting(right_layout, "Màu COB (Bid - Đỏ)", "COB_BID_COLOR")
        self.add_color_setting(right_layout, "Màu COB (Ask - Xanh)", "COB_ASK_COLOR")
        self.add_color_setting(right_layout, "Màu chữ COB", "COB_TEXT_COLOR")

        right_layout.addRow(QLabel("--- Cài đặt Màu Sắc Chung ---"))
        self.add_color_setting(right_layout, "Màu nền", "BG_COLOR")
        self.add_color_setting(right_layout, "Màu chữ", "TEXT_COLOR")
        self.add_color_setting(right_layout, "Nến tăng", "BULL_COLOR")
        self.add_color_setting(right_layout, "Nến giảm", "BEAR_COLOR")
        self.add_color_setting(right_layout, "Râu nến", "WICK_COLOR")
        self.add_color_setting(right_layout, "Màu POC", "POC_HIGHLIGHT_COLOR")
        self.add_color_setting(right_layout, "Màu VWAP", "VWAP_COLOR") 
        
        self.font_button = QPushButton(f"{self.settings.MAIN_FONT.family()}, {self.settings.MAIN_FONT.pointSize()}pt")
        self.font_button.clicked.connect(self.open_font_dialog)
        right_layout.addRow("Font chữ chính:", self.font_button)
        
        # === NÚT BẤM ===
        self.button_box = QHBoxLayout()
        apply_btn = QPushButton("Áp dụng"); apply_btn.clicked.connect(self.apply_and_close)
        cancel_btn = QPushButton("Hủy"); cancel_btn.clicked.connect(self.reject)
        self.button_box.addStretch(); self.button_box.addWidget(apply_btn); self.button_box.addWidget(cancel_btn)
        self.main_layout.addLayout(self.button_box)

    def add_spinbox_setting(self, layout, label, tf_key, value):
        spinbox = QSpinBox()
        spinbox.setRange(1, 2000); spinbox.setSingleStep(5); spinbox.setValue(value)
        layout.addRow(label, spinbox)
        self.grouping_spinboxes[tf_key] = spinbox 

    def add_double_spinbox_setting(self, layout, label, setting_name, value, step, min_val=0.0, max_val=10000.0):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val); 
        spinbox.setSingleStep(step); 
        spinbox.setDecimals(2); 
        spinbox.setValue(value)
        layout.addRow(label, spinbox)
        self.double_spinboxes[setting_name] = spinbox 

    def add_generic_spinbox_setting(self, layout, label, setting_name, value):
        spinbox = QSpinBox()
        spinbox.setRange(10, 5000); spinbox.setSingleStep(10); spinbox.setValue(value)
        layout.addRow(label, spinbox)
        self.generic_spinboxes[setting_name] = spinbox

    def add_checkbox_setting(self, layout, label, setting_name):
        checkbox = QCheckBox(); checkbox.setChecked(getattr(self.settings, setting_name))
        checkbox.stateChanged.connect(lambda state, name=setting_name: setattr(self.settings, name, state == Qt.Checked))
        layout.addRow(label, checkbox)
        
    def add_color_setting(self, layout, label, setting_name):
        color = getattr(self.settings, setting_name); btn = QPushButton()
        btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #52525b;")
        btn.clicked.connect(lambda: self.open_color_dialog(setting_name, btn)); 
        layout.addRow(label, btn)
        
    def open_color_dialog(self, setting_name, button):
        color = QColorDialog.getColor(getattr(self.settings, setting_name), self, "Chọn màu")
        if color.isValid(): setattr(self.settings, setting_name, color); button.setStyleSheet(f"background-color: {color.name()};")
        
    def open_font_dialog(self):
        ok, font = QFontDialog.getFont(self.settings.MAIN_FONT, self)
        if ok: self.settings.MAIN_FONT = font; self.font_button.setText(f"{font.family()}, {font.pointSize()}pt")
    
    def apply_and_close(self): 
        for tf_key, spinbox in self.grouping_spinboxes.items():
            self.settings.PRICE_GROUPING[tf_key] = spinbox.value()
        for setting_name, spinbox in self.double_spinboxes.items():
            setattr(self.settings, setting_name, spinbox.value())
        for setting_name, spinbox in self.generic_spinboxes.items():
            setattr(self.settings, setting_name, spinbox.value())
        
        self.settings.LIQ_PRICE_GROUPING = self.liq_grouping_spinbox.value()

        self.settingsApplied.emit(); 
        self.accept()

# ==============================================================================
# HỆ THỐNG INDICATOR (Giữ nguyên)
# ==============================================================================
class BaseIndicator:
    def __init__(self, settings, name="Indicator", period=20): 
        self.name=name; self.period=period; self.settings=settings; self.data=[]
    def calculate(self, chart_data): 
        raise NotImplementedError
    def paint(self, painter, price_y_map, start_x_map, eff_candle_width, eff_pl_height): 
        raise NotImplementedError
        
    def get_y_for_price(self, price, price_y_map, eff_pl_height):
        if not price_y_map: 
            return -1
        try:
            min_map_p = min(price_y_map.keys())
            max_map_p = max(price_y_map.keys())
        except ValueError:
            return -1 
        if max_map_p == min_map_p:
             return price_y_map[min_map_p] 
        min_y = price_y_map[max_map_p] 
        max_y = price_y_map[min_map_p]
        total_p_range = max_map_p - min_map_p
        total_y_range = max_y - min_y
        if price >= max_map_p: return min_y
        if price <= min_map_p: return max_y
        p_ratio = (max_map_p - price) / total_p_range 
        y_pos = min_y + (p_ratio * total_y_range)
        return y_pos + (eff_pl_height / 2) 

class VWAPIndicator(BaseIndicator):
    def __init__(self, settings):
        super().__init__(settings, name="VWAP (Moving)", period=0) 
        self.vwap_color = settings.VWAP_COLOR
    def calculate(self, chart_data):
        self.data = []
        cumulative_pv = 0.0 
        cumulative_v = 0.0  
        for i, candle in enumerate(chart_data):
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('totalVolume', 0)
            if volume == 0:
                if self.data:
                    last_vwap = self.data[-1]['vwap']
                    self.data.append({'index': i, 'timestamp': candle.get('timestamp'), 'vwap': last_vwap})
                else:
                    self.data.append({'index': i, 'timestamp': candle.get('timestamp'), 'vwap': close})
                continue
            typical_price = (high + low + close) / 3.0
            cumulative_pv += typical_price * volume
            cumulative_v += volume
            vwap_value = cumulative_pv / cumulative_v if cumulative_v > 0 else typical_price
            self.data.append({'index': i, 'timestamp': candle.get('timestamp'), 'vwap': vwap_value})
    def paint(self, painter, price_y_map, start_x_map, eff_candle_width, eff_pl_height):
        if len(self.data) < 2:
            return 
        self.vwap_color = self.settings.VWAP_COLOR 
        pen = QPen(self.vwap_color, 1, Qt.SolidLine)
        painter.setPen(pen)
        for i in range(1, len(self.data)):
            point_a = self.data[i-1]
            point_b = self.data[i]
            if point_a['index'] not in start_x_map or point_b['index'] not in start_x_map:
                continue
            x1 = start_x_map[point_a['index']] + (eff_candle_width / 2)
            x2 = start_x_map[point_b['index']] + (eff_candle_width / 2)
            y1 = self.get_y_for_price(point_a['vwap'], price_y_map, eff_pl_height)
            y2 = self.get_y_for_price(point_b['vwap'], price_y_map, eff_pl_height)
            if y1 > 0 and y2 > 0:
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

class IndicatorPanel(QWidget):
    indicatorVisibilityChanged = Signal(int, bool)
    indicatorSettingsRequested = Signal(int)
    indicatorRemoved = Signal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(5, 5, 5, 5); self.layout().setSpacing(4); self.layout().setAlignment(Qt.AlignTop)
        self.setStyleSheet(f"IndicatorPanel {{ background-color: rgba(30, 30, 30, 180); border-radius: 6px; border: 1px solid #334155; }}")
        self.indicator_widgets = []
    def update_indicators(self, indicators_list):
        for widget in self.indicator_widgets: widget.deleteLater()
        self.indicator_widgets.clear()
        for idx, indicator_info in enumerate(indicators_list):
            indicator = indicator_info['instance']; is_visible = indicator_info['visible']
            row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 0, 0, 0); row_layout.setSpacing(5)
            name_label = QLabel(indicator.name); name_label.setStyleSheet("background-color: transparent; border: none;")
            vis_button = QPushButton("👁️"); vis_button.setCheckable(True); vis_button.setChecked(is_visible); vis_button.setToolTip("Ẩn/Hiện Indicator"); vis_button.setFixedSize(24, 24); vis_button.setStyleSheet("background-color: transparent; border: none; font-size: 14px;"); vis_button.toggled.connect(lambda checked, i=idx: self.indicatorVisibilityChanged.emit(i, checked))
            settings_button = QPushButton("⚙️"); settings_button.setToolTip("Cài đặt Indicator (chưa có)"); settings_button.setFixedSize(24, 24); settings_button.setStyleSheet("background-color: transparent; border: none; font-size: 14px;"); settings_button.clicked.connect(lambda _, i=idx: self.indicatorSettingsRequested.emit(i))
            remove_button = QPushButton("🗑️"); remove_button.setToolTip("Xóa Indicator"); remove_button.setFixedSize(24, 24); remove_button.setStyleSheet("background-color: transparent; border: none; font-size: 14px;"); remove_button.clicked.connect(lambda _, i=idx: self.indicatorRemoved.emit(i))
            row_layout.addWidget(name_label); row_layout.addStretch(); row_layout.addWidget(vis_button); row_layout.addWidget(settings_button); row_layout.addWidget(remove_button)
            self.layout().addWidget(row); self.indicator_widgets.append(row)
        self.adjustSize(); self.setVisible(len(self.indicator_widgets) > 0)

# ==============================================================================
# CÁC WIDGET THÀNH PHẦN (Giữ nguyên)
# ==============================================================================

class PriceAxisWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.settings=settings; self.setMinimumWidth(60)
        self.price_scale, self.crosshair_y, self.last_price = [], -1, 0
        self.price_level_height, self.y_zoom = 14, 1.0; self.timeframe = '5M'
        self.last_price_label_bg_color = QColor(59, 130, 246, 150) 
    def effective_price_level_height(self): return self.price_level_height * self.y_zoom
    def update_data(self, params):
        self.price_scale=params["price_scale"]; self.price_level_height=params["price_level_height"]
        self.y_zoom=params["y_zoom"]; self.last_price=params.get("last_price",0); self.timeframe=params.get("timeframe","5M")
        self.settings.timeframe = self.timeframe
        chart_height = len(self.price_scale) * (self.effective_price_level_height() + 2)
        self.setFixedHeight(chart_height if chart_height > 0 else 300); self.update()
    def set_crosshair_y(self, y): self.crosshair_y = y; self.update()
    def paintEvent(self, event):
        painter=QPainter(self); painter.fillRect(self.rect(), self.settings.BG_COLOR); painter.setFont(self.settings.MAIN_FONT)
        if not self.price_scale: painter.end(); return
        eff_height=self.effective_price_level_height()
        group_by=self.settings.PRICE_GROUPING.get(self.timeframe, 1) 
        if group_by <= 0: group_by = 1 
        total_row_height = eff_height + 2
        last_price_bucket = -1
        if self.last_price > 0: last_price_bucket = int(self.last_price / group_by) * group_by
        for i, price in enumerate(self.price_scale):
            y_pos = i * total_row_height; text_rect = QRectF(0, y_pos, self.width() - 5, eff_height)
            if price == last_price_bucket:
                highlight_rect = QRectF(0, y_pos, self.width(), total_row_height)
                painter.fillRect(highlight_rect, self.last_price_label_bg_color); painter.setPen(self.settings.TEXT_COLOR) 
            else: painter.setPen(self.settings.TEXT_COLOR)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, f"{price:.0f}")
        if self.crosshair_y > 0:
            index = int(self.crosshair_y / total_row_height)
            if 0 <= index < len(self.price_scale):
                price = self.price_scale[index]; y_pos = index * total_row_height; label_rect = QRectF(0, y_pos, self.width() - 1, eff_height)
                painter.fillRect(label_rect, self.settings.CROSSHAIR_LABEL_BG_COLOR); painter.setPen(self.settings.CROSSHAIR_LABEL_TEXT_COLOR)
                painter.drawText(label_rect, Qt.AlignCenter, f"{price:.0f}")
        painter.end()

class VolumeProfileAxisWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.settings = settings; self.setMinimumWidth(80)
        self.price_scale, self.volume_profile = [], {}; self.price_level_height, self.y_zoom, self.timeframe = 14, 1.0, '5M'
    def effective_price_level_height(self): return self.price_level_height * self.y_zoom
    def update_data(self, params):
        self.price_scale=params.get("price_scale",[]); self.volume_profile=params.get("total_volume_profile",{})
        self.price_level_height=params.get("price_level_height",14); self.y_zoom=params.get("y_zoom",1.0); self.timeframe=params.get("timeframe","5M")
        chart_height = len(self.price_scale) * (self.effective_price_level_height()+2); self.setFixedHeight(chart_height if chart_height>0 else 300); self.update()
    def paintEvent(self, event):
        painter=QPainter(self); painter.fillRect(self.rect(),self.settings.BG_COLOR); painter.setFont(self.settings.MAIN_FONT)
        if not self.price_scale or not self.volume_profile: painter.end(); return
        eff_height=self.effective_price_level_height(); volumes=self.volume_profile.values(); max_volume=max(volumes) if volumes else 0
        poc_price = max(self.volume_profile, key=self.volume_profile.get) if self.volume_profile else -1
        if max_volume<=0: painter.end(); return
        for i, price in enumerate(self.price_scale):
            y_pos = i*(eff_height+2); volume_at_price = self.volume_profile.get(price, 0)
            if volume_at_price > 0:
                bar_width=(volume_at_price/max_volume)*self.width(); bar_rect=QRectF(self.width()-bar_width,y_pos,bar_width,eff_height)
                painter.fillRect(bar_rect, self.settings.VP_BAR_COLOR) 
                if price == poc_price: painter.setPen(QPen(self.settings.POC_HIGHLIGHT_COLOR,1)); painter.drawRect(bar_rect); painter.setPen(Qt.NoPen)
        painter.end()

# <<<< SỬA: Logic co giãn COB (Yêu cầu mới) >>>>
class CurrentOrderBlockWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setMinimumWidth(80)
        self.unfiltered_live_order_book = {'bid': {}, 'ask': {}}
        # Xóa max_live_bid và max_live_ask (sẽ tính động)
        self.price_scale = []
        self.price_level_height = 14
        self.y_zoom = 1.0
        self.timeframe = '5M'

    def effective_price_level_height(self): 
        return self.price_level_height * self.y_zoom

    @Slot(dict, float)
    def on_live_liquidity_updated(self, unfiltered_live_data, max_liq_ignored):
        """Nhận dữ liệu live book UNFILTERED từ chart chính."""
        self.unfiltered_live_order_book = unfiltered_live_data
        # Không cần tính max_live_bid/ask ở đây nữa
        self.update() # Chỉ cần yêu cầu vẽ lại

    def update_data(self, params):
        """Đồng bộ trục Y với chart chính."""
        self.price_scale = params.get("price_scale", [])
        self.price_level_height = params.get("price_level_height", 14)
        self.y_zoom = params.get("y_zoom", 1.0)
        self.timeframe = params.get("timeframe", "5M")
        chart_height = len(self.price_scale) * (self.effective_price_level_height() + 2)
        self.setFixedHeight(chart_height if chart_height > 0 else 300)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.settings.BG_COLOR)
        painter.setFont(self.settings.MAIN_FONT)
        
        if not self.price_scale or not self.unfiltered_live_order_book:
            painter.end()
            return

        eff_height = self.effective_price_level_height()
        half_width = self.width() / 2.0
        
        bid_color = self.settings.COB_BID_COLOR # -> Đỏ
        ask_color = self.settings.COB_ASK_COLOR # -> Xanh
        text_color = self.settings.COB_TEXT_COLOR
        
        price_group_by = self.settings.PRICE_GROUPING.get(self.timeframe, 1)
        if price_group_by <= 0: price_group_by = 1
        
        # --- BẮT ĐẦU LOGIC SỬA ---
        
        # 1. Gộp toàn bộ thanh khoản (như cũ)
        agg_bids = defaultdict(float)
        agg_asks = defaultdict(float)

        for p_live, (qty, ts) in self.unfiltered_live_order_book['bid'].items():
            p_bucket = int(p_live / price_group_by) * price_group_by
            agg_bids[p_bucket] += qty
            
        for p_live, (qty, ts) in self.unfiltered_live_order_book['ask'].items():
            p_bucket = int(p_live / price_group_by) * price_group_by
            agg_asks[p_bucket] += qty

        # 2. Tìm max CHỈ TRONG PHẠM VI HIỂN THỊ (Yêu cầu mới)
        visible_bids_qty = []
        visible_asks_qty = []
        visible_price_set = set(self.price_scale)

        for price, qty in agg_bids.items():
            if price in visible_price_set:
                visible_bids_qty.append(qty)
        
        for price, qty in agg_asks.items():
            if price in visible_price_set:
                visible_asks_qty.append(qty)

        max_bid_visible = max(visible_bids_qty) if visible_bids_qty else 1.0
        max_ask_visible = max(visible_asks_qty) if visible_asks_qty else 1.0
        
        if max_bid_visible == 0: max_bid_visible = 1.0
        if max_ask_visible == 0: max_ask_visible = 1.0

        # --- KẾT THÚC LOGIC SỬA ---

        # 3. Vẽ, sử dụng max_visible (Yêu cầu mới)
        for i, price in enumerate(self.price_scale):
            y_pos = i * (eff_height + 2)
            
            # Vẽ Asks (Xanh) bên TRÁI
            qty_ask = agg_asks.get(price, 0)
            if qty_ask > 0:
                bar_width = (qty_ask / max_ask_visible) * half_width # Sửa: dùng max_ask_visible
                bar_rect = QRectF(0, y_pos, bar_width, eff_height) 
                painter.fillRect(bar_rect, ask_color) 
                painter.setPen(text_color)
                text_rect = QRectF(0 + 2, y_pos, half_width - 2, eff_height) 
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, f" {qty_ask:.1f}")

            # Vẽ Bids (Đỏ) bên PHẢI
            qty_bid = agg_bids.get(price, 0)
            if qty_bid > 0:
                bar_width = (qty_bid / max_bid_visible) * half_width # Sửa: dùng max_bid_visible
                bar_rect = QRectF(self.width() - bar_width, y_pos, bar_width, eff_height) 
                painter.fillRect(bar_rect, bid_color)
                painter.setPen(text_color)
                text_rect = QRectF(half_width, y_pos, half_width - 2, eff_height) 
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, f"{qty_bid:.1f} ")
                
        painter.end()
# <<<< KẾT THÚC SỬA COB >>>>

class InfoLabelsWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.settings=settings
        self.header_width, self.row_height = 120, 20
        self.labels = ["Total Vol", "Delta", "Max Delta", "Min Delta", "Cum Delta", "Bid Vol", "Ask Vol"]
        self.setFixedWidth(self.header_width); self.setFixedHeight(len(self.labels) * self.row_height + 1)
    def paintEvent(self, event):
        painter=QPainter(self); painter.fillRect(self.rect(), self.settings.BG_COLOR); painter.setFont(self.settings.MAIN_FONT)
        painter.setPen(self.settings.GRID_COLOR)
        for i in range(len(self.labels) + 1): y=i*self.row_height; painter.drawLine(0,y,self.width(),y)
        painter.setPen(self.settings.TEXT_COLOR)
        for i, label in enumerate(self.labels): painter.drawText(QRectF(5,i*self.row_height,self.width()-10,self.row_height),Qt.AlignVCenter|Qt.AlignRight,label)

class DetailedInfoDataWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.settings=settings; self.chart_data=[]; self.cum_deltas=[]
        self.candle_total_width, self.candle_gap, self.x_zoom=0,0,1.0; self.crosshair_x=-1; self.row_height=20; 
        self.highlight_color=QColor(self.settings.GRID_COLOR.name()); self.highlight_color.setAlpha(100) 
        self.pos_color = self.settings.BULL_COLOR; self.neg_color = self.settings.BEAR_COLOR
        self.num_rows = 7; self.setFixedHeight(self.num_rows * self.row_height + 1)
        self.delta_labels_check = ["Delta", "Max Delta", "Min Delta", "Cum Delta"]
    def effective_candle_total_width(self): return self.candle_total_width*self.x_zoom
    def effective_candle_gap(self): return self.candle_gap*self.x_zoom
    def update_data(self, params):
        self.chart_data=params["chart_data"]; self.candle_total_width=params["candle_total_width"]; self.candle_gap=params["candle_gap"]; self.x_zoom=params["x_zoom"]
        self.cum_deltas=[]; current_cum_delta=0
        for candle in self.chart_data:
            ask_vol=sum(a for p,b,a in candle.get('levels',[])); bid_vol=sum(b for p,b,a in candle.get('levels',[]))
            current_cum_delta+=(ask_vol-bid_vol); self.cum_deltas.append(current_cum_delta)
        eff_total_width, eff_gap=self.effective_candle_total_width(),self.effective_candle_gap()
        extra_space = self.parent().width()*0.2 if self.parent() else 200
        total_width=len(self.chart_data)*eff_total_width+(len(self.chart_data)-1)*eff_gap if self.chart_data else 0
        self.setFixedWidth(total_width+extra_space if total_width>0 else 0); self.update()
    def set_crosshair_x(self, x): self.crosshair_x=x; self.update()
    def paintEvent(self, event):
        painter=QPainter(self); painter.fillRect(self.rect(), self.settings.BG_COLOR); painter.setFont(self.settings.MAIN_FONT)
        if not self.chart_data: painter.end(); return
        eff_total_width, eff_gap=self.effective_candle_total_width(),self.effective_candle_gap(); painter.setPen(self.settings.GRID_COLOR)
        for i in range(self.num_rows + 1):
            y=i*self.row_height; painter.drawLine(0,y,self.width(),y)
        if self.crosshair_x>0:
            index = int(self.crosshair_x/(eff_total_width+eff_gap))
            if 0<=index<len(self.chart_data): painter.fillRect(QRectF(index*(eff_total_width+eff_gap),0,eff_total_width,self.height()),self.highlight_color)
        current_x=0
        for i, candle in enumerate(self.chart_data):
            ask_vol=sum(a for p,b,a in candle.get('levels',[])); bid_vol=sum(b for p,b,a in candle.get('levels',[])); total_vol=ask_vol+bid_vol; delta=ask_vol-bid_vol
            level_deltas=[a-b for p,b,a in candle.get('levels',[])]; max_delta=max(level_deltas) if level_deltas else 0; min_delta=min(level_deltas) if level_deltas else 0
            cum_delta=self.cum_deltas[i]; 
            painter.setPen(self.settings.GRID_COLOR); painter.drawLine(int(current_x), 0, int(current_x), self.height())
            data_points=[f"{v:.1f}" for v in [total_vol,delta,max_delta,min_delta,cum_delta,bid_vol,ask_vol]]
            label_names = ["Total Vol", "Delta", "Max Delta", "Min Delta", "Cum Delta", "Bid Vol", "Ask Vol"]
            for j, data_str in enumerate(data_points):
                rect=QRectF(current_x,j*self.row_height,eff_total_width,self.row_height)
                if "Delta" in label_names[j]:
                    value=float(data_str)
                    if value>0: painter.setPen(self.pos_color)
                    elif value<0: painter.setPen(self.neg_color)
                    else: painter.setPen(self.settings.TEXT_COLOR)
                else: painter.setPen(self.settings.TEXT_COLOR)
                painter.drawText(rect,Qt.AlignCenter,data_str)
            current_x+=eff_total_width+eff_gap
        painter.end()

# ==============================================================================
# BỘ XỬ LÝ DỮ LIỆU (Worker) (Giữ nguyên)
# ==============================================================================
class DataProcessor(QObject):
    dataReady = Signal(dict)
    
    @Slot(list, str, dict, float)
    def process_data(self, chart_data_list, timeframe, price_grouping, last_price):
        group_by = price_grouping.get(timeframe, 1)
        if group_by <= 0: group_by = 1 
        
        if not chart_data_list: 
            if last_price > 0:
                expanded_min_p = last_price - 3000
                expanded_max_p = last_price + 3000
                min_bucket, max_bucket = int(expanded_min_p / group_by) * group_by, int(expanded_max_p / group_by) * group_by
                aggregated_price_scale = [p for p in range(max_bucket, min_bucket - 1, -group_by)]
                self.dataReady.emit({"aggregated_price_scale": aggregated_price_scale, "aggregated_chart_data": [], "total_volume_profile": {}, "detailed_volume_profile": {}})
                return
            else:
                self.dataReady.emit({}); return

        all_prices = set()
        for c in chart_data_list:
            all_prices.update([c.get('open',0), c.get('high',0), c.get('low',0), c.get('close',0)])
            for p, _, _ in c.get('levels', []): all_prices.add(p)
                
        if not all_prices: 
             if last_price > 0:
                expanded_min_p = last_price - 3000
                expanded_max_p = last_price + 3000
                min_bucket, max_bucket = int(expanded_min_p / group_by) * group_by, int(expanded_max_p / group_by) * group_by
                aggregated_price_scale = [p for p in range(max_bucket, min_bucket - 1, -group_by)]
                self.dataReady.emit({"aggregated_price_scale": aggregated_price_scale, "aggregated_chart_data": [], "total_volume_profile": {}, "detailed_volume_profile": {}})
                return
             else:
                self.dataReady.emit({}); return

        min_p, max_p = min(all_prices), max(all_prices)
        
        if last_price > 0:
            expanded_min_p = last_price - 3000
            expanded_max_p = last_price + 3000
            min_p = min(min_p, expanded_min_p)
            max_p = max(max_p, expanded_max_p)
            
        min_p -= group_by
        max_p += group_by

        min_bucket, max_bucket = int(min_p / group_by) * group_by, int(max_p / group_by) * group_by
        aggregated_price_scale = [p for p in range(max_bucket, min_bucket - 1, -group_by)]
        
        aggregated_chart_data = []
        for candle in chart_data_list:
            new_levels = defaultdict(lambda: {'b': 0, 'a': 0})
            for p, b, a in candle.get('levels', []):
                new_levels[int(p / group_by) * group_by]['b'] += b; new_levels[int(p / group_by) * group_by]['a'] += a
            agg_candle = candle.copy(); agg_candle['levels'] = [[p, v['b'], v['a']] for p, v in new_levels.items()]
            
            aggregated_chart_data.append(agg_candle)
            
        new_profile = defaultdict(float)
        for candle in aggregated_chart_data:
            for p, b, a in candle.get('levels', []): new_profile[p] += (b + a)
        total_volume_profile = dict(new_profile); detailed_prof = defaultdict(float)

        for candle in chart_data_list:
            for p, b, a in candle.get('levels', []): detailed_prof[p] += (b+a)
        detailed_volume_profile = dict(detailed_prof)
        
        self.dataReady.emit({ 
            "aggregated_price_scale": aggregated_price_scale, 
            "aggregated_chart_data": aggregated_chart_data, 
            "total_volume_profile": total_volume_profile, 
            "detailed_volume_profile": detailed_volume_profile 
        })

# ==============================================================================
# BIỂU ĐỒ CHÍNH (FOOTPRINTCHARTWIDGET)
# ==============================================================================
class FootprintChartWidget(QWidget):
    crosshairMoved = Signal(QPoint)
    dataChanged = Signal()
    liveLiquidityChanged = Signal(dict, float) 
    
    def __init__(self, settings, parent_window=None, parent=None): 
        super().__init__(parent); self.settings=settings; self.setMouseTracking(True)
        self.parent_window = parent_window 
        self.crosshair_pos=QPoint(-1,-1)
        self.chart_data=deque(maxlen=self.settings.get_max_candles(self.settings.timeframe)) 
        self._aggregated_price_scale=[]; self._aggregated_chart_data=[]; self.total_volume_profile={}; self.detailed_volume_profile={}
        self.current_tf=self.settings.timeframe; self.price_level_height,self.candle_gap=14,10; self.candle_body_width,self.profile_width,self.body_profile_gap=6,60,4
        self.x_zoom,self.y_zoom=1.0,1.0; self.last_price=0
        self.last_price_highlight_color = QColor(self.settings.GRID_COLOR.name()); self.last_price_highlight_color.setAlpha(80) 
        self.setMinimumSize(400,300); self.indicators = []; self._setup_indicator_panel()
        self.historical_heatmap_data = []; self.max_historical_liq = 1.0     
        self.live_order_book = { 'bid': {}, 'ask': {} } 
        self.unfiltered_live_order_book = { 'bid': {}, 'ask': {} }
        self.max_live_liq = 1.0 
        self.fade_timer = QTimer(self); self.fade_timer.timeout.connect(self.update); self.fade_timer.start(HEATMAP_REFRESH_RATE_MS) 

    def set_historical_heatmap(self, data):
        self.historical_heatmap_data = data
        max_liq = 0
        if data:
            try: max_liq = max(point.get('total_quantity', 0) for point in data)
            except ValueError: max_liq = 0 
        self.max_historical_liq = max_liq if max_liq > 0 else 1.0; self.update() 

    @Slot(dict)
    def add_live_liquidity(self, data):
        event_time = data.get('timestamp')
        if not event_time: 
            return

        min_liq_filter = self.settings.MIN_LIQUIDITY_TO_SHOW
        
        group_by = self.settings.LIQ_PRICE_GROUPING
        if group_by <= 0: 
            group_by = 1
        
        for p_str, q_str in data.get('bids', []):
            price = float(p_str); qty = float(q_str)
            price_bucket = int(price / group_by) * group_by
            
            if qty == 0: 
                if price_bucket in self.unfiltered_live_order_book['bid']:
                    del self.unfiltered_live_order_book['bid'][price_bucket]
            else:
                self.unfiltered_live_order_book['bid'][price_bucket] = (qty, event_time)

            if qty < min_liq_filter: 
                if price_bucket in self.live_order_book['bid']: 
                    del self.live_order_book['bid'][price_bucket]
            else: 
                self.live_order_book['bid'][price_bucket] = (qty, event_time)
                
        for p_str, q_str in data.get('asks', []):
            price = float(p_str); qty = float(q_str)
            price_bucket = int(price / group_by) * group_by
            
            if qty == 0:
                if price_bucket in self.unfiltered_live_order_book['ask']:
                    del self.unfiltered_live_order_book['ask'][price_bucket]
            else:
                self.unfiltered_live_order_book['ask'][price_bucket] = (qty, event_time)
                
            if qty < min_liq_filter:
                if price_bucket in self.live_order_book['ask']: 
                    del self.live_order_book['ask'][price_bucket]
            else: 
                self.live_order_book['ask'][price_bucket] = (qty, event_time)
        
        max_liq = 0
        try: 
            max_bids = max(item[0] for item in self.live_order_book['bid'].values())
        except ValueError: 
            max_bids = 0
        try: 
            max_asks = max(item[0] for item in self.live_order_book['ask'].values())
        except ValueError: 
            max_asks = 0
        
        self.max_live_liq = max(max_bids, max_asks)
        if self.max_live_liq == 0: 
            self.max_live_liq = 1.0
        
        self.liveLiquidityChanged.emit(self.unfiltered_live_order_book, 0) 
    
    def _setup_indicator_panel(self):
        self.indicator_panel = IndicatorPanel(self)
        self.indicator_panel.indicatorVisibilityChanged.connect(self.set_indicator_visibility)
        self.indicator_panel.indicatorRemoved.connect(self.remove_indicator)
        self.indicator_panel.indicatorSettingsRequested.connect(self.open_indicator_settings)

    def add_indicator(self, indicator_instance): 
        for ind in self.indicators:
            if ind['instance'].name == indicator_instance.name:
                print(f"Indicator {indicator_instance.name} đã tồn tại.")
                return 
        self.indicators.append({'instance': indicator_instance, 'visible': True}); 
        self._recalculate_and_redraw()
        
    def remove_indicator(self, index):
        if 0 <= index < len(self.indicators): del self.indicators[index]; self._recalculate_and_redraw()
    def set_indicator_visibility(self, index, visible):
        if 0 <= index < len(self.indicators): self.indicators[index]['visible'] = visible; self.update()
    def open_indicator_settings(self, index):
        if 0 <= index < len(self.indicators): print(f"Yêu cầu cài đặt cho: {self.indicators[index]['instance'].name}")
    def clear_indicators(self): self.indicators.clear(); self._recalculate_and_redraw()
    def apply_zoom(self, delta):
        factor=1.1 if delta>0 else(1/1.1); self.x_zoom=max(0.1,min(self.x_zoom*factor,5.0)); self.y_zoom=max(0.2,min(self.y_zoom*factor,4.0)); self._recalculate_and_redraw()
    def reset_zoom(self): self.x_zoom,self.y_zoom=1.0,1.0; self._recalculate_and_redraw()
    def effective_price_level_height(self): return self.price_level_height*self.y_zoom
    def effective_candle_body_width(self): return self.candle_body_width*self.x_zoom
    def effective_profile_width(self): return self.profile_width*self.x_zoom
    def effective_candle_gap(self): return self.candle_gap*self.x_zoom
    def effective_body_profile_gap(self): return self.body_profile_gap*self.x_zoom
    def effective_candle_total_width(self): return self.effective_candle_body_width()+self.effective_body_profile_gap()+self.effective_profile_width()
    def get_render_params(self):
        return {"price_scale":self._aggregated_price_scale,"chart_data":self._aggregated_chart_data,"candle_total_width":self.candle_body_width+self.body_profile_gap+self.profile_width,"candle_gap":self.candle_gap,"price_level_height":self.price_level_height,"x_zoom":self.x_zoom,"y_zoom":self.y_zoom,"timeframe":self.current_tf,"last_price":self.last_price,"total_volume_profile":self.total_volume_profile,"detailed_volume_profile":self.detailed_volume_profile}
    
    # (Giữ nguyên) Sửa lỗi KeyError
    def _sweep_liquidity(self, candle_low, candle_high):
        if candle_low == 0 or candle_high == 0:
            return 
            
        bids_to_remove = [p for p in self.unfiltered_live_order_book['bid'] if candle_low <= p <= candle_high]
        asks_to_remove = [p for p in self.unfiltered_live_order_book['ask'] if candle_low <= p <= candle_high]
        
        did_remove = False
        for p in bids_to_remove:
            if p in self.live_order_book['bid']:
                del self.live_order_book['bid'][p] 
            if p in self.unfiltered_live_order_book['bid']:
                del self.unfiltered_live_order_book['bid'][p]; did_remove = True
                
        for p in asks_to_remove:
            if p in self.live_order_book['ask']:
                del self.live_order_book['ask'][p] 
            if p in self.unfiltered_live_order_book['ask']:
                del self.unfiltered_live_order_book['ask'][p]; did_remove = True
        
        if did_remove:
            try: max_bids = max(item[0] for item in self.live_order_book['bid'].values())
            except ValueError: max_bids = 0
            try: max_asks = max(item[0] for item in self.live_order_book['ask'].values())
            except ValueError: max_asks = 0
            self.max_live_liq = max(max_bids, max_asks)
            if self.max_live_liq == 0: self.max_live_liq = 1.0
            
            self.liveLiquidityChanged.emit(self.unfiltered_live_order_book, 0)
    
    @Slot(dict)
    def on_data_processed(self, processed_data):
        self._aggregated_price_scale=processed_data.get("aggregated_price_scale",[]); 
        self._aggregated_chart_data=processed_data.get("aggregated_chart_data",[])
        self.total_volume_profile=processed_data.get("total_volume_profile",{}); 
        self.detailed_volume_profile=processed_data.get("detailed_volume_profile",{})
        
        if self._aggregated_chart_data:
            last_candle = self._aggregated_chart_data[-1]
            raw_low = last_candle.get('low', 0)
            raw_high = last_candle.get('high', 0)
            self._sweep_liquidity(raw_low, raw_high)
        
        self._recalculate_and_redraw()
        
    def _recalculate_and_redraw(self):
        for indicator_info in self.indicators: 
            indicator_info['instance'].calculate(self.chart_data) 

        self.indicator_panel.update_indicators(self.indicators)
        if not self._aggregated_chart_data and not self._aggregated_price_scale: 
            self.setFixedSize(400,300); self.update(); self.dataChanged.emit(); return
        chart_height=len(self._aggregated_price_scale)*(self.effective_price_level_height()+2)
        extra_space=self.parent().width()*0.2 if self.parent() else 200
        total_width=len(self._aggregated_chart_data)*self.effective_candle_total_width()+(len(self._aggregated_chart_data)-1)*self.effective_candle_gap()
        self.setFixedSize(max(400,total_width+extra_space),max(300,chart_height))
        self.update(); self.dataChanged.emit()
        
    def mouseMoveEvent(self, event): 
        if event.buttons() != Qt.NoButton: event.ignore() 
        else: self.crosshair_pos=event.position().toPoint(); self.crosshairMoved.emit(self.crosshair_pos); self.update(); event.accept() 
    def leaveEvent(self, event): 
        self.crosshair_pos=QPoint(-1,-1); self.crosshairMoved.emit(self.crosshair_pos); self.update(); event.accept() 
    def resizeEvent(self, event):
        super().resizeEvent(event); self.indicator_panel.move(10, 10)

    def paintEvent(self, event):
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.fillRect(self.rect(), self.settings.BG_COLOR)
        if not self._aggregated_chart_data and not self._aggregated_price_scale:
            painter.setPen(self.settings.TEXT_COLOR); painter.drawText(self.rect(),Qt.AlignCenter,"Đang chờ dữ liệu..."); painter.end(); return
        
        painter.setFont(self.settings.MAIN_FONT)
        eff_pl_height, eff_total_width, eff_gap = self.effective_price_level_height(), self.effective_candle_total_width(), self.effective_candle_gap()
        price_y_map={p:i*(eff_pl_height+2) for i,p in enumerate(self._aggregated_price_scale)}
        
        if price_y_map:
            self._draw_liquidity_heatmap(painter, price_y_map)
            self._draw_last_price_highlight(painter, price_y_map)
            
        start_x_map={}
        
        for i, candle in enumerate(self._aggregated_chart_data):
            start_x=i*(eff_total_width+eff_gap)
            start_x_map[i]=start_x
            self._draw_candle(painter, candle, start_x, price_y_map)
        
        for indicator_info in self.indicators: 
            if indicator_info['visible']:
                indicator_info['instance'].paint(painter, price_y_map, start_x_map, eff_total_width, eff_pl_height)

        if self.crosshair_pos.x() > 0: self._draw_crosshair(painter)
            
        painter.end()


    def _draw_merged_block_helper(self, painter, block_data, price_y_map, base_color_ignored, current_time_ms, rect_x, rect_width, eff_pl_height):
        if not block_data:
            return
            
        start_price = block_data[0][0] 
        end_price = block_data[-1][0] 
        
        if start_price not in price_y_map or end_price not in price_y_map:
            return
            
        y_start = price_y_map[start_price]
        height = (price_y_map[end_price] - y_start) + eff_pl_height
        
        total_qty = sum(item[1] for item in block_data)
        avg_qty = total_qty / len(block_data) 
        avg_timestamp = sum(item[2] for item in block_data) / len(block_data)
        
        time_elapsed = current_time_ms - avg_timestamp
        fade_alpha = 1.0 - (time_elapsed / HEATMAP_FADE_DURATION_MS)
        
        qty_alpha = min(avg_qty, self.max_live_liq) / self.max_live_liq 
        
        min_alpha = self.settings.LIQ_ALPHA_MIN
        max_alpha = self.settings.LIQ_ALPHA_MAX
        base_alpha = min_alpha + qty_alpha * (max_alpha - min_alpha)
        final_alpha = int(base_alpha * fade_alpha * 255) 
        
        if final_alpha < 5: 
            return
            
        start_color = self.settings.LIQ_COLOR_LOW
        end_color = self.settings.LIQ_COLOR_HIGH
        
        r = start_color.red() + (end_color.red() - start_color.red()) * qty_alpha
        g = start_color.green() + (end_color.green() - start_color.green()) * qty_alpha
        b = start_color.blue() + (end_color.blue() - start_color.blue()) * qty_alpha
        
        color = QColor(int(r), int(g), int(b))
        color.setAlpha(final_alpha)
        
        rect = QRectF(rect_x, y_start, rect_width, height)
        painter.fillRect(rect, color)
        
        if self.settings.SHOW_LIQ_TEXT:
            text = f"{total_qty:.1f}" 
            text_rect = QRectF(rect_x, y_start, rect_width - 5, height) 
            text_color = QColor(self.settings.LIQ_TEXT_COLOR)
            text_color.setAlpha(255) 
            painter.setPen(text_color)
            original_font = painter.font()
            bold_font = QFont(original_font)
            bold_font.setBold(True)
            painter.setFont(bold_font)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, text)
            painter.setFont(original_font)
            
    def _draw_liquidity_heatmap(self, painter, price_y_map):
        if self.current_tf not in ['1M', '5M'] or not self.chart_data: 
            return
            
        min_ts = self.chart_data[0]['timestamp']
        
        eff_total_width = self.effective_candle_total_width()
        eff_gap = self.effective_candle_gap()
        candle_plus_gap = eff_total_width + eff_gap
        total_pixel_width = (len(self.chart_data) * candle_plus_gap) - eff_gap 
        
        if total_pixel_width <= 0: return

        tf_duration_ms = TIMEFRAME_MS.get(self.current_tf, 300000) 
        
        max_ts = self.chart_data[-1]['timestamp'] + tf_duration_ms
        total_duration_ms = max_ts - min_ts
        if total_duration_ms <= 0: return
            
        def time_to_x(ts):
            relative_pos = (ts - min_ts) / total_duration_ms
            return relative_pos * total_pixel_width

        eff_pl_height = self.effective_price_level_height()
        
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        is_auto_scroll_active = self.parent_window.is_auto_scroll_active 
        
        scrollbar_width = self.parent_window.chart_scroll_area.verticalScrollBar().width() if self.parent_window.chart_scroll_area.verticalScrollBar().isVisible() else 0
        chart_area_width = self.width() - scrollbar_width 

        if is_auto_scroll_active:
            live_heatmap_x = (len(self.chart_data) * candle_plus_gap) - eff_gap
        else:
            live_heatmap_x = time_to_x(current_time_ms)
        
        live_heatmap_width = chart_area_width - live_heatmap_x
        
        if live_heatmap_width <= 0: 
            return 

        group_by = self.settings.LIQ_PRICE_GROUPING
        if group_by <= 0: group_by = 1
            
        # Vẽ Live Bids (Dùng FILTERED book)
        prices_to_remove = []
        sorted_bids = sorted(self.live_order_book['bid'].items(), key=lambda item: item[0], reverse=True)
        current_block = [] 
        
        for (price, (qty, timestamp)) in sorted_bids:
            time_elapsed = current_time_ms - timestamp
            if time_elapsed > HEATMAP_FADE_DURATION_MS:
                prices_to_remove.append(price)
                continue
            if price not in price_y_map:
                continue
            if not current_block or price == current_block[-1][0] - group_by:
                current_block.append((price, qty, timestamp))
            else:
                self._draw_merged_block_helper(painter, current_block, price_y_map, None, current_time_ms, live_heatmap_x, live_heatmap_width, eff_pl_height)
                current_block = [(price, qty, timestamp)]
        if current_block:
            self._draw_merged_block_helper(painter, current_block, price_y_map, None, current_time_ms, live_heatmap_x, live_heatmap_width, eff_pl_height)
        for price in prices_to_remove: 
            if price in self.live_order_book['bid']:
                del self.live_order_book['bid'][price]

        # Vẽ Live Asks (Dùng FILTERED book)
        prices_to_remove = []
        sorted_asks = sorted(self.live_order_book['ask'].items(), key=lambda item: item[0], reverse=True)
        current_block = [] 
        for (price, (qty, timestamp)) in sorted_asks:
            time_elapsed = current_time_ms - timestamp
            if time_elapsed > HEATMAP_FADE_DURATION_MS:
                prices_to_remove.append(price)
                continue
            if price not in price_y_map:
                continue
            if not current_block or price == current_block[-1][0] - group_by:
                current_block.append((price, qty, timestamp))
            else:
                self._draw_merged_block_helper(painter, current_block, price_y_map, None, current_time_ms, live_heatmap_x, live_heatmap_width, eff_pl_height)
                current_block = [(price, qty, timestamp)]
        if current_block:
            self._draw_merged_block_helper(painter, current_block, price_y_map, None, current_time_ms, live_heatmap_x, live_heatmap_width, eff_pl_height)
        for price in prices_to_remove: 
            if price in self.live_order_book['ask']:
                del self.live_order_book['ask'][price]

    def _draw_candle(self, painter, candle_data, start_x, price_y_map):
        open_p, close_p, high_p, low_p = candle_data.get('open',0), candle_data.get('close',0), candle_data.get('high',0), candle_data.get('low',0)
        levels, is_bullish = candle_data.get('levels', []), close_p > open_p
        group_by = self.settings.PRICE_GROUPING.get(self.current_tf, 1)
        if group_by <= 0: group_by = 1 
        
        poc_price, max_vol_in_candle = None, 0
        if levels:
            levels_map = {p: {'b': b, 'a': a} for p, b, a in levels}
            for p, v in levels_map.items():
                total_vol = v['b'] + v['a']
                if total_vol > max_vol_in_candle: max_vol_in_candle, poc_price = total_vol, p
        else: levels_map = {}
            
        eff_pl_height = self.effective_price_level_height(); eff_body_width = self.effective_candle_body_width()
        eff_profile_width = self.effective_profile_width(); eff_body_profile_gap = self.effective_body_profile_gap()
        
        body_min_p = min(open_p, close_p)
        body_max_p = max(open_p, close_p)
        wick_min_p = low_p
        wick_max_p = high_p
        
        for price, y_pos in price_y_map.items():
            price_end = price + group_by
            
            if self.settings.SHOW_CANDLE_BODY and (body_min_p < price_end and price < body_max_p):
                painter.fillRect(QRectF(start_x, y_pos, eff_body_width, eff_pl_height), self.settings.BULL_COLOR if is_bullish else self.settings.BEAR_COLOR)
            
            elif self.settings.SHOW_CANDLE_WICK and (wick_min_p < price_end and price < wick_max_p):
                if not (body_min_p < price_end and price < body_max_p):
                    painter.fillRect(QRectF(start_x + (eff_body_width - 2) / 2, y_pos, 2, eff_pl_height), self.settings.WICK_COLOR)
            
            if self.settings.SHOW_CANDLE_PROFILE and price in levels_map:
                profile_x = start_x + eff_body_width + eff_body_profile_gap
                bid_vol, ask_vol = levels_map[price]['b'], levels_map[price]['a']
                total_vol, delta = bid_vol + ask_vol, ask_vol - bid_vol
                bar_width = (total_vol / max_vol_in_candle * eff_profile_width) if max_vol_in_candle > 0 else 0
                bar_rect = QRectF(profile_x, y_pos, bar_width, eff_pl_height)
                
                if delta > 0: bar_color = self.settings.DELTA_POS_COLOR
                elif delta < 0: bar_color = self.settings.DELTA_NEG_COLOR
                else: bar_color = self.settings.TEXT_COLOR 
                
                painter.fillRect(bar_rect, bar_color)
                
                combined_text = f"{bid_vol:.1f} x {ask_vol:.1f}"; painter.setPen(self.settings.TEXT_COLOR)
                original_font = painter.font(); bold_font = QFont(original_font); bold_font.setBold(True)
                painter.setFont(bold_font); painter.drawText(QRectF(profile_x, y_pos, eff_profile_width, eff_pl_height), Qt.AlignCenter, combined_text); painter.setFont(original_font)
                
                if price == poc_price: 
                    painter.setPen(QPen(self.settings.POC_HIGHLIGHT_COLOR, 1))
                    painter.drawRect(bar_rect)
                    painter.setPen(Qt.NoPen)
            
    def _draw_last_price_highlight(self, painter, price_y_map):
        if self.last_price > 0:
            group_by = self.settings.PRICE_GROUPING.get(self.current_tf, 1) 
            if group_by <= 0: group_by = 1 
            last_price_bucket = int(self.last_price / group_by) * group_by
            if last_price_bucket in price_y_map:
                y = price_y_map[last_price_bucket]; eff_height = self.effective_price_level_height()
                painter.fillRect(QRectF(0, y, self.width(), eff_height + 2), self.last_price_highlight_color)
                pen = QPen(self.settings.LAST_PRICE_LINE_COLOR, 1, Qt.DashLine); painter.setPen(pen)
                center_y = y + eff_height / 2; painter.drawLine(QPointF(0, center_y), QPointF(self.width(), center_y))
                
    def _draw_crosshair(self, painter):
        eff_pl_height = self.effective_price_level_height(); total_row_height = eff_pl_height + 2
        index = int(self.crosshair_pos.y() / total_row_height); snapped_y = (index * total_row_height) + (eff_pl_height / 2)
        pen = QPen(self.settings.CROSSHAIR_LINE_COLOR, 1, Qt.DashLine); painter.setPen(pen)
        painter.drawLine(0, snapped_y, self.width(), snapped_y)
        eff_total_width = self.effective_candle_total_width(); eff_gap = self.effective_candle_gap(); candle_plus_gap = eff_total_width + eff_gap
        scroll_x = 0; parent_scroll_area = self.parent().parent() 
        if isinstance(parent_scroll_area, QScrollArea): scroll_x = parent_scroll_area.horizontalScrollBar().value()
        absolute_x = self.crosshair_pos.x() + scroll_x; candle_index = int(absolute_x / candle_plus_gap)
        snapped_absolute_x = (candle_index * candle_plus_gap) + (eff_total_width / 2)
        painter.drawLine(QPointF(snapped_absolute_x, 0), QPointF(snapped_absolute_x, self.height()))

class PannableScrollArea(QScrollArea):
    panned = Signal(); zoomRequested = Signal(float)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.setCursor(Qt.OpenHandCursor); self._is_panning, self._is_v_panning = False, False; self._last_mouse_pos = QPoint()
    def wheelEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier: self.zoomRequested.emit(event.angleDelta().y() / 120.0); self.panned.emit()
        elif modifiers == Qt.ShiftModifier: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y()); self.panned.emit()
        else: self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().y()); self.panned.emit()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self._is_panning, self._last_mouse_pos, _ = True, event.position().toPoint(), self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.RightButton: self._is_v_panning, self._last_mouse_pos, _ = True, event.position().toPoint(), self.setCursor(Qt.SizeVerCursor)
        else: super().mousePressEvent(event)
    def mouseReleaseEvent(self, event):
        if event.button() in [Qt.LeftButton, Qt.RightButton]: self._is_panning, self._is_v_panning, _ = False, False, self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
    def mouseMoveEvent(self, event):
        if self._is_panning or self._is_v_panning:
            delta = event.position().toPoint() - self._last_mouse_pos
            if self._is_panning: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._last_mouse_pos = event.position().toPoint(); self.panned.emit()
        super().mouseMoveEvent(event)

# ==============================================================================
# CỬA SỔ CHÍNH
# ==============================================================================
class MainWindow(QMainWindow):
    requestProcessData = Signal(list, str, dict, float)
    
    def __init__(self, db_queue_ref, db_thread_ref):
        super().__init__(); 
        
        self.db_queue = db_queue_ref 
        self.db_thread = db_thread_ref 
        
        self.settings = AppSettings() 
        self.load_settings() 
        
        self.setWindowTitle("Footprint Chart V22.5 - Sửa lỗi Scaling COB") 
        self.resize(1920, 1080)
        self.is_auto_scroll_active = True 
        self.current_tf = self.settings.timeframe; self._initial_sizes_set = False;
        
        self._setup_data_thread(); self._setup_ui(); self._setup_websocket(); self._update_stylesheet()
    
    def load_settings(self):
        try:
            if os.path.exists("chart_settings.json"):
                with open("chart_settings.json", "r") as f:
                    s = json.load(f)
                    for key, value in s.items():
                        if hasattr(self.settings, key):
                            if "COLOR" in key: setattr(self.settings, key, QColor(value))
                            elif key == "MAIN_FONT": self.settings.MAIN_FONT = QFont(value[0], value[1])
                            elif key == "PRICE_GROUPING": 
                                defaults = self.settings.PRICE_GROUPING.copy()
                                if isinstance(value, dict):
                                    defaults.update(value)
                                self.settings.PRICE_GROUPING = defaults
                            else: setattr(self.settings, key, value)
        except Exception as e: print(f"Không thể tải cài đặt, dùng mặc định: {e}")
    
    
    def save_settings(self):
        try:
            s = {key: value for key, value in self.settings.__dict__.items() if not key.startswith('__') and key != 'timeframe'}
            for key, value in s.items():
                if isinstance(value, QColor): s[key] = value.name()
                elif isinstance(value, QFont): s[key] = [value.family(), value.pointSize()]
            with open("chart_settings.json", "w") as f: json.dump(s, f, indent=4)
        except Exception as e: print(f"Không thể lưu cài đặt: {e}")

    def _update_stylesheet(self):
        BG_COLOR = self.settings.BG_COLOR.name(); TEXT_COLOR = self.settings.TEXT_COLOR.name(); GRID_COLOR = self.settings.GRID_COLOR.name() 
        BORDER_LIGHTER_COLOR = "#334155"; ACCENT_COLOR = self.settings.POC_HIGHLIGHT_COLOR.name(); ACCENT_TEXT_COLOR = "#000000"; WIDGET_BG_COLOR = GRID_COLOR 
        self.setStyleSheet(f"""
            QWidget {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; font-family: '{self.settings.MAIN_FONT.family()}'; }} 
            QSplitter::handle {{ background-color: {GRID_COLOR}; }} QSplitter::handle:vertical {{ width: 1px; }} QSplitter#v_splitter::handle:horizontal {{ height: 1px; }}
            QPushButton {{ background-color: {WIDGET_BG_COLOR}; border: 1px solid {BORDER_LIGHTER_COLOR}; padding: 4px 12px; border-radius: 6px; font-size: {self.settings.MAIN_FONT.pointSize()}px; }} 
            QPushButton:checked {{ background-color: {ACCENT_COLOR}; border-color: {ACCENT_COLOR}; color: {ACCENT_TEXT_COLOR}; }} 
            QScrollArea {{ border: none; }} 
            QScrollBar:vertical {{ border: none; background: {BG_COLOR}; width: 0px; margin: 0px 0px 0px 0px; }}
            QScrollBar:horizontal {{ border: none; background: {BG_COLOR}; height: 0px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle {{ background: transparent; border-radius: 0px; }} QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; background: none; }}
            QSpinBox, QDoubleSpinBox {{ background-color: {WIDGET_BG_COLOR}; border: 1px solid {BORDER_LIGHTER_COLOR}; padding: 4px; border-radius: 6px; font-size: {self.settings.MAIN_FONT.pointSize()}px; }}
            QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 15px; border: none; }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url(icons:arrow-up.png); width: 7px; height: 7px; }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url(icons:arrow-down.png); width: 7px; height: 7px; }}
            QSpinBox#header_spinbox {{ padding: 4px 6px; }}
            QFormLayout QLabel {{ font-size: {self.settings.MAIN_FONT.pointSize() + 1}px; padding-top: 4px; }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_sizes_set:
            QTimer.singleShot(100, self._set_bottom_pane_sizes)
            self._initial_sizes_set = True

    def _set_bottom_pane_sizes(self):
        info_pane_height = self.detailed_info_data_widget.height() + 4
        if info_pane_height < 100: info_pane_height = 145 
        total_height = self.height(); top_height = total_height - info_pane_height
        if top_height < 200: top_height = 200; info_pane_height = total_height - top_height;
        if info_pane_height < 100: info_pane_height = 100
        if sum(self.v_splitter.sizes()) == 0 or self.v_splitter.sizes()[0] < 10: self.v_splitter.setSizes([top_height, info_pane_height])
        
        if sum(self.h_splitter.sizes()) == 0 or self.h_splitter.sizes()[0] < 10: 
            w = self.width()
            price_w = 60
            cob_w = 80
            vpvr_w = 80
            chart_w = w - (vpvr_w + cob_w + price_w)
            if chart_w < 400: chart_w = 400
            total_side = vpvr_w + cob_w + price_w
            total_chart = w - total_side
            self.h_splitter.setSizes([total_chart, vpvr_w, cob_w, price_w])
        
    def _setup_data_thread(self): self.data_thread = QThread(); self.data_processor = DataProcessor(); self.data_processor.moveToThread(self.data_thread); self.data_thread.start()
    
    def _setup_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget); main_layout.setSpacing(0); main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(self._create_header()) 
        self.v_splitter = QSplitter(Qt.Vertical); self.v_splitter.setObjectName("v_splitter"); self.v_splitter.setChildrenCollapsible(False)
        self.h_splitter = QSplitter(Qt.Horizontal); self.h_splitter.setChildrenCollapsible(False)
        
        chart_pane = QWidget(); chart_layout = QGridLayout(chart_pane); chart_layout.setSpacing(0); chart_layout.setContentsMargins(0,0,0,0)
        self.chart_widget = FootprintChartWidget(self.settings, parent_window=self) 
        self.chart_scroll_area = PannableScrollArea(); self.chart_scroll_area.setWidget(self.chart_widget)
        self.chart_scroll_area.setWidgetResizable(True); chart_layout.addWidget(self.chart_scroll_area, 0, 0)
        
        self.volume_profile_pane = QWidget(); self.volume_profile_pane.setMinimumWidth(80); vp_layout = QGridLayout(self.volume_profile_pane); vp_layout.setSpacing(0); vp_layout.setContentsMargins(0,0,0,0)
        self.volume_profile_axis_widget = VolumeProfileAxisWidget(self.settings); self.volume_profile_scroll_area = QScrollArea(); self.volume_profile_scroll_area.setWidget(self.volume_profile_axis_widget)
        self.volume_profile_scroll_area.setWidgetResizable(True); self.volume_profile_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); vp_layout.addWidget(self.volume_profile_scroll_area, 0, 0)
        
        self.cob_pane = QWidget(); self.cob_pane.setMinimumWidth(80)
        cob_layout = QGridLayout(self.cob_pane); cob_layout.setSpacing(0); cob_layout.setContentsMargins(0,0,0,0)
        self.cob_widget = CurrentOrderBlockWidget(self.settings)
        self.cob_scroll_area = QScrollArea(); self.cob_scroll_area.setWidget(self.cob_widget)
        self.cob_scroll_area.setWidgetResizable(True); self.cob_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cob_layout.addWidget(self.cob_scroll_area, 0, 0)
        
        self.price_axis_pane = QWidget(); self.price_axis_pane.setMinimumWidth(60); price_layout = QGridLayout(self.price_axis_pane); price_layout.setSpacing(0); price_layout.setContentsMargins(0,0,0,0)
        self.price_axis_widget = PriceAxisWidget(self.settings); self.price_axis_scroll_area = QScrollArea(); self.price_axis_scroll_area.setWidget(self.price_axis_widget)
        self.price_axis_scroll_area.setWidgetResizable(True); self.price_axis_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); price_layout.addWidget(self.price_axis_scroll_area, 0, 0)
        
        self.h_splitter.addWidget(chart_pane)
        self.h_splitter.addWidget(self.volume_profile_pane)
        self.h_splitter.addWidget(self.cob_pane) 
        self.h_splitter.addWidget(self.price_axis_pane)

        self.info_pane = QWidget(); info_layout = QHBoxLayout(self.info_pane); info_layout.setSpacing(0); info_layout.setContentsMargins(0,0,0,0); self.info_pane.setMaximumHeight(150) 
        self.info_labels_widget = InfoLabelsWidget(self.settings)
        self.detailed_info_data_widget = DetailedInfoDataWidget(self.settings); self.info_scroll_area = QScrollArea(); self.info_scroll_area.setWidget(self.detailed_info_data_widget)
        self.info_scroll_area.setWidgetResizable(True); self.info_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        info_layout.addWidget(self.info_scroll_area); info_layout.addWidget(self.info_labels_widget) 
        self.v_splitter.addWidget(self.h_splitter); self.v_splitter.addWidget(self.info_pane)
        main_layout.addWidget(self.v_splitter)
        
        self.setMenuBar(self._create_menu_bar()); 
        self._sync_scrollbars()
        self.apply_settings()
        
        self.chart_widget.dataChanged.connect(self._process_pane_updates)
        self.chart_widget.crosshairMoved.connect(self._on_crosshair_moved)
        self.chart_scroll_area.panned.connect(self._disable_auto_scroll) 
        self.chart_scroll_area.zoomRequested.connect(self.chart_widget.apply_zoom)
        self.requestProcessData.connect(self.data_processor.process_data)
        self.data_processor.dataReady.connect(self.chart_widget.on_data_processed)
        
        self.chart_widget.liveLiquidityChanged.connect(self.cob_widget.on_live_liquidity_updated)

    def _sync_scrollbars(self):
        h_bars = [self.chart_scroll_area.horizontalScrollBar(), self.info_scroll_area.horizontalScrollBar()]
        for i in range(len(h_bars)):
            for j in range(len(h_bars)):
                if i != j: h_bars[i].valueChanged.connect(h_bars[j].setValue)
                
        v_bar_chart = self.chart_scroll_area.verticalScrollBar()
        v_bar_price = self.price_axis_scroll_area.verticalScrollBar()
        v_bar_vp = self.volume_profile_scroll_area.verticalScrollBar()
        v_bar_cob = self.cob_scroll_area.verticalScrollBar() 
        
        v_bars = [v_bar_chart, v_bar_price, v_bar_vp, v_bar_cob]
        for i in range(len(v_bars)):
            for j in range(len(v_bars)):
                if i != j: v_bars[i].valueChanged.connect(v_bars[j].setValue)
                
    def _create_header(self):
        header = QWidget(); header.setFixedHeight(40); header_layout = QHBoxLayout(header); header_layout.setContentsMargins(10, 0, 10, 0)
        self.status_label = QLabel("Đang kết nối..."); header_layout.addWidget(self.status_label); header_layout.addStretch()
        self.timeframe_button_group = QButtonGroup(self)
        for tf in ["1M", "5M", "15M", "1H", "4H", "1D"]:
            btn = QPushButton(tf); btn.setCheckable(True)
            if tf == self.current_tf: btn.setChecked(True)
            btn.clicked.connect(self._on_timeframe_changed); header_layout.addWidget(btn); self.timeframe_button_group.addButton(btn)
        header_layout.addStretch(); header_layout.addSpacing(15)
        self.reset_view_button = QPushButton("Auto Scroll"); 
        self.reset_view_button.setCheckable(True); 
        self.reset_view_button.setChecked(self.is_auto_scroll_active); 
        self.reset_view_button.toggled.connect(self._on_auto_scroll_toggled); 
        header_layout.addWidget(self.reset_view_button)
        settings_button = QPushButton("Cài Đặt"); settings_button.clicked.connect(self.open_settings_dialog); header_layout.addWidget(settings_button)
        return header
        
    def _create_menu_bar(self):
        menu_bar = QMenuBar(); 
        indicator_menu = menu_bar.addMenu("Indicators")
        
        builtin_menu = indicator_menu.addMenu("Add Built-in Indicator")
        vwap_action = QAction("VWAP (Moving)", self)
        vwap_action.triggered.connect(lambda: self.chart_widget.add_indicator(VWAPIndicator(self.settings)))
        builtin_menu.addAction(vwap_action)

        load_action = QAction("Load Indicator from File...", self); load_action.triggered.connect(self.load_indicator_from_file); indicator_menu.addAction(load_action)
        indicator_menu.addSeparator()
        clear_indicators_action = QAction("Xóa hết Indicators", self); clear_indicators_action.triggered.connect(self.chart_widget.clear_indicators); indicator_menu.addAction(clear_indicators_action)
        return menu_bar
    
    def load_indicator_from_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Chọn file Indicator Python", "", "Python Files (*.py)")
        if not filepath: return
        try:
            module_name = os.path.splitext(os.path.basename(filepath))[0]; spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseIndicator) and obj is not BaseIndicator:
                    self.chart_widget.add_indicator(obj(self.settings)); print(f"Đã tải thành công: {obj.__name__}"); return
            print("Lỗi: Không tìm thấy class indicator hợp lệ trong file.")
        except Exception as e: print(f"Lỗi khi tải indicator: {e}")
        
    @Slot(bool)
    def _on_auto_scroll_toggled(self, checked):
        self.is_auto_scroll_active = checked
        if checked: self.chart_widget.reset_zoom(); QTimer.singleShot(50, self._scroll_to_end)
        
    @Slot()
    def _disable_auto_scroll(self):
        if self.is_auto_scroll_active: 
            self.reset_view_button.setChecked(False) 
            self.is_auto_scroll_active = False
        
    @Slot()
    def open_settings_dialog(self): 
        dialog = SettingsDialog(self.settings, self)
        dialog.settingsApplied.connect(self.apply_settings)
        dialog.exec()
    
    @Slot()
    def apply_settings(self):
        QTimer.singleShot(0, self._apply_settings_deferred)

    def _apply_settings_deferred(self):
        self.save_settings()
        self._update_stylesheet()
        
        if self.websocket.isValid():
            print("Đang gửi cài đặt Price Grouping mới cho Backend...")
            self.websocket.sendTextMessage(json.dumps({
                "type": "update_settings",
                "price_grouping": self.settings.PRICE_GROUPING
            }))
        
        h_sizes = self.h_splitter.sizes()
        v_sizes = self.v_splitter.sizes()

        self.info_pane.setVisible(self.settings.SHOW_INFO_PANE)
        self.info_labels_widget.setVisible(self.settings.SHOW_PANE_3)
        self.volume_profile_pane.setVisible(self.settings.SHOW_VPVR_PANE)
        self.cob_pane.setVisible(self.settings.SHOW_COB_PANE)
        self.price_axis_pane.setVisible(self.settings.SHOW_VPVR_PANE) 
        
        self.h_splitter.setSizes(h_sizes)
        self.v_splitter.setSizes(v_sizes)
        
        current_maxlen = self.chart_widget.chart_data.maxlen
        new_maxlen = self.settings.get_max_candles(self.current_tf)
        
        print(f"Áp dụng cài đặt mới. Yêu cầu lại dữ liệu cho {self.current_tf}...")
        if current_maxlen != new_maxlen:
            print(f"Thay đổi maxlen từ {current_maxlen} sang {new_maxlen}")
            old_data = list(self.chart_widget.chart_data)
            self.chart_widget.chart_data = deque(maxlen=new_maxlen)
            self.chart_widget.chart_data.extend(old_data)
        
        self.chart_widget.set_historical_heatmap([]) 
        self._request_timeframe_data(self.current_tf) 
        
    @Slot()
    def _process_pane_updates(self):
        QTimer.singleShot(0, self._deferred_process_pane_updates)

    def _deferred_process_pane_updates(self):
        if not self.chart_widget: return 
        params = self.chart_widget.get_render_params()
        self.price_axis_widget.update_data(params)
        self.volume_profile_axis_widget.update_data(params)
        self.cob_widget.update_data(params)
        self.detailed_info_data_widget.update_data(params)
        if self.is_auto_scroll_active: self._scroll_to_end()
        
    @Slot(QPoint)
    def _on_crosshair_moved(self, pos):
        h_scroll_value = self.chart_scroll_area.horizontalScrollBar().value()
        absolute_x = pos.x() + h_scroll_value; viewport_y = pos.y()
        self.price_axis_widget.set_crosshair_y(viewport_y)
        self.detailed_info_data_widget.set_crosshair_x(absolute_x)
        
    def _setup_websocket(self):
        self.websocket = QWebSocket(); self.websocket.connected.connect(self._on_websocket_connected)
        self.websocket.disconnected.connect(self._on_websocket_disconnected); self.websocket.textMessageReceived.connect(self._on_websocket_message)
        self.reconnect_timer = QTimer(self); self.reconnect_timer.setInterval(3000); self.reconnect_timer.timeout.connect(self._connect_websocket); self._connect_websocket()
        
    def _connect_websocket(self): 
        print(f"Frontend đang kết nối tới ws://{SERVER_HOST}:{SERVER_PORT}...")
        self.websocket.open(QUrl(f"ws://{SERVER_HOST}:{SERVER_PORT}"))
        
    def _on_websocket_connected(self): 
        self.status_label.setText(f"<span style='color: {self.settings.BULL_COLOR.name()};'>●</span> Đã kết nối"); 
        self.reconnect_timer.stop(); 
        if self.websocket.isValid():
            print("Kết nối thành công. Đang gửi cài đặt cho Backend...")
            self.websocket.sendTextMessage(json.dumps({ "type": "update_settings", "price_grouping": self.settings.PRICE_GROUPING }))
        self._request_timeframe_data(self.current_tf)

    def _on_websocket_disconnected(self): 
        self.status_label.setText(f"<span style='color: {self.settings.BEAR_COLOR.name()};'>●</span> Mất kết nối..."); self.reconnect_timer.start()
    
    def _request_timeframe_data(self, tf):
        max_candles = self.settings.get_max_candles(tf)
        self.websocket.sendTextMessage(json.dumps({
            "type": "request_timeframe", 
            "timeframe": tf,
            "max_candles": max_candles,
            "min_liquidity": self.settings.MIN_LIQUIDITY_TO_SHOW 
        }))
    
    # (Giữ nguyên) Sửa lỗi AttributeError
    def _scroll_to_end(self):
        self.chart_scroll_area.horizontalScrollBar().setValue(self.chart_scroll_area.horizontalScrollBar().maximum())
        params = self.chart_widget.get_render_params()
        
        if not params["price_scale"] or params["last_price"] == 0: 
            return
            
        price_scale = params["price_scale"]; group_by = self.settings.PRICE_GROUPING.get(params["timeframe"], 1)
        if group_by <= 0: group_by = 1 
        
        last_price_bucket = int(params["last_price"] / group_by) * group_by 
        
        try:
            target_index = price_scale.index(last_price_bucket); eff_pl_height = self.chart_widget.effective_price_level_height()
            target_y = target_index * (eff_pl_height + 2); viewport_height = self.chart_scroll_area.viewport().height()
            scroll_y = target_y - viewport_height / 2; self.chart_scroll_area.verticalScrollBar().setValue(int(scroll_y))
        except ValueError: 
             v_bar = self.chart_scroll_area.verticalScrollBar(); 
             v_bar.setValue(int(v_bar.maximum() / 2))
        
    @Slot()
    def _on_timeframe_changed(self):
        sender = self.sender()
        if not sender: return
        new_tf = sender.text()
        if new_tf != self.current_tf:
            self.current_tf = new_tf
            self.chart_widget.current_tf = new_tf
            
            new_maxlen = self.settings.get_max_candles(new_tf)
            print(f"Đổi Timeframe sang {new_tf}, maxlen = {new_maxlen}")
            old_data = list(self.chart_widget.chart_data)
            self.chart_widget.chart_data = deque(maxlen=new_maxlen)
            self.chart_widget.chart_data.extend(old_data) 
            
            self.chart_widget.chart_data.clear()
            self.chart_widget.on_data_processed({}) 
            self.chart_widget.set_historical_heatmap([]) 
            
            self.cob_widget.on_live_liquidity_updated({}, 1.0)
            
            if self.websocket.isValid():
                self._request_timeframe_data(self.current_tf)
            else:
                 pass 
            
    @Slot(str)
    def _on_websocket_message(self, msg):
        try: message = json.loads(msg)
        except json.JSONDecodeError: return
        msg_type = message.get('type')
        
        if msg_type == 'full_data' and message.get('timeframe') == self.current_tf:
            self.chart_widget.chart_data.clear()
            self.chart_widget.chart_data.extend(message.get('data', [])) 
            if self.chart_widget.chart_data: self.chart_widget.last_price = self.chart_widget.chart_data[-1].get('close', 0)
            
            self.requestProcessData.emit(list(self.chart_widget.chart_data), self.current_tf, self.settings.PRICE_GROUPING, self.chart_widget.last_price)
        
        elif msg_type == 'update':
            update = message.get('data', {}).get(self.current_tf)
            if update:
                if self.chart_widget.chart_data and self.chart_widget.chart_data[-1]['timestamp'] == update['timestamp']:
                    self.chart_widget.chart_data[-1] = update
                else:
                    self.chart_widget.chart_data.append(update) 
                self.chart_widget.last_price = self.chart_widget.chart_data[-1].get('close', 0)
                
                self.requestProcessData.emit(list(self.chart_widget.chart_data), self.current_tf, self.settings.PRICE_GROUPING, self.chart_widget.last_price)
        
        elif msg_type == 'full_heatmap' and message.get('timeframe') == self.current_tf:
            print(f"Nhận được {len(message.get('data', []))} điểm heatmap lịch sử.")
            self.chart_widget.set_historical_heatmap(message.get('data', []))

        elif msg_type == 'liquidity_raw':
            self.chart_widget.add_live_liquidity(message)
                
    def closeEvent(self, event): 
        print("Bắt đầu quá trình tắt máy...")
        self.save_settings()
        
        self.db_queue.put(None) 
        
        self.data_thread.quit()
        self.data_thread.wait()
        
        if self.db_thread and self.db_thread.is_alive():
            print("Đang đợi luồng CSDL (Nhân Viên Kho) tắt...")
            self.db_thread.join(timeout=10.0) 
            if self.db_thread.is_alive():
                print("Lỗi: Luồng CSDL không chịu tắt! Tắt cưỡng bức.")
        
        print("Tắt máy hoàn tất.")
        super().closeEvent(event)