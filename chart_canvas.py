"""
chart_canvas.py
График STRG в строгом стиле QUIK:
- Тонкие контурные свечи (BarGraphItem + косметические фитили 1px)
- Фиксированная точная временная и ценовая ось (без скачков шкалы)
- Линии уровней фракталов с бейджами Fractal <price>
- Отображение сделок (стрелки Buy/Sell) с обязательными номерами попыток (#1, #2, #3...)
- Защитные уровни SL (красный пунктир) и TP (зеленый пунктир)
"""

import pyqtgraph as pg
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt
import numpy as np


class CustomTimeAxis(pg.AxisItem):
    """Ось X: точное время свечи."""
    def __init__(self, time_labels, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_labels = time_labels

    def set_time_labels(self, labels):
        self.time_labels = labels

    def tickStrings(self, values, scale, spacing):
        result = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self.time_labels):
                result.append(self.time_labels[idx])
            else:
                result.append("")
        return result


class CustomPriceAxis(pg.AxisItem):
    """Ось Y: цены с пробелом тысяч (226 250)."""
    def tickStrings(self, values, scale, spacing):
        return [f"{int(v):,}".replace(",", " ") if v == int(v) else f"{v:,.1f}".replace(",", " ") for v in values]


class ChartCanvas(pg.PlotWidget):
    """Основной виджет графика STRG."""
    def __init__(self):
        self.time_axis = CustomTimeAxis(time_labels=[], orientation="bottom")
        self.price_axis = CustomPriceAxis(orientation="right")

        super().__init__(axisItems={"bottom": self.time_axis, "right": self.price_axis})

        self._chart_items = []
        self.current_price_line = None
        self.price_label = None

        self._setup_style()

    def _setup_style(self):
        """Строгий стиль QUIK Dark."""
        self.hideButtons()
        self.getPlotItem().setMenuEnabled(False)

        self.setBackground("#181818")
        
        pi = self.getPlotItem()
        pi.showAxis("right")
        pi.hideAxis("left")
        pi.showGrid(x=True, y=True, alpha=0.12)
        pi.getAxis("right").setPen(pg.mkPen(color="#333333", width=1))
        pi.getAxis("bottom").setPen(pg.mkPen(color="#333333", width=1))
        pi.getAxis("right").setTextPen(pg.mkPen(color="#888888"))
        pi.getAxis("bottom").setTextPen(pg.mkPen(color="#888888"))

        # Линия текущей цены
        self.current_price_line = pg.InfiniteLine(
            pos=0, angle=0,
            pen=pg.mkPen(color="#c9b037", width=1, style=Qt.PenStyle.SolidLine),
        )
        pi.addItem(self.current_price_line)

        self.price_label = pg.TextItem(
            text="", anchor=(0, 0.5), color="#111111",
            fill=pg.mkBrush("#c9b037")
        )
        pi.addItem(self.price_label)

    def _clear_chart_items(self):
        """Удаляет все динамические элементы (свечи, уровни, сделки)."""
        pi = self.getPlotItem()
        for item in self._chart_items:
            pi.removeItem(item)
        self._chart_items.clear()

    def set_full_timeline(self, df_candles_full):
        """Устанавливает стабильную шкалу времени на весь день."""
        if not df_candles_full.empty:
            labels = df_candles_full["time"].dt.strftime("%H:%M").tolist()
            self.time_axis.set_time_labels(labels)

    def render_candles(self, df_candles, auto_range=False):
        """Отрисовывает свечи на графике."""
        self._clear_chart_items()
        pi = self.getPlotItem()

        if df_candles.empty:
            return

        idx = df_candles["bar_idx"].values.astype(float)
        opens = df_candles["open"].values
        highs = df_candles["high"].values
        lows = df_candles["low"].values
        closes = df_candles["close"].values

        up_mask = closes >= opens
        down_mask = ~up_mask

        # ===============================
        # 1. ФИТИЛИ (1px косметические линии)
        # ===============================
        wick_x = np.repeat(idx, 2)
        wick_y = np.column_stack([lows, highs]).flatten()
        wick_pen = pg.mkPen(color="#999999", width=1)
        wick_pen.setCosmetic(True)
        wick_item = pg.PlotCurveItem(wick_x, wick_y, connect="pairs", pen=wick_pen)
        pi.addItem(wick_item)
        self._chart_items.append(wick_item)

        # ===============================
        # 2. ТЕЛА СВЕЧЕЙ (BarGraphItem)
        # ===============================
        bar_width = 0.55

        # Растущие свечи
        if up_mask.any():
            up_idx = idx[up_mask]
            up_open = opens[up_mask]
            up_close = closes[up_mask]
            up_heights = up_close - up_open
            up_heights[up_heights < 0.5] = 0.5

            up_pen = pg.mkPen(color="#cccccc", width=1)
            up_pen.setCosmetic(True)
            up_bars = pg.BarGraphItem(
                x=up_idx, y=up_open, height=up_heights, width=bar_width,
                pen=up_pen, brush=pg.mkBrush("#cccccc")
            )
            pi.addItem(up_bars)
            self._chart_items.append(up_bars)

        # Падающие свечи
        if down_mask.any():
            dn_idx = idx[down_mask]
            dn_open = opens[down_mask]
            dn_close = closes[down_mask]
            dn_heights = dn_open - dn_close
            dn_heights[dn_heights < 0.5] = 0.5

            dn_pen = pg.mkPen(color="#555555", width=1)
            dn_pen.setCosmetic(True)
            dn_bars = pg.BarGraphItem(
                x=dn_idx, y=dn_close, height=dn_heights, width=bar_width,
                pen=dn_pen, brush=pg.mkBrush("#444444")
            )
            pi.addItem(dn_bars)
            self._chart_items.append(dn_bars)

        # ===============================
        # 3. ЛИНИЯ ТЕКУЩЕЙ ЦЕНЫ
        # ===============================
        n = len(df_candles)
        last_price = closes[-1]
        self.current_price_line.setValue(last_price)
        self.price_label.setText(f" {int(last_price):,} ".replace(",", " "))
        self.price_label.setPos(n + 1, last_price)

        if auto_range:
            price_range = highs.max() - lows.min()
            pi.setXRange(-3, n + 8, padding=0.01)
            margin = price_range * 0.05
            pi.setYRange(lows.min() - margin, highs.max() + margin, padding=0.01)

    def render_fractal_levels(self, levels, df_candles):
        """
        Отрисовывает горизонтальные пунктирные линии фракталов с бейджами.
        Линия тянется от момента появления до снятия (или до текущей свечи).
        """
        if not levels or df_candles.empty:
            return

        pi = self.getPlotItem()
        c_times = df_candles["time"].values
        n_bars = len(df_candles)
        curr_time = c_times[-1]

        badge_font = QFont("Tahoma", 8, QFont.Weight.Bold)

        for lvl in levels:
            price = lvl["price"]
            st = np.datetime64(lvl["start_time"])
            et = np.datetime64(lvl["end_time"])

            # Если уровень появился позже текущего момента — не рисуем
            if st > curr_time:
                continue

            idx_start = int(np.searchsorted(c_times, st, side="right")) - 1
            idx_start = max(0, min(idx_start, n_bars - 1))

            # Если уровень еще активен в текущий момент — тянем его до последней видимой свечи
            eff_et = min(et, curr_time)
            idx_end = int(np.searchsorted(c_times, eff_et, side="right")) - 1
            idx_end = max(idx_start + 1, min(idx_end, n_bars - 1))

            # Желтая пунктирная линия
            pen_lvl = pg.mkPen(color="#e5a93c", width=1, style=Qt.PenStyle.DotLine)
            pen_lvl.setCosmetic(True)
            line = pg.PlotCurveItem(x=[idx_start, idx_end], y=[price, price], pen=pen_lvl)
            pi.addItem(line)
            self._chart_items.append(line)

            # Прямоугольная плашка посередине отрезка линии
            idx_mid = (idx_start + idx_end) / 2.0
            badge = pg.TextItem(
                text=f" {lvl.get('label', f'Fractal {int(price)}')} ",
                color="#ffffff",
                fill=pg.mkBrush("#e5a93c"),
                anchor=(0.5, 0.5)
            )
            badge.setFont(badge_font)
            badge.setPos(idx_mid, price)
            pi.addItem(badge)
            self._chart_items.append(badge)

    def render_trades(self, trades, df_candles):
        """
        Отрисовывает точки входов в сделки:
        - Real Buy: зеленая стрелка ▲ (влево)
        - Real Sell: красная стрелка ▼ (вправо)
        - Virt Buy: желтая стрелка ▲ (влево)
        - Virt Sell: фиолетовая стрелка ▼ (вправо)
        - ВСЕГДА отображает цифру попытки перезахода (#1, #2, #3, #4)
        - Рисует линии SL (красный пунктир) и TP (зеленый пунктир)
        """
        if not trades or df_candles.empty:
            return

        pi = self.getPlotItem()
        c_times = df_candles["time"].values
        n_bars = len(df_candles)
        curr_time = c_times[-1]

        rb_x, rb_y = [], []
        rs_x, rs_y = [], []
        vb_x, vb_y = [], []
        vs_x, vs_y = [], []

        att_font = QFont("Tahoma", 8, QFont.Weight.Bold)

        pen_sl = pg.mkPen(color="#e74c3c", width=1, style=Qt.PenStyle.DotLine)
        pen_sl.setCosmetic(True)
        pen_tp = pg.mkPen(color="#2ecc71", width=1, style=Qt.PenStyle.DotLine)
        pen_tp.setCosmetic(True)

        for tr in trades:
            t = np.datetime64(tr["entry_time"])
            if t > curr_time:
                continue

            idx = int(np.searchsorted(c_times, t, side="right")) - 1
            idx = max(0, min(idx, n_bars - 1))

            p = tr["entry_price"]
            is_real = tr["is_real"]
            direction = tr["direction"]
            attempt = tr.get("attempt", 1)

            # Отрисовка стрелки и номера перезахода
            if direction == "BUY":
                x_pos = idx - 0.22
                if is_real:
                    rb_x.append(x_pos)
                    rb_y.append(p)
                    lbl_col = "#2ecc71"
                else:
                    vb_x.append(x_pos)
                    vb_y.append(p)
                    lbl_col = "#f1c40f"

                # Цифра перезахода под стрелкой — ВСЕГДА
                lbl = pg.TextItem(text=f"#{attempt}", color=lbl_col, anchor=(0.5, -0.4))
                lbl.setFont(att_font)
                lbl.setPos(x_pos, p)
                pi.addItem(lbl)
                self._chart_items.append(lbl)

            else:
                x_pos = idx + 0.22
                if is_real:
                    rs_x.append(x_pos)
                    rs_y.append(p)
                    lbl_col = "#e74c3c"
                else:
                    vs_x.append(x_pos)
                    vs_y.append(p)
                    lbl_col = "#9b59b6"

                # Цифра перезахода над стрелкой — ВСЕГДА
                lbl = pg.TextItem(text=f"#{attempt}", color=lbl_col, anchor=(0.5, 1.4))
                lbl.setFont(att_font)
                lbl.setPos(x_pos, p)
                pi.addItem(lbl)
                self._chart_items.append(lbl)

            # Отрисовка линий SL и TP для реальных сделок
            if is_real and tr.get("sl") and tr.get("tp"):
                sl_price = tr["sl"]
                tp_price = tr["tp"]
                
                # Конечная точка линии (момент закрытия сделки или текущее время)
                if tr.get("close_time"):
                    close_np = np.datetime64(tr["close_time"])
                    eff_close = min(close_np, curr_time)
                else:
                    eff_close = curr_time

                idx_close = int(np.searchsorted(c_times, eff_close, side="right")) - 1
                idx_close = max(idx + 1, min(idx_close, n_bars - 1))

                # Линия Stop Loss
                line_sl = pg.PlotCurveItem(x=[idx, idx_close], y=[sl_price, sl_price], pen=pen_sl)
                pi.addItem(line_sl)
                self._chart_items.append(line_sl)

                # Линия Take Profit
                line_tp = pg.PlotCurveItem(x=[idx, idx_close], y=[tp_price, tp_price], pen=pen_tp)
                pi.addItem(line_tp)
                self._chart_items.append(line_tp)

        # Стрелки сделок
        if rb_x:
            sp_rb = pg.ScatterPlotItem(
                x=rb_x, y=rb_y, symbol="t1", size=10,
                pen=pg.mkPen(color="#1b5e20", width=1), brush=pg.mkBrush("#2ecc71")
            )
            pi.addItem(sp_rb)
            self._chart_items.append(sp_rb)

        if rs_x:
            sp_rs = pg.ScatterPlotItem(
                x=rs_x, y=rs_y, symbol="t", size=10,
                pen=pg.mkPen(color="#7f1d1d", width=1), brush=pg.mkBrush("#e74c3c")
            )
            pi.addItem(sp_rs)
            self._chart_items.append(sp_rs)

        if vb_x:
            sp_vb = pg.ScatterPlotItem(
                x=vb_x, y=vb_y, symbol="t1", size=9,
                pen=pg.mkPen(color="#7d6608", width=1), brush=pg.mkBrush("#f1c40f")
            )
            pi.addItem(sp_vb)
            self._chart_items.append(sp_vb)

        if vs_x:
            sp_vs = pg.ScatterPlotItem(
                x=vs_x, y=vs_y, symbol="t", size=9,
                pen=pg.mkPen(color="#4a235a", width=1), brush=pg.mkBrush("#9b59b6")
            )
            pi.addItem(sp_vs)
            self._chart_items.append(sp_vs)
