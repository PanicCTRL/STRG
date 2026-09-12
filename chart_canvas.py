"""
chart_canvas.py
График STRG в строгом стиле QUIK:
- Тонкие контурные свечи (BarGraphItem + косметические фитили 1px)
- Фиксированная точная временная и ценовая ось (без скачков шкалы)
- Линии уровней фракталов с бейджами Fractal <price>
- Отображение сделок (стрелки Buy/Sell) с обязательными номерами попыток (#1, #2, #3...)
- Защитные уровни SL (красный пунктир) и TP (зеленый пунктир)
"""

import math
import pyqtgraph as pg
from PyQt6.QtGui import QColor, QFont, QPainter, QPolygonF, QPen, QBrush
from PyQt6.QtCore import Qt, QPointF, QRectF
import numpy as np
import pandas as pd
import theme


class TradeVectorItem(pg.GraphicsObject):
    """
    Векторная стрелка сделки от точки входа к уровню TP или SL:
    - Линия со сплошным треугольным наконечником на конце.
    - Наконечник косметический (фиксированный размер в пикселях, не искажается при масштабировании графика).
    """
    def __init__(self, x1, y1, x2, y2, color, width=2.0, head_size=10):
        super().__init__()
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.x2 = float(x2)
        self.y2 = float(y2)
        self.color = QColor(color)
        self.pen = QPen(self.color, width)
        self.pen.setCosmetic(True)
        self.brush = QBrush(self.color)
        self.head_size = head_size

    def boundingRect(self):
        xmin = min(self.x1, self.x2)
        xmax = max(self.x1, self.x2)
        ymin = min(self.y1, self.y2)
        ymax = max(self.y1, self.y2)
        return QRectF(xmin - 0.5, ymin - 10, max(1.0, xmax - xmin + 1.0), max(20.0, ymax - ymin + 20.0))

    def paint(self, p, opt, widget):
        vb = self.getViewBox()
        if vb is None:
            return

        p1_dev = vb.mapViewToDevice(QPointF(self.x1, self.y1))
        p2_dev = vb.mapViewToDevice(QPointF(self.x2, self.y2))

        dx = p2_dev.x() - p1_dev.x()
        dy = p2_dev.y() - p1_dev.y()
        length = math.hypot(dx, dy)
        if length < 3:
            return

        p.save()
        p.resetTransform()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        hs = self.head_size
        hw = hs * 0.42
        ux = dx / length
        uy = dy / length

        tip = p2_dev
        nx = -uy
        ny = ux
        base_left = QPointF(tip.x() - hs * ux + hw * nx, tip.y() - hs * uy + hw * ny)
        base_right = QPointF(tip.x() - hs * ux - hw * nx, tip.y() - hs * uy - hw * ny)
        arrow_base = QPointF(tip.x() - (hs - 1) * ux, tip.y() - (hs - 1) * uy)

        p.setPen(self.pen)
        p.drawLine(p1_dev, arrow_base)

        p.setBrush(self.brush)
        p.drawPolygon(QPolygonF([tip, base_left, base_right]))

        p.restore()


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
        self.df_candles = None
        self.current_price_line = None
        self.price_label = None
        self.v_line = None
        self.h_line = None
        self.crosshair_label = None

        self.visibility = {
            "candles": True,
            "current_price": True,
            "crosshair": True,
            "classic_fractals": True,
            "plateau_high": True,
            "plateau_low": True,
            "ch0_orange_upper": True,
            "ch0_orange_lower": True,
            "ch0_orange_fill": True,
            "ch1_green_upper": True,
            "ch1_green_lower": True,
            "ch1_green_fill": True,
            "ch2_purple_upper": True,
            "ch2_purple_lower": True,
            "ch2_purple_fill": True,
            "ch3_blue_upper": True,
            "ch3_blue_lower": True,
            "ch3_blue_fill": True,
            "ch4_cyan_upper": True,
            "ch4_cyan_lower": True,
            "ch4_cyan_fill": True,
            "corridor_upper": True,
            "corridor_lower": True,
            "corridor_fill": True,
            "fractal_levels": True,
            "level_labels": True,
            "levels_active_only": False,
            "choch_arrows": True,
            "choch_shelves": True,
            "real_trades": True,
            "real_vectors": True,
            "real_attempts": True,
            "real_sl": True,
            "real_tp": True,
            "filter_profitable": True,
            "filter_loss": True,
            "virt_trades": True,
            "virt_vectors": True,
            "virt_attempts": True,
            "virt_sl": True,
            "virt_tp": True,
            "virt_filter_profitable": True,
            "virt_filter_loss": True,
        }

        self._setup_style()

    def update_visibility(self, config):
        """Обновляет параметры видимости элементов графика."""
        self.visibility.update(config)

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

        # Интерактивное перекрестие (Crosshair)
        pen_cross = pg.mkPen(color="#777777", width=1, style=Qt.PenStyle.DashLine)
        pen_cross.setCosmetic(True)

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pen_cross)
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pen_cross)
        self.v_line.setVisible(False)
        self.h_line.setVisible(False)
        pi.addItem(self.v_line, ignoreBounds=True)
        pi.addItem(self.h_line, ignoreBounds=True)

        # Плашка под курсором (HUD Tooltip)
        self.crosshair_label = pg.TextItem(
            text="", anchor=(-0.05, 1.05), color="#e0e0e0",
            fill=pg.mkBrush(QColor(18, 18, 18, 230)),
            border=pg.mkPen("#444444", width=1)
        )
        self.crosshair_label.setFont(QFont("Consolas", 8))
        self.crosshair_label.setVisible(False)
        pi.addItem(self.crosshair_label, ignoreBounds=True)

        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self.v_line:
            self.v_line.setVisible(False)
        if self.h_line:
            self.h_line.setVisible(False)
        if self.crosshair_label:
            self.crosshair_label.setVisible(False)

    def _on_mouse_moved(self, pos):
        if not self.visibility.get("crosshair", True):
            if self.v_line:
                self.v_line.setVisible(False)
            if self.h_line:
                self.h_line.setVisible(False)
            if self.crosshair_label:
                self.crosshair_label.setVisible(False)
            return

        pi = self.getPlotItem()
        vb = pi.vb
        if not vb.sceneBoundingRect().contains(pos):
            self.v_line.setVisible(False)
            self.h_line.setVisible(False)
            self.crosshair_label.setVisible(False)
            return

        mouse_pt = vb.mapSceneToView(pos)
        x_val = mouse_pt.x()
        y_val = mouse_pt.y()

        self.v_line.setPos(x_val)
        self.h_line.setPos(y_val)
        self.v_line.setVisible(True)
        self.h_line.setVisible(True)

        if self.df_candles is not None and not self.df_candles.empty:
            idx = int(round(x_val))
            if 0 <= idx < len(self.df_candles):
                row = self.df_candles.iloc[idx]
                t_str = row["time"].strftime("%H:%M")
                p_cur = f"{int(round(y_val)):,}".replace(",", " ")
                o = f"{int(row['open']):,}".replace(",", " ")
                h = f"{int(row['high']):,}".replace(",", " ")
                l = f"{int(row['low']):,}".replace(",", " ")
                c = f"{int(row['close']):,}".replace(",", " ")
                vol = f"{int(row['volume']):,}".replace(",", " ")

                text = (
                    f" {t_str} | Курсор: {p_cur}\n"
                    f" O: {o}   H: {h}\n"
                    f" L: {l}   C: {c}\n"
                    f" Объём: {vol} "
                )
                self.crosshair_label.setText(text)

                view_range = vb.viewRange()
                x_range = view_range[0]
                y_range = view_range[1]

                # Автоматически смещаем плашку, чтобы не вылезала за края графика
                anchor_x = 1.05 if (x_val - x_range[0]) > 0.7 * (x_range[1] - x_range[0]) else -0.05
                anchor_y = 1.05 if (y_val - y_range[0]) < 0.3 * (y_range[1] - y_range[0]) else -0.05

                self.crosshair_label.setAnchor((anchor_x, anchor_y))
                self.crosshair_label.setPos(x_val, y_val)
                self.crosshair_label.setVisible(True)
            else:
                self.crosshair_label.setVisible(False)
        else:
            self.crosshair_label.setVisible(False)

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
        self.df_candles = df_candles
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
        # 1. ФИТИЛИ И ТЕЛА СВЕЧЕЙ
        # ===============================
        show_candles = self.visibility.get("candles", True)
        if show_candles:
            # 1. ФИТИЛИ (1px косметические линии)
            wick_x = np.repeat(idx, 2)
            wick_y = np.column_stack([lows, highs]).flatten()
            wick_pen = pg.mkPen(color="#999999", width=1)
            wick_pen.setCosmetic(True)
            wick_item = pg.PlotCurveItem(wick_x, wick_y, connect="pairs", pen=wick_pen)
            pi.addItem(wick_item)
            self._chart_items.append(wick_item)

            # 2. ТЕЛА СВЕЧЕЙ (BarGraphItem через y0 и y1 для точной привязки к Open и Close)
            bar_width = 0.55

            # Растущие свечи
            if up_mask.any():
                up_idx = idx[up_mask]
                up_open = opens[up_mask]
                up_close = closes[up_mask]
                up_close_eff = np.maximum(up_close, up_open + 0.5)

                up_pen = pg.mkPen(color="#cccccc", width=1)
                up_pen.setCosmetic(True)
                up_bars = pg.BarGraphItem(
                    x=up_idx, y0=up_open, y1=up_close_eff, width=bar_width,
                    pen=up_pen, brush=pg.mkBrush("#cccccc")
                )
                pi.addItem(up_bars)
                self._chart_items.append(up_bars)

            # Падающие свечи
            if down_mask.any():
                dn_idx = idx[down_mask]
                dn_open = opens[down_mask]
                dn_close = closes[down_mask]
                dn_open_eff = np.maximum(dn_open, dn_close + 0.5)

                dn_pen = pg.mkPen(color="#555555", width=1)
                dn_pen.setCosmetic(True)
                dn_bars = pg.BarGraphItem(
                    x=dn_idx, y0=dn_close, y1=dn_open_eff, width=bar_width,
                    pen=dn_pen, brush=pg.mkBrush("#333333")
                )
                pi.addItem(dn_bars)
                self._chart_items.append(dn_bars)

        # ===============================
        # 3. ЛИНИЯ ТЕКУЩЕЙ ЦЕНЫ
        # ===============================
        n = len(df_candles)
        last_price = closes[-1]
        show_cur_price = self.visibility.get("current_price", True)
        self.current_price_line.setVisible(show_cur_price)
        self.price_label.setVisible(show_cur_price)
        if show_cur_price:
            self.current_price_line.setValue(last_price)
            self.price_label.setText(f" {int(last_price):,} ".replace(",", " "))
            self.price_label.setPos(n + 1, last_price)

        if auto_range:
            price_range = highs.max() - lows.min()
            pi.setXRange(-3, n + 8, padding=0.01)
            margin = price_range * 0.05
            pi.setYRange(lows.min() - margin, highs.max() + margin, padding=0.01)

    def render_classic_fractals(self, df_candles):
        """
        Отрисовывает классические 5-свечные фракталы Билла Вильямса:
        - Зелёный треугольник ▲ (FRACTAL_UP) над максимумом подтверждённой свечи
        - Красный треугольник ▼ (FRACTAL_DOWN) под минимумом подтверждённой свечи
        """
        if not self.visibility.get("classic_fractals", True):
            return

        if df_candles is None or len(df_candles) < 5:
            return

        pi = self.getPlotItem()

        # Фрактал считается подтверждённым, если справа от него закрылись как минимум 2 свечи
        confirmed = df_candles.iloc[:-2]
        up_mask = confirmed["fractal_up"].notna()
        down_mask = confirmed["fractal_down"].notna()

        if not up_mask.any() and not down_mask.any():
            return

        highs = df_candles["high"].values
        lows = df_candles["low"].values
        price_range = max(100.0, float(highs.max() - lows.min()))
        offset = price_range * 0.012

        # 1. Верхние фракталы ▲
        if up_mask.any():
            up_bars = confirmed[up_mask]
            up_x = up_bars["bar_idx"].values.astype(float)
            up_y = up_bars["high"].values.astype(float) + offset

            sp_up = pg.ScatterPlotItem(
                x=up_x, y=up_y, symbol="t1", size=9,
                pen=pg.mkPen(color="#134e3f", width=1),
                brush=pg.mkBrush(theme.FRACTAL_UP)
            )
            pi.addItem(sp_up)
            self._chart_items.append(sp_up)

        # 2. Нижние фракталы ▼
        if down_mask.any():
            dn_bars = confirmed[down_mask]
            dn_x = dn_bars["bar_idx"].values.astype(float)
            dn_y = dn_bars["low"].values.astype(float) - offset

            sp_dn = pg.ScatterPlotItem(
                x=dn_x, y=dn_y, symbol="t", size=9,
                pen=pg.mkPen(color="#5c1a1a", width=1),
                brush=pg.mkBrush(theme.FRACTAL_DOWN)
            )
            pi.addItem(sp_dn)
            self._chart_items.append(sp_dn)

    def render_plateaus(self, df_candles):
        """
        Отрисовывает линии плато (одинаковые экстремумы соседних баров):
        - Ярко-зеленые горизонтальные отрезки на уровне High соседних баров (вверх)
        - Ярко-оранжевые горизонтальные отрезки на уровне Low соседних баров (вниз)
        """
        show_high = self.visibility.get("plateau_high", True)
        show_low = self.visibility.get("plateau_low", True)
        if not show_high and not show_low:
            return

        if df_candles is None or len(df_candles) < 2:
            return

        pi = self.getPlotItem()
        n = len(df_candles)
        highs = df_candles["high"].values
        lows = df_candles["low"].values
        bar_indices = df_candles["bar_idx"].values if "bar_idx" in df_candles.columns else np.arange(n)

        pen_high = pg.mkPen(color=theme.PLATEAU_HIGH_LINE, width=2.5)
        pen_high.setCosmetic(True)
        pen_low = pg.mkPen(color=theme.PLATEAU_LOW_LINE, width=2.5)
        pen_low.setCosmetic(True)

        # 1. Плато по High (ярко-зеленые линии)
        if show_high:
            i = 1
            while i < n:
                if highs[i] == highs[i - 1] and highs[i] > 0:
                    start_i = i - 1
                    while i < n and highs[i] == highs[start_i]:
                        i += 1
                    end_i = i - 1
                    x_start = float(bar_indices[start_i]) - 0.35
                    x_end = float(bar_indices[end_i]) + 0.35
                    p = float(highs[start_i])
                    line = pg.PlotCurveItem(x=[x_start, x_end], y=[p, p], pen=pen_high)
                    pi.addItem(line)
                    self._chart_items.append(line)
                else:
                    i += 1

        # 2. Плато по Low (ярко-оранжевые линии)
        if show_low:
            i = 1
            while i < n:
                if lows[i] == lows[i - 1] and lows[i] > 0:
                    start_i = i - 1
                    while i < n and lows[i] == lows[start_i]:
                        i += 1
                    end_i = i - 1
                    x_start = float(bar_indices[start_i]) - 0.35
                    x_end = float(bar_indices[end_i]) + 0.35
                    p = float(lows[start_i])
                    line = pg.PlotCurveItem(x=[x_start, x_end], y=[p, p], pen=pen_low)
                    pi.addItem(line)
                    self._chart_items.append(line)
                else:
                    i += 1

    def _draw_corridor_channel(
        self, pi, upper_events, lower_events, bar_indices, last_bar_x,
        pen_upper_color, pen_lower_color, fill_rgba,
        show_upper, show_lower, show_fill
    ):
        """Отрисовывает один коридор (ступенчатые границы и заливку)."""
        if not show_upper and not show_lower and not show_fill:
            return

        def build_step_arrays(events, is_high):
            if not events:
                return np.array([]), np.array([])
            res = {}
            for b_idx, p in events:
                if b_idx not in res:
                    res[b_idx] = p
                else:
                    res[b_idx] = max(res[b_idx], p) if is_high else min(res[b_idx], p)
            sorted_ev = sorted(res.items(), key=lambda x: x[0])

            x_out = []
            y_out = []

            first_b, first_p = sorted_ev[0]
            start_x = float(bar_indices[0]) - 0.45
            x_out.extend([start_x, first_b])
            y_out.extend([first_p, first_p])

            prev_b = first_b
            prev_p = first_p

            for k in range(1, len(sorted_ev)):
                b_idx, p = sorted_ev[k]
                if p == prev_p:
                    prev_b = b_idx
                    continue

                gap = b_idx - prev_b
                if gap > 1.0:
                    # Есть промежуток между сигналами -> скос от предыдущей свечи (b_idx - 1) к новому уровню (b_idx) как в TW
                    x_out.append(b_idx - 1.0)
                    y_out.append(prev_p)
                    x_out.append(b_idx)
                    y_out.append(p)
                else:
                    # Нет промежутка (соседние свечи или плато сразу перед фракталом) -> строго вертикальная линия на b_idx
                    x_out.append(b_idx)
                    y_out.append(prev_p)
                    x_out.append(b_idx)
                    y_out.append(p)

                prev_b = b_idx
                prev_p = p

            # Продлеваем последнюю полку до конца графика
            x_out.append(last_bar_x)
            y_out.append(prev_p)

            return np.array(x_out), np.array(y_out)

        curve_u = None
        curve_l = None

        if upper_events and (show_upper or show_fill):
            xu, yu = build_step_arrays(upper_events, True)
            if len(xu) > 0:
                pen_u = pg.mkPen(color=pen_upper_color, width=1.5)
                pen_u.setCosmetic(True)
                curve_u = pg.PlotCurveItem(x=xu, y=yu, pen=pen_u if show_upper else None)
                pi.addItem(curve_u)
                self._chart_items.append(curve_u)

        if lower_events and (show_lower or show_fill):
            xl, yl = build_step_arrays(lower_events, False)
            if len(xl) > 0:
                pen_l = pg.mkPen(color=pen_lower_color, width=1.5)
                pen_l.setCosmetic(True)
                curve_l = pg.PlotCurveItem(x=xl, y=yl, pen=pen_l if show_lower else None)
                pi.addItem(curve_l)
                self._chart_items.append(curve_l)

        # Полупрозрачная деликатная заливка коридора
        if show_fill and curve_u is not None and curve_l is not None:
            fill_item = pg.FillBetweenItem(curve_l, curve_u, brush=pg.mkBrush(*fill_rgba))
            pi.addItem(fill_item)
            self._chart_items.append(fill_item)

    def render_signal_corridor(self, df_candles):
        """
        Отрисовывает 5 разновидностей каналов (коридоров):
        0. «Фракталы и плато» (Оранжевый) - авторский тактический микро-канал.
        1. «Классика Вильямса» (Зеленый) - мировой стандарт, только подтвержденные фракталы Вильямса.
        2. «Диапазонный» (Фиолетовый) - Fractal Envelope, удерживает границы боковика без схлопывания.
        3. «Структурный» (Синий) - крупный макро-канал по ключевым свингам слома структуры (CHoCH).
        4. «Вильямс с расширением плато» (Бирюзовый) - фрактальный канал с расширением диапазона за счет внешних плато.
        """
        # Фильтры видимости Канала 0 (Оранжевый: Фракталы и плато)
        ch0_u = self.visibility.get("ch0_orange_upper", True)
        ch0_l = self.visibility.get("ch0_orange_lower", True)
        ch0_f = self.visibility.get("ch0_orange_fill", True)

        # Фильтры видимости Канала 1 (Зеленый: Классика Вильямса)
        ch1_u = self.visibility.get("ch1_green_upper", True)
        ch1_l = self.visibility.get("ch1_green_lower", True)
        ch1_f = self.visibility.get("ch1_green_fill", True)

        # Фильтры видимости Канала 2 (Фиолетовый: Диапазонный)
        ch2_u = self.visibility.get("ch2_purple_upper", True)
        ch2_l = self.visibility.get("ch2_purple_lower", True)
        ch2_f = self.visibility.get("ch2_purple_fill", True)

        # Фильтры видимости Канала 3 (Синий: Структурный)
        ch3_u = self.visibility.get("ch3_blue_upper", True)
        ch3_l = self.visibility.get("ch3_blue_lower", True)
        ch3_f = self.visibility.get("ch3_blue_fill", True)

        # Фильтры видимости Канала 4 (Бирюзовый: Вильямс с расширением плато)
        ch4_u = self.visibility.get("ch4_cyan_upper", True)
        ch4_l = self.visibility.get("ch4_cyan_lower", True)
        ch4_f = self.visibility.get("ch4_cyan_fill", True)

        any_ch0 = ch0_u or ch0_l or ch0_f
        any_ch1 = ch1_u or ch1_l or ch1_f
        any_ch2 = ch2_u or ch2_l or ch2_f
        any_ch3 = ch3_u or ch3_l or ch3_f
        any_ch4 = ch4_u or ch4_l or ch4_f

        if not any_ch0 and not any_ch1 and not any_ch2 and not any_ch3 and not any_ch4:
            return

        if df_candles is None or len(df_candles) < 3:
            return

        pi = self.getPlotItem()
        n = len(df_candles)
        highs = df_candles["high"].values
        lows = df_candles["low"].values
        bar_indices = df_candles["bar_idx"].values if "bar_idx" in df_candles.columns else np.arange(n)

        has_f_up = "fractal_up" in df_candles.columns
        has_f_down = "fractal_down" in df_candles.columns
        f_up_vals = df_candles["fractal_up"].values if has_f_up else None
        f_down_vals = df_candles["fractal_down"].values if has_f_down else None

        # События для 5 каналов
        ch0_upper_events, ch0_lower_events = [], []
        ch1_upper_events, ch1_lower_events = [], []
        ch2_upper_events, ch2_lower_events = [], []
        ch3_upper_events, ch3_lower_events = [], []
        ch4_upper_events, ch4_lower_events = [], []

        last_high = None
        last_low = None
        current_trend = None

        # Для Диапазонного канала (держит границы боковика)
        env_high = None
        env_low = None

        # Для Канала 4 (Вильямс с расширением за счет внешних плато)
        ch4_cur_high = None
        ch4_cur_low = None

        for i in range(n):
            c_high = float(highs[i])
            c_low = float(lows[i])

            # 1. Williams fractals (подтвержден на баре i, пик на i-2)
            if i >= 2 and f_up_vals is not None and not np.isnan(f_up_vals[i - 2]):
                p = float(f_up_vals[i - 2])
                b_idx = float(bar_indices[i - 2])
                # Канал 0 (Фракталы и плато) и Канал 1 (Классика Вильямса)
                ch0_upper_events.append((b_idx, p))
                ch1_upper_events.append((b_idx, p))
                last_high = {"price": p, "i": i - 2}

                # Канал 4 (Вильямс с расширением плато): базовый уровень фрактала
                ch4_cur_high = p
                ch4_upper_events.append((b_idx, ch4_cur_high))

                # Канал 2 (Диапазонный): расширяет верх при новом максимуме
                if env_high is None or p >= env_high:
                    env_high = p
                    ch2_upper_events.append((b_idx, env_high))

            if i >= 2 and f_down_vals is not None and not np.isnan(f_down_vals[i - 2]):
                p = float(f_down_vals[i - 2])
                b_idx = float(bar_indices[i - 2])
                # Канал 0 (Фракталы и плато) и Канал 1 (Классика Вильямса)
                ch0_lower_events.append((b_idx, p))
                ch1_lower_events.append((b_idx, p))
                last_low = {"price": p, "i": i - 2}

                # Канал 4 (Вильямс с расширением плато): базовый уровень фрактала
                ch4_cur_low = p
                ch4_lower_events.append((b_idx, ch4_cur_low))

                # Канал 2 (Диапазонный): расширяет низ при новом минимуме
                if env_low is None or p <= env_low:
                    env_low = p
                    ch2_lower_events.append((b_idx, env_low))

            # 2. Плато
            if i >= 1:
                if highs[i] == highs[i - 1] and highs[i] > 0:
                    p = float(highs[i])
                    b_idx = float(bar_indices[i - 1])
                    # Канал 0: принимает любые плато
                    ch0_upper_events.append((b_idx, p))
                    last_high = {"price": p, "i": i - 1}

                    # Канал 4: расширяется только если плато ВЫШЕ текущей верхней границы
                    if ch4_cur_high is None or p > ch4_cur_high:
                        ch4_cur_high = p
                        ch4_upper_events.append((b_idx, ch4_cur_high))

                if lows[i] == lows[i - 1] and lows[i] > 0:
                    p = float(lows[i])
                    b_idx = float(bar_indices[i - 1])
                    # Канал 0: принимает любые плато
                    ch0_lower_events.append((b_idx, p))
                    last_low = {"price": p, "i": i - 1}

                    # Канал 4: расширяется только если плато НИЖЕ текущей нижней границы
                    if ch4_cur_low is None or p < ch4_cur_low:
                        ch4_cur_low = p
                        ch4_lower_events.append((b_idx, ch4_cur_low))

            # 3. CHoCH (Слом структуры)
            if last_low and c_low < last_low["price"] and current_trend != "BEAR":
                s_i = last_low["i"]
                window = highs[s_i : i + 1]
                if len(window) > 0:
                    rel_max = int(np.argmax(window))
                    peak_bar = float(bar_indices[s_i + rel_max])
                    peak_val = float(window[rel_max])

                    # Канал 3 (Структурный): свинг-хай при сломе вниз
                    ch3_upper_events.append((peak_bar, peak_val))

                    # Канал 2 (Диапазонный): при сломе структуры вниз верхняя граница переносится на свинг-хай
                    env_high = peak_val
                    ch2_upper_events.append((peak_bar, env_high))

                current_trend = "BEAR"

            elif last_high and c_high > last_high["price"] and current_trend != "BULL":
                s_i = last_high["i"]
                window = lows[s_i : i + 1]
                if len(window) > 0:
                    rel_min = int(np.argmin(window))
                    trough_bar = float(bar_indices[s_i + rel_min])
                    trough_val = float(window[rel_min])

                    # Канал 3 (Структурный): свинг-лоу при сломе вверх
                    ch3_lower_events.append((trough_bar, trough_val))

                    # Канал 2 (Диапазонный): при сломе структуры вверх нижняя граница переносится на свинг-лоу
                    env_low = trough_val
                    ch2_lower_events.append((trough_bar, env_low))

                current_trend = "BULL"

        last_bar_x = float(bar_indices[-1]) + 0.45

        # 0. Отрисовка Канала 0 (Оранжевый: Фракталы и плато)
        if any_ch0:
            self._draw_corridor_channel(
                pi, ch0_upper_events, ch0_lower_events, bar_indices, last_bar_x,
                theme.CH0_ORANGE_UPPER, theme.CH0_ORANGE_LOWER, theme.CH0_ORANGE_FILL,
                ch0_u, ch0_l, ch0_f
            )

        # 1. Отрисовка Канала 1 (Зеленый: Классика Вильямса)
        if any_ch1:
            self._draw_corridor_channel(
                pi, ch1_upper_events, ch1_lower_events, bar_indices, last_bar_x,
                theme.CH1_GREEN_UPPER, theme.CH1_GREEN_LOWER, theme.CH1_GREEN_FILL,
                ch1_u, ch1_l, ch1_f
            )

        # 2. Отрисовка Канала 2 (Фиолетовый: Диапазонный)
        if any_ch2:
            self._draw_corridor_channel(
                pi, ch2_upper_events, ch2_lower_events, bar_indices, last_bar_x,
                theme.CH2_PURPLE_UPPER, theme.CH2_PURPLE_LOWER, theme.CH2_PURPLE_FILL,
                ch2_u, ch2_l, ch2_f
            )

        # 3. Отрисовка Канала 3 (Синий: Структурный)
        if any_ch3:
            self._draw_corridor_channel(
                pi, ch3_upper_events, ch3_lower_events, bar_indices, last_bar_x,
                theme.CH3_BLUE_UPPER, theme.CH3_BLUE_LOWER, theme.CH3_BLUE_FILL,
                ch3_u, ch3_l, ch3_f
            )

        # 4. Отрисовка Канала 4 (Бирюзовый: Вильямс с расширением плато)
        if any_ch4:
            self._draw_corridor_channel(
                pi, ch4_upper_events, ch4_lower_events, bar_indices, last_bar_x,
                theme.CH4_CYAN_UPPER, theme.CH4_CYAN_LOWER, theme.CH4_CYAN_FILL,
                ch4_u, ch4_l, ch4_f
            )

    def render_fractal_levels(self, levels, df_candles):
        """
        Отрисовывает горизонтальные пунктирные линии фракталов с бейджами.
        Линия тянется от момента появления до снятия (или до текущей свечи).
        """
        if not self.visibility.get("fractal_levels", True):
            return

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

            # Фильтр "Только активные в памяти" (скрыть забытые / пробитые)
            if self.visibility.get("levels_active_only", False):
                if et < curr_time:
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
            if self.visibility.get("level_labels", True):
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

    def render_structure_breaks(self, df_candles):
        """
        Отрисовывает сигналы слома структуры (CHoCH):
        - Горизонтальная полка уровня (от бара образования свинга до бара слома).
        - Стрелка слома (▲/▼) с бейджем CHoCH в момент пробоя.
        """
        show_shelves = self.visibility.get("choch_shelves", True)
        show_arrows = self.visibility.get("choch_arrows", True)
        if not show_shelves and not show_arrows:
            return

        if df_candles is None or len(df_candles) < 3:
            return

        pi = self.getPlotItem()
        n = len(df_candles)

        pen_bull_shelf = pg.mkPen(color="#00e5ff", width=1.5, style=Qt.PenStyle.DashLine)
        pen_bull_shelf.setCosmetic(True)
        pen_bear_shelf = pg.mkPen(color="#ff5252", width=1.5, style=Qt.PenStyle.DashLine)
        pen_bear_shelf.setCosmetic(True)

        badge_font = QFont("Tahoma", 8, QFont.Weight.Bold)

        highs = df_candles["high"].values
        lows = df_candles["low"].values
        has_f_up = "fractal_up" in df_candles.columns
        has_f_down = "fractal_down" in df_candles.columns
        f_up_vals = df_candles["fractal_up"].values if has_f_up else None
        f_down_vals = df_candles["fractal_down"].values if has_f_down else None
        bar_indices = df_candles["bar_idx"].values if "bar_idx" in df_candles.columns else np.arange(n)

        last_high = None
        last_low = None
        current_trend = None

        for i in range(n):
            c_high = float(highs[i])
            c_low = float(lows[i])
            i_x = float(bar_indices[i])

            # 1. Обновление подтвержденных свингов (фрактал 2 бара назад)
            if i >= 2 and f_up_vals is not None and not np.isnan(f_up_vals[i - 2]):
                last_high = {"price": float(f_up_vals[i - 2]), "bar_idx": float(bar_indices[i - 2])}
            if i >= 2 and f_down_vals is not None and not np.isnan(f_down_vals[i - 2]):
                last_low = {"price": float(f_down_vals[i - 2]), "bar_idx": float(bar_indices[i - 2])}

            # Плато (равенство цен соседних баров)
            if i >= 1:
                if highs[i] == highs[i - 1]:
                    last_high = {"price": float(highs[i]), "bar_idx": float(bar_indices[i - 1])}
                if lows[i] == lows[i - 1]:
                    last_low = {"price": float(lows[i]), "bar_idx": float(bar_indices[i - 1])}

            # 2. Проверка слома структуры
            # Медвежий слом (BEAR CHoCH): пробой последнего Low вниз
            if last_low and c_low < last_low["price"] and current_trend != "BEAR":
                p_lvl = last_low["price"]
                s_idx = last_low["bar_idx"]

                # Рисуем полку от бара образования до бара слома
                if show_shelves:
                    shelf_line = pg.PlotCurveItem(x=[s_idx, i_x + 0.35], y=[p_lvl, p_lvl], pen=pen_bear_shelf)
                    pi.addItem(shelf_line)
                    self._chart_items.append(shelf_line)

                # Рисуем стрелку вниз и плашку
                if show_arrows:
                    sp_arrow = pg.ScatterPlotItem(
                        x=[i_x], y=[p_lvl], symbol="t", size=10,
                        pen=pg.mkPen(color="#ffffff", width=1),
                        brush=pg.mkBrush("#ff5252")
                    )
                    pi.addItem(sp_arrow)
                    self._chart_items.append(sp_arrow)

                    lbl = pg.TextItem(text="CHoCH ▼", color="#ffffff", fill=pg.mkBrush("#5a1818"), anchor=(0.5, 1.4))
                    lbl.setFont(badge_font)
                    lbl.setPos(i_x, p_lvl)
                    pi.addItem(lbl)
                    self._chart_items.append(lbl)

                current_trend = "BEAR"

            # Бычий слом (BULL CHoCH): пробой последнего High вверх
            elif last_high and c_high > last_high["price"] and current_trend != "BULL":
                p_lvl = last_high["price"]
                s_idx = last_high["bar_idx"]

                # Рисуем полку от бара образования до бара слома
                if show_shelves:
                    shelf_line = pg.PlotCurveItem(x=[s_idx, i_x + 0.35], y=[p_lvl, p_lvl], pen=pen_bull_shelf)
                    pi.addItem(shelf_line)
                    self._chart_items.append(shelf_line)

                # Рисуем стрелку вверх и плашку
                if show_arrows:
                    sp_arrow = pg.ScatterPlotItem(
                        x=[i_x], y=[p_lvl], symbol="t1", size=10,
                        pen=pg.mkPen(color="#ffffff", width=1),
                        brush=pg.mkBrush("#00e5ff")
                    )
                    pi.addItem(sp_arrow)
                    self._chart_items.append(sp_arrow)

                    lbl = pg.TextItem(text="CHoCH ▲", color="#ffffff", fill=pg.mkBrush("#103b4d"), anchor=(0.5, -0.4))
                    lbl.setFont(badge_font)
                    lbl.setPos(i_x, p_lvl)
                    pi.addItem(lbl)
                    self._chart_items.append(lbl)

                current_trend = "BULL"

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

        # Фильтруем сделки, попадающие во временной срез и настройки видимости
        filtered_trades = []
        for tr in trades:
            t = np.datetime64(tr["entry_time"])
            if t > curr_time:
                continue

            idx = int(np.searchsorted(c_times, t, side="right")) - 1
            idx = max(0, min(idx, n_bars - 1))

            is_real = tr["is_real"]

            # Фильтрация по результату
            if is_real:
                close_reason = tr.get("close_reason")
                if close_reason == "TP" and not self.visibility.get("filter_profitable", True):
                    continue
                if close_reason == "SL" and not self.visibility.get("filter_loss", True):
                    continue
            else:
                close_reason = tr.get("close_reason")
                if close_reason == "TP" and not self.visibility.get("virt_filter_profitable", True):
                    continue
                if close_reason == "SL" and not self.visibility.get("virt_filter_loss", True):
                    continue
                if (not self.visibility.get("virt_trades", True)
                        and not self.visibility.get("virt_attempts", True)
                        and not self.visibility.get("virt_sl", True)
                        and not self.visibility.get("virt_tp", True)):
                    continue

            filtered_trades.append((idx, tr))

        # Группируем сделки по свече и направлению: на одну свечу — строго одна стрелка, одно число и один вектор
        from collections import defaultdict
        grouped_trades = defaultdict(list)
        for idx, tr in filtered_trades:
            grouped_trades[(idx, tr["direction"])].append(tr)

        for (idx, direction), bar_trades in grouped_trades.items():
            # Берем последнюю (результирующую) сделку этой свечи
            tr = bar_trades[-1]
            p = tr["entry_price"]
            is_real = tr["is_real"]
            attempt = tr.get("attempt", len(bar_trades))

            # Отрисовка стрелки и номера перезахода: строго одна стрелка и одно число на свечу
            if direction == "BUY":
                x_pos = idx - 0.22
                if is_real:
                    if self.visibility.get("real_trades", True):
                        rb_x.append(x_pos)
                        rb_y.append(p)
                    lbl_col = "#2ecc71"
                    show_att = self.visibility.get("real_attempts", True)
                else:
                    if self.visibility.get("virt_trades", True):
                        vb_x.append(x_pos)
                        vb_y.append(p)
                    lbl_col = "#f1c40f"
                    show_att = self.visibility.get("virt_attempts", True)

                # Одно общее число перезахода под стрелкой
                if show_att:
                    lbl = pg.TextItem(text=f"#{attempt}", color=lbl_col, anchor=(0.5, -0.4))
                    lbl.setFont(att_font)
                    lbl.setPos(x_pos, p)
                    pi.addItem(lbl)
                    self._chart_items.append(lbl)

            else:
                x_pos = idx + 0.22
                if is_real:
                    if self.visibility.get("real_trades", True):
                        rs_x.append(x_pos)
                        rs_y.append(p)
                    lbl_col = "#e74c3c"
                    show_att = self.visibility.get("real_attempts", True)
                else:
                    if self.visibility.get("virt_trades", True):
                        vs_x.append(x_pos)
                        vs_y.append(p)
                    lbl_col = "#9b59b6"
                    show_att = self.visibility.get("virt_attempts", True)

                # Одно общее число перезахода над стрелкой
                if show_att:
                    lbl = pg.TextItem(text=f"#{attempt}", color=lbl_col, anchor=(0.5, 1.4))
                    lbl.setFont(att_font)
                    lbl.setPos(x_pos, p)
                    pi.addItem(lbl)
                    self._chart_items.append(lbl)

            # Отрисовка линий SL и TP (для результирующей сделки свечи)
            if tr.get("sl") and tr.get("tp"):
                sl_price = tr["sl"]
                tp_price = tr["tp"]
                
                # Конечная точка линии (момент закрытия сделки или текущее время)
                if tr.get("close_time"):
                    close_np = np.datetime64(tr["close_time"])
                    eff_close = min(close_np, curr_time)
                else:
                    eff_close = curr_time

                idx_close = int(np.searchsorted(c_times, eff_close, side="right")) - 1
                idx_close = max(idx, min(idx_close, n_bars - 1))
                x_end = max(idx + 0.6, float(idx_close))

                show_sl = self.visibility.get("real_sl", True) if is_real else self.visibility.get("virt_sl", True)
                show_tp = self.visibility.get("real_tp", True) if is_real else self.visibility.get("virt_tp", True)

                # Линия Stop Loss
                if show_sl:
                    line_sl = pg.PlotCurveItem(x=[idx, x_end], y=[sl_price, sl_price], pen=pen_sl)
                    pi.addItem(line_sl)
                    self._chart_items.append(line_sl)

                # Линия Take Profit
                if show_tp:
                    line_tp = pg.PlotCurveItem(x=[idx, x_end], y=[tp_price, tp_price], pen=pen_tp)
                    pi.addItem(line_tp)
                    self._chart_items.append(line_tp)

                # Векторные стрелки Брекета (к TP и к SL) — ровно одна стрелка на свечу
                show_vectors = self.visibility.get("real_vectors", True) if is_real else self.visibility.get("virt_vectors", True)
                if show_vectors:
                    x_vec_end = max(float(idx) + 0.45, float(idx_close))
                    close_reason = tr.get("close_reason")
                    is_closed_now = tr.get("close_time") is not None and np.datetime64(tr["close_time"]) <= curr_time

                    if is_real:
                        if not is_closed_now:
                            tp_col = "#2ecc71"
                            sl_col = "#e74c3c"
                            tp_w, sl_w = 1.5, 1.5
                            tp_hs, sl_hs = 9, 9
                        elif close_reason == "TP":
                            tp_col = "#2ecc71"
                            sl_col = "#5a2020"
                            tp_w, sl_w = 2.0, 1.2
                            tp_hs, sl_hs = 11, 8
                        else:
                            tp_col = "#7f8d7b"
                            sl_col = "#e74c3c"
                            tp_w, sl_w = 1.2, 2.0
                            tp_hs, sl_hs = 8, 11
                    else:
                        base_virt_col = "#f1c40f" if direction == "BUY" else "#9b59b6"
                        dim_virt_col = "#8c8452" if direction == "BUY" else "#6d5b75"

                        if not is_closed_now:
                            tp_col = base_virt_col
                            sl_col = "#e74c3c"
                            tp_w, sl_w = 1.5, 1.5
                            tp_hs, sl_hs = 9, 9
                        elif close_reason == "TP":
                            tp_col = base_virt_col
                            sl_col = "#5a2020"
                            tp_w, sl_w = 2.0, 1.2
                            tp_hs, sl_hs = 11, 8
                        else:
                            tp_col = dim_virt_col
                            sl_col = "#e74c3c"
                            tp_w, sl_w = 1.2, 2.0
                            tp_hs, sl_hs = 8, 11

                    vec_tp = TradeVectorItem(idx, p, x_vec_end, tp_price, tp_col, width=tp_w, head_size=tp_hs)
                    pi.addItem(vec_tp)
                    self._chart_items.append(vec_tp)

                    vec_sl = TradeVectorItem(idx, p, x_vec_end, sl_price, sl_col, width=sl_w, head_size=sl_hs)
                    pi.addItem(vec_sl)
                    self._chart_items.append(vec_sl)

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
