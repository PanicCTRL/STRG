"""
gui_window.py
Главное окно STRG:
- Интерактивный график свечей по центру (pyqtgraph в стиле QUIK)
- Полнофункциональный Market Replayer внизу под графиком:
  * Кнопки: [ ⏹ В начало ] [ ⏮ Шаг ] [ ▶ Старт / ⏸ Пауза ] [ ⏭ Шаг ]
  * Слайдер-скруббер времени по всему торговому дню
  * Переключение скоростей (1x, 5x, 25x, 100x, MAX)
  * Табло текущего времени (HH:MM:SS) и цены
  * Горячая клавиша: Пробел
- Исполнение Lua-стратегий через lupa
- Точная отрисовка уровней фракталов, стрелок сделок с номерами попыток (#1..#4) и линий SL/TP
"""

import os
import json
import glob
import re
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QButtonGroup, QSlider, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QComboBox, QFileDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
import theme
from chart_canvas import ChartCanvas
from tick_aggregator import TickAggregator
from lua_runner import LuaStrategyRunner

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("STRG — Strategy Monitor & Market Replayer")
        self.resize(1280, 780)

        # Движок данных
        saved_settings = self.load_settings()
        self.current_tf = saved_settings.get("current_tf", "5M")
        saved_file = saved_settings.get("current_file", "Y:/MXU6_260901_260901.txt")
        self.default_file = saved_file if os.path.exists(saved_file) else "Y:/MXU6_260901_260901.txt"
        self.aggregator = TickAggregator(self.default_file)
        self.df_candles_full = pd.DataFrame()

        # Исполнитель Lua-стратегии
        saved_strat = saved_settings.get("current_strategy", r"Y:\opening_strategy\mock_opening.lua")
        self.strategy_file = saved_strat if os.path.exists(saved_strat) else r"Y:\opening_strategy\mock_opening.lua"
        self.runner = LuaStrategyRunner(self.strategy_file)
        self.last_trades = []
        self.last_levels = []
        self.last_stats = {}
        self._ticks_loaded = False

        # Состояние плеера
        self.is_playing = False
        self.current_tick_idx = 0
        self.speed_multiplier = 25
        self.replay_timer = QTimer(self)
        self.replay_timer.setInterval(40)  # ~25 FPS
        self.replay_timer.timeout.connect(self._on_replay_timer_tick)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # 1. Левая/Центральная часть: Тулбар + График + Плеер + Статус
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)

        # Верхний тулбар
        self.top_toolbar = self._create_quik_top_toolbar()
        left_layout.addWidget(self.top_toolbar)

        # Графический холст
        self.chart_canvas = ChartCanvas()
        left_layout.addWidget(self.chart_canvas, stretch=1)

        # ПЛЕЕР ПОД ГРАФИКОМ
        self.replayer_panel = self._create_replayer_panel()
        left_layout.addWidget(self.replayer_panel)

        # Нижняя статусная полоска
        self.status_bar = self._create_bottom_bar()
        left_layout.addLayout(self.status_bar)

        root_layout.addWidget(left_container, stretch=1)

        # 2. Правая панель управления (155px)
        self.right_panel = self._create_right_panel()
        root_layout.addWidget(self.right_panel)

        # Применяем настройки видимости к холсту
        self._apply_tree_visibility()

        # Первичная загрузка
        self.load_and_render(reload_lua=True, auto_range=True)

    def _create_quik_top_toolbar(self):
        """Создает компактную верхнюю полоску с кнопками в стиле QUIK."""
        bar = QFrame()
        bar.setObjectName("TopToolbar")
        bar.setFixedHeight(26)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        self.lbl_inst = QLabel("MIX-9.26 [5 минут]")
        self.lbl_inst.setStyleSheet("font-size: 11px; font-weight: bold; color: #aaaaaa; padding-right: 6px; border: none;")
        layout.addWidget(self.lbl_inst)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setStyleSheet("color: #333333; max-width: 1px;")
        layout.addWidget(sep0)

        # Выбор торгового дня (тиковый файл)
        self.combo_days = QComboBox()
        self.combo_days.setObjectName("ComboDays")
        self.combo_days.setToolTip("Выбор торгового дня (тиковый файл)")
        self.combo_days.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.combo_days)

        self.btn_browse = QPushButton("📁")
        self.btn_browse.setObjectName("BtnBrowseDay")
        self.btn_browse.setToolTip("Открыть файл торгового дня через проводник...")
        self.btn_browse.setFixedWidth(24)
        self.btn_browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_browse.clicked.connect(self._on_browse_file)
        layout.addWidget(self.btn_browse)

        self._populate_day_selector()
        self.combo_days.currentIndexChanged.connect(self._on_day_changed)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #333333; max-width: 1px;")
        layout.addWidget(sep)

        tools = [
            ("⟲ Сброс", "Автоподгонка масштаба"),
            ("🔍+", "Приблизить"),
            ("🔍-", "Отдалить"),
            ("📈 Тренд", "Линия тренда"),
            ("水平 Гориз.", "Горизонтальная линия"),
            ("📏 Линейка", "Измерение пунктов и баров"),
        ]

        for text, tooltip in tools:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, t=text: self.on_top_btn_clicked(t))
            layout.addWidget(btn)

        sep_tf = QFrame()
        sep_tf.setFrameShape(QFrame.Shape.VLine)
        sep_tf.setStyleSheet("color: #333333; max-width: 1px;")
        layout.addWidget(sep_tf)

        lbl_tf = QLabel("ТФ:")
        lbl_tf.setStyleSheet("font-size: 10px; font-weight: bold; color: #777777; border: none; padding-left: 2px;")
        layout.addWidget(lbl_tf)

        self.combo_tf = QComboBox()
        self.combo_tf.setObjectName("ComboTf")
        self.combo_tf.setToolTip("Выбор таймфрейма свечей")
        self.combo_tf.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for tf_val in ["1M", "3M", "5M", "15M", "1H"]:
            self.combo_tf.addItem(tf_val)
        self.combo_tf.setCurrentText(self.current_tf)
        self.combo_tf.currentTextChanged.connect(self.on_tf_changed)
        layout.addWidget(self.combo_tf)

        layout.addStretch()

        lbl_quik_title = QLabel("QUIK [График]")
        lbl_quik_title.setStyleSheet("font-size: 10px; color: #555555; border: none;")
        layout.addWidget(lbl_quik_title)

        return bar

    def _create_replayer_panel(self):
        """Панель управления воспроизведением рынка под графиком."""
        panel = QFrame()
        panel.setObjectName("ReplayerPanel")
        panel.setFixedHeight(62)

        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(6)

        # 1. Сетка кнопок управления (2 ряда)
        btn_grid = QGridLayout()
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setSpacing(3)

        # Кнопка [ ⏹ В начало ] — занимает оба ряда
        self.btn_reset = QPushButton("⏹ В начало")
        self.btn_reset.setProperty("class", "ReplayBtn")
        self.btn_reset.setFixedWidth(88)
        self.btn_reset.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_reset.setToolTip("Перемотать в самое начало дня")
        self.btn_reset.clicked.connect(self.reset_replay)
        btn_grid.addWidget(self.btn_reset, 0, 0, 2, 1)

        # Ряд 0: Шаг назад (тики с изменением цены)
        self.btn_step_back = QPushButton("⏮ Шаг")
        self.btn_step_back.setProperty("class", "ReplayBtn")
        self.btn_step_back.setToolTip("Шаг назад (изменение цены)")
        self.btn_step_back.setFixedWidth(82)
        self.btn_step_back.clicked.connect(self.step_tick_backward)
        btn_grid.addWidget(self.btn_step_back, 0, 1)

        # Ряд 1: Свеча назад (свечи)
        self.btn_candle_back = QPushButton("⏮ Свеча")
        self.btn_candle_back.setProperty("class", "ReplayBtn")
        self.btn_candle_back.setToolTip("Свеча назад (на 1 свечу выбранного ТФ)")
        self.btn_candle_back.setFixedWidth(82)
        self.btn_candle_back.clicked.connect(self.step_candle_backward)
        btn_grid.addWidget(self.btn_candle_back, 1, 1)

        # Кнопка [ ▶ Старт ] — занимает оба ряда
        self.btn_play = QPushButton("▶ Старт")
        self.btn_play.setProperty("class", "ReplayBtn")
        self.btn_play.setFixedWidth(82)
        self.btn_play.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_play.setToolTip("Запуск / Пауза воспроизведения (Пробел)")
        self.btn_play.clicked.connect(self.toggle_play)
        btn_grid.addWidget(self.btn_play, 0, 2, 2, 1)

        # Ряд 0: Шаг вперед (тики с изменением цены)
        self.btn_step_fwd = QPushButton("⏭ Шаг")
        self.btn_step_fwd.setProperty("class", "ReplayBtn")
        self.btn_step_fwd.setToolTip("Шаг вперед (изменение цены)")
        self.btn_step_fwd.setFixedWidth(82)
        self.btn_step_fwd.clicked.connect(self.step_tick_forward)
        btn_grid.addWidget(self.btn_step_fwd, 0, 3)
        self.btn_step = self.btn_step_fwd  # Алиас

        # Ряд 1: Свеча вперед (свечи)
        self.btn_candle_fwd = QPushButton("⏭ Свеча")
        self.btn_candle_fwd.setProperty("class", "ReplayBtn")
        self.btn_candle_fwd.setToolTip("Свеча вперед (на 1 свечу выбранного ТФ)")
        self.btn_candle_fwd.setFixedWidth(82)
        self.btn_candle_fwd.clicked.connect(self.step_candle_forward)
        btn_grid.addWidget(self.btn_candle_fwd, 1, 3)

        main_layout.addLayout(btn_grid)

        # 2. Правая часть: сверху длинный слайдер, снизу время, цена и скорости
        right_box = QVBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(2)

        # Слайдер перемотки времени на всю ширину
        self.slider_time = QSlider(Qt.Orientation.Horizontal)
        self.slider_time.setMinimum(0)
        self.slider_time.setMaximum(100)
        self.slider_time.sliderMoved.connect(self.on_slider_moved)
        right_box.addWidget(self.slider_time)

        # Нижний ряд: цифровое табло + кнопки скоростей
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(5)

        # Табло времени и цены
        self.lbl_replay_time = QLabel("06:59:06")
        self.lbl_replay_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_replay_time.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #d4b106; background: #1a1708; "
            "border: 1px solid #4a3e0f; padding: 2px 6px; min-width: 65px;"
        )
        bottom_row.addWidget(self.lbl_replay_time)

        self.lbl_replay_price = QLabel("218 700")
        self.lbl_replay_price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_replay_price.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #e0e0e0; background: #202020; "
            "border: 1px solid #353535; padding: 2px 6px; min-width: 65px;"
        )
        bottom_row.addWidget(self.lbl_replay_price)

        bottom_row.addStretch()

        # Переключатели скорости
        self.speed_group = QButtonGroup(self)
        self.speed_buttons = {}

        for spd_val, spd_label in [(1, "1x"), (5, "5x"), (25, "25x"), (100, "100x"), (1000, "MAX")]:
            btn = QPushButton(spd_label)
            btn.setCheckable(True)
            btn.setProperty("class", "ReplayBtn")
            btn.setFixedWidth(42)
            btn.clicked.connect(lambda checked, s=spd_val: self.set_speed(s))
            self.speed_group.addButton(btn)
            bottom_row.addWidget(btn)
            self.speed_buttons[spd_val] = btn

        self.speed_buttons[25].setChecked(True)
        right_box.addLayout(bottom_row)

        main_layout.addLayout(right_box, stretch=1)

        return panel

    def _create_pnl_card(self, title):
        """Создает карточку PnL со структурой 2x2 как в TradingView-тестере."""
        card_box = QFrame()
        card_box.setObjectName("PnlCard")
        card_box.setStyleSheet(
            "QFrame#PnlCard { background-color: #161a1e; border: 1px solid #282f38; border-radius: 2px; padding: 4px; }"
        )

        box_layout = QVBoxLayout(card_box)
        box_layout.setContentsMargins(5, 4, 5, 5)
        box_layout.setSpacing(3)

        lbl_card_title = QLabel(title)
        lbl_card_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #8a9ba8; border: none;")
        box_layout.addWidget(lbl_card_title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)

        lbl_pos_cap = QLabel("ПОЗИЦИЯ")
        lbl_pos_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_pos_val = QLabel("0 (FLAT)")
        lbl_pos_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #cccccc; border: none;")

        lbl_unreal_cap = QLabel("ПЛАВАЮЩИЙ PnL")
        lbl_unreal_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_unreal_val = QLabel("0 пт")
        lbl_unreal_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

        lbl_entry_cap = QLabel("ЦЕНА ВХОДА")
        lbl_entry_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_entry_val = QLabel("-")
        lbl_entry_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #cccccc; border: none;")

        lbl_total_cap = QLabel("ИТОГО PnL ДНЯ")
        lbl_total_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_total_val = QLabel("0 пт")
        lbl_total_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

        grid.addWidget(lbl_pos_cap, 0, 0)
        grid.addWidget(lbl_unreal_cap, 0, 1)
        grid.addWidget(lbl_pos_val, 1, 0)
        grid.addWidget(lbl_unreal_val, 1, 1)

        grid.addWidget(lbl_entry_cap, 2, 0)
        grid.addWidget(lbl_total_cap, 2, 1)
        grid.addWidget(lbl_entry_val, 3, 0)
        grid.addWidget(lbl_total_val, 3, 1)

        lbl_cnt_cap = QLabel("СДЕЛОК")
        lbl_cnt_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_cnt_val = QLabel("0")
        lbl_cnt_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #cccccc; border: none;")

        lbl_res_cap = QLabel("ТЕЙК / СТОП")
        lbl_res_cap.setStyleSheet("font-size: 8.5px; font-weight: bold; color: #5a6e82; border: none;")
        lbl_res_val = QLabel("0 / 0")
        lbl_res_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

        grid.addWidget(lbl_cnt_cap, 4, 0)
        grid.addWidget(lbl_res_cap, 4, 1)
        grid.addWidget(lbl_cnt_val, 5, 0)
        grid.addWidget(lbl_res_val, 5, 1)

        box_layout.addLayout(grid)

        return {
            "frame": card_box,
            "lbl_pos": lbl_pos_val,
            "lbl_entry": lbl_entry_val,
            "lbl_unreal": lbl_unreal_val,
            "lbl_total": lbl_total_val,
            "lbl_trades": lbl_cnt_val,
            "lbl_result": lbl_res_val,
        }

    def _set_card_values(self, card, pos_text, entry_text, unreal_pnl, total_pnl, count_trades=0, count_tp=0, count_sl=0):
        """Обновляет значения и цвета в карточке PnL."""
        card["lbl_pos"].setText(pos_text)
        if "LONG" in pos_text:
            card["lbl_pos"].setStyleSheet("font-size: 11px; font-weight: bold; color: #52c41a; border: none;")
        elif "SHORT" in pos_text:
            card["lbl_pos"].setStyleSheet("font-size: 11px; font-weight: bold; color: #ef5350; border: none;")
        else:
            card["lbl_pos"].setStyleSheet("font-size: 11px; font-weight: bold; color: #cccccc; border: none;")

        card["lbl_entry"].setText(entry_text)

        # Плавающий PnL
        if unreal_pnl > 0:
            card["lbl_unreal"].setText(f"+{unreal_pnl:,} пт".replace(",", " "))
            card["lbl_unreal"].setStyleSheet("font-size: 11px; font-weight: bold; color: #52c41a; border: none;")
        elif unreal_pnl < 0:
            card["lbl_unreal"].setText(f"{unreal_pnl:,} пт".replace(",", " "))
            card["lbl_unreal"].setStyleSheet("font-size: 11px; font-weight: bold; color: #ef5350; border: none;")
        else:
            card["lbl_unreal"].setText("0 пт")
            card["lbl_unreal"].setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

        # Итого PnL дня
        if total_pnl > 0:
            card["lbl_total"].setText(f"+{total_pnl:,} пт".replace(",", " "))
            card["lbl_total"].setStyleSheet("font-size: 11px; font-weight: bold; color: #26a69a; border: none;")
        elif total_pnl < 0:
            card["lbl_total"].setText(f"{total_pnl:,} пт".replace(",", " "))
            card["lbl_total"].setStyleSheet("font-size: 11px; font-weight: bold; color: #ef5350; border: none;")
        else:
            card["lbl_total"].setText("0 пт")
            card["lbl_total"].setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

        # Количество сделок и результат Тейк / Стоп
        if "lbl_trades" in card:
            card["lbl_trades"].setText(str(count_trades))
        if "lbl_result" in card:
            card["lbl_result"].setText(f"{count_tp} / {count_sl}")
            if count_tp > count_sl:
                card["lbl_result"].setStyleSheet("font-size: 11px; font-weight: bold; color: #52c41a; border: none;")
            elif count_sl > count_tp:
                card["lbl_result"].setStyleSheet("font-size: 11px; font-weight: bold; color: #ef5350; border: none;")
            else:
                card["lbl_result"].setStyleSheet("font-size: 11px; font-weight: bold; color: #888888; border: none;")

    def _update_pnl_dashboard(self, curr_time, curr_price):
        """Динамический пересчет PnL для реальных (LONG) и виртуальных (SHORT) сделок."""
        if not hasattr(self, "real_pnl_card") or not hasattr(self, "virt_pnl_card"):
            return

        target_np = np.datetime64(curr_time)
        real_trades = [t for t in self.last_trades if t.get("is_real")]
        virt_trades = [t for t in self.last_trades if not t.get("is_real")]

        def calc_pnl(trades, fallback_dir="BUY"):
            closed_pnl = 0
            active_trade = None
            count_trades = 0
            count_tp = 0
            count_sl = 0

            for tr in trades:
                e_time = np.datetime64(tr["entry_time"])
                if e_time > target_np:
                    continue

                count_trades += 1
                c_time = np.datetime64(tr["close_time"]) if tr.get("close_time") else None
                direction = tr.get("direction", fallback_dir)
                entry_p = float(tr.get("entry_price", 0))

                if c_time is not None and c_time <= target_np:
                    close_p = float(tr.get("close_price", entry_p))
                    if direction == "BUY":
                        closed_pnl += (close_p - entry_p)
                    else:
                        closed_pnl += (entry_p - close_p)

                    reason = tr.get("close_reason")
                    if reason == "TP":
                        count_tp += 1
                    elif reason == "SL":
                        count_sl += 1
                else:
                    active_trade = tr

            if active_trade:
                direction = active_trade.get("direction", fallback_dir)
                entry_p = float(active_trade.get("entry_price", curr_price))
                pos_text = "+1 (LONG)" if direction == "BUY" else "-1 (SHORT)"
                entry_text = f"{int(entry_p):,} ".replace(",", " ")
                if direction == "BUY":
                    unrealized_pnl = curr_price - entry_p
                else:
                    unrealized_pnl = entry_p - curr_price
            else:
                pos_text = "0 (FLAT)"
                entry_text = "-"
                unrealized_pnl = 0

            total_pnl = closed_pnl + unrealized_pnl
            return pos_text, entry_text, int(unrealized_pnl), int(total_pnl), count_trades, count_tp, count_sl

        r_pos, r_entry, r_unreal, r_total, r_cnt, r_tp, r_sl = calc_pnl(real_trades, "BUY")
        self._set_card_values(self.real_pnl_card, r_pos, r_entry, r_unreal, r_total, r_cnt, r_tp, r_sl)

        v_pos, v_entry, v_unreal, v_total, v_cnt, v_tp, v_sl = calc_pnl(virt_trades, "SELL")
        self._set_card_values(self.virt_pnl_card, v_pos, v_entry, v_unreal, v_total, v_cnt, v_tp, v_sl)

        if hasattr(self, "lbl_total_trades"):
            tot = r_cnt + v_cnt
            self.lbl_total_trades.setText(f"{tot}")
            self.lbl_total_trades.setToolTip(
                f"Всего сделок: {tot}\nРеальных (LONG): {r_cnt} (Тейк: {r_tp} / Стоп: {r_sl})\n"
                f"Виртуальных (SHORT): {v_cnt} (Тейк: {v_tp} / Стоп: {v_sl})"
            )

    def _create_right_panel(self):
        """Создает правую панель управления в строгом стиле QUIK с прокруткой."""
        scroll = QScrollArea()
        scroll.setObjectName("RightPanelScroll")
        scroll.setFixedWidth(220)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("RightPanelContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Блок режимов
        lbl_mode_title = QLabel("РЕЖИМ")
        lbl_mode_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_mode_title)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(2)

        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}

        for mode_id, mode_label in [("MOCK", "МОК"), ("TEST", "ТЕСТ"), ("LIVE", "БОЙ")]:
            btn = QPushButton(mode_label)
            btn.setCheckable(True)
            btn.setProperty("class", "ModeBtn")
            btn.clicked.connect(lambda checked, m=mode_id: self.on_mode_clicked(m))
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
            self.mode_buttons[mode_id] = btn

        self.mode_buttons["TEST"].setChecked(True)
        layout.addLayout(mode_layout)

        layout.addSpacing(2)

        # Стратегия Lua
        lbl_strat_title = QLabel("СТРАТЕГИЯ LUA")
        lbl_strat_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_strat_title)

        strat_h_box = QHBoxLayout()
        strat_h_box.setSpacing(2)
        strat_h_box.setContentsMargins(0, 0, 0, 0)

        self.combo_strategy = QComboBox()
        self.combo_strategy.setObjectName("ComboStrategy")
        self.combo_strategy.setToolTip("Выбор торговой стратегии на Lua")
        self.combo_strategy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        strat_h_box.addWidget(self.combo_strategy, stretch=1)

        self.btn_browse_strat = QPushButton("📁")
        self.btn_browse_strat.setObjectName("BtnBrowseStrat")
        self.btn_browse_strat.setToolTip("Открыть файл стратегии (.lua) через проводник...")
        self.btn_browse_strat.setFixedWidth(24)
        self.btn_browse_strat.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_browse_strat.clicked.connect(self._on_browse_strategy)
        strat_h_box.addWidget(self.btn_browse_strat)

        layout.addLayout(strat_h_box)

        self._populate_strategy_selector()
        self.combo_strategy.currentIndexChanged.connect(self._on_strategy_changed)

        layout.addSpacing(2)

        # Управление
        lbl_ctrl_title = QLabel("УПРАВЛЕНИЕ")
        lbl_ctrl_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_ctrl_title)

        self.btn_refresh = QPushButton("🔄 Обновить")
        self.btn_refresh.setObjectName("BtnRefresh")
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        layout.addWidget(self.btn_refresh)

        self.btn_restart = QPushButton("⏮ В начало дня")
        self.btn_restart.setObjectName("BtnRestart")
        self.btn_restart.clicked.connect(self.reset_replay)
        layout.addWidget(self.btn_restart)

        self.btn_show_all = QPushButton("Показать все")
        self.btn_show_all.setObjectName("BtnShowAll")
        self.btn_show_all.clicked.connect(self.show_all)
        layout.addWidget(self.btn_show_all)

        layout.addSpacing(2)

        # Дерево слоев видимости
        lbl_layers_title = QLabel("ВИДИМОСТЬ СЛОЁВ")
        lbl_layers_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_layers_title)

        self.tree_visibility = self._create_visibility_tree()
        self.tree_visibility.setMinimumHeight(150)
        layout.addWidget(self.tree_visibility)

        layout.addSpacing(2)

        # Результат PnL
        lbl_res_title = QLabel("РЕЗУЛЬТАТ (PnL)")
        lbl_res_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_res_title)

        self.real_pnl_card = self._create_pnl_card("РЕАЛЬНАЯ (LONG)")
        layout.addWidget(self.real_pnl_card["frame"])

        self.virt_pnl_card = self._create_pnl_card("ВИРТУАЛЬНАЯ (SHORT)")
        layout.addWidget(self.virt_pnl_card["frame"])

        layout.addSpacing(2)

        # Статистика: Перезаходы и Всего сделок
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(4)

        # Колонка: Перезаходы
        col_att = QVBoxLayout()
        col_att.setSpacing(2)
        lbl_att_title = QLabel("ПЕРЕЗАХОДЫ")
        lbl_att_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        self.lbl_attempts = QLabel("4 / 4")
        self.lbl_attempts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_attempts.setStyleSheet(
            "background-color: #242010; color: #d4b106; font-size: 12px; font-weight: bold; "
            "padding: 4px; border: 1px solid #453c15;"
        )
        self.lbl_attempts.setToolTip("Оставшиеся попытки перезахода на текущем активном уровне (из 4)")
        col_att.addWidget(lbl_att_title)
        col_att.addWidget(self.lbl_attempts)

        # Колонка: Всего сделок
        col_trades = QVBoxLayout()
        col_trades.setSpacing(2)
        lbl_trades_title = QLabel("ВСЕГО СДЕЛОК")
        lbl_trades_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        self.lbl_total_trades = QLabel("0")
        self.lbl_total_trades.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_total_trades.setStyleSheet(
            "background-color: #101c24; color: #00b0ff; font-size: 12px; font-weight: bold; "
            "padding: 4px; border: 1px solid #1c3547;"
        )
        self.lbl_total_trades.setToolTip("Общее количество совершенных сделок к текущему моменту")
        col_trades.addWidget(lbl_trades_title)
        col_trades.addWidget(self.lbl_total_trades)

        stats_layout.addLayout(col_att)
        stats_layout.addLayout(col_trades)
        layout.addLayout(stats_layout)

        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def load_settings(self):
        """Загружает сохраненные настройки видимости и веток дерева из settings.json."""
        if not os.path.exists(SETTINGS_FILE):
            return {}
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Ошибка загрузки settings.json: {e}")
            return {}

    def save_settings(self):
        """Сохраняет настройки видимости и раскрытия веток дерева в settings.json."""
        if not hasattr(self, "tree_visibility"):
            return

        vis = {}
        expanded = {}

        def scan_checks(node):
            key = node.data(0, Qt.ItemDataRole.UserRole)
            if key:
                vis[key] = (node.checkState(0) != Qt.CheckState.Unchecked)
            for i in range(node.childCount()):
                scan_checks(node.child(i))

        def scan_expanded(node, path=""):
            node_text = node.text(0)
            current_path = f"{path}/{node_text}" if path else node_text
            if node.childCount() > 0:
                expanded[current_path] = node.isExpanded()
                for i in range(node.childCount()):
                    scan_expanded(node.child(i), current_path)

        for i in range(self.tree_visibility.topLevelItemCount()):
            top_item = self.tree_visibility.topLevelItem(i)
            scan_checks(top_item)
            scan_expanded(top_item)

        data = {
            "current_file": self.default_file,
            "current_tf": self.current_tf,
            "current_strategy": self.strategy_file,
            "visibility": vis,
            "tree_expanded": expanded,
        }

        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Ошибка сохранения settings.json: {e}")

    def _create_visibility_tree(self):
        """Создает дерево слоев видимости с чекбоксами и ветками."""
        tree = QTreeWidget()
        tree.setObjectName("VisibilityTree")
        tree.setHeaderHidden(True)
        tree.setIndentation(13)

        saved_settings = self.load_settings()
        saved_vis = saved_settings.get("visibility", {})
        saved_expanded = saved_settings.get("tree_expanded", {})

        tree_data = [
            {
                "text": "Базовый график",
                "children": [
                    {"text": "Свечи (OHLC)", "key": "candles", "default": True},
                    {"text": "Текущая цена", "key": "current_price", "default": True},
                    {"text": "Перекрестие", "key": "crosshair", "default": True},
                ]
            },
            {
                "text": "Индикаторы",
                "children": [
                    {"text": "Фракталы Вильямса (▲/▼)", "key": "classic_fractals", "default": True},
                    {
                        "text": "Линии плато",
                        "children": [
                            {"text": "Плато вверх (High)", "key": "plateau_high", "default": True},
                            {"text": "Плато вниз (Low)", "key": "plateau_low", "default": True},
                        ]
                    },
                    {
                        "text": "Каналы и коридоры",
                        "children": [
                            {
                                "text": "Фракталы и плато",
                                "children": [
                                    {"text": "Верхняя граница (High)", "key": "ch0_orange_upper", "default": True},
                                    {"text": "Нижняя граница (Low)", "key": "ch0_orange_lower", "default": True},
                                    {"text": "Заливка коридора", "key": "ch0_orange_fill", "default": True},
                                ]
                            },
                            {
                                "text": "Классика Вильямса",
                                "children": [
                                    {"text": "Верхняя граница (High)", "key": "ch1_green_upper", "default": True},
                                    {"text": "Нижняя граница (Low)", "key": "ch1_green_lower", "default": True},
                                    {"text": "Заливка коридора", "key": "ch1_green_fill", "default": True},
                                ]
                            },
                            {
                                "text": "Диапазонный",
                                "children": [
                                    {"text": "Верхняя граница (High)", "key": "ch2_purple_upper", "default": True},
                                    {"text": "Нижняя граница (Low)", "key": "ch2_purple_lower", "default": True},
                                    {"text": "Заливка коридора", "key": "ch2_purple_fill", "default": True},
                                ]
                            },
                            {
                                "text": "Структурный",
                                "children": [
                                    {"text": "Верхняя граница (High)", "key": "ch3_blue_upper", "default": True},
                                    {"text": "Нижняя граница (Low)", "key": "ch3_blue_lower", "default": True},
                                    {"text": "Заливка коридора", "key": "ch3_blue_fill", "default": True},
                                ]
                            },
                            {
                                "text": "Вильямс с расширением плато",
                                "children": [
                                    {"text": "Верхняя граница (High)", "key": "ch4_cyan_upper", "default": True},
                                    {"text": "Нижняя граница (Low)", "key": "ch4_cyan_lower", "default": True},
                                    {"text": "Заливка коридора", "key": "ch4_cyan_fill", "default": True},
                                ]
                            },
                        ]
                    },
                ]
            },
            {
                "text": "Фрактальные уровни",
                "children": [
                    {"text": "Линии уровней", "key": "fractal_levels", "default": True},
                    {"text": "Метки цен", "key": "level_labels", "default": True},
                    {"text": "Только активные в памяти", "key": "levels_active_only", "default": False},
                ]
            },
            {
                "text": "Слом структуры (CHoCH)",
                "children": [
                    {"text": "Стрелки слома", "key": "choch_arrows", "default": True},
                    {"text": "Полки уровней", "key": "choch_shelves", "default": True},
                ]
            },
            {
                "text": "Торговые операции",
                "children": [
                    {
                        "text": "Реальные сделки",
                        "children": [
                            {"text": "Стрелки входа (Buy/Sell)", "key": "real_trades", "default": True},
                            {"text": "Стрелки Брекета (Векторы)", "key": "real_vectors", "default": True},
                            {"text": "Номера перезаходов (#1..4)", "key": "real_attempts", "default": True},
                            {"text": "Линия Stop Loss", "key": "real_sl", "default": True},
                            {"text": "Линия Take Profit", "key": "real_tp", "default": True},
                            {
                                "text": "Фильтр результата",
                                "children": [
                                    {"text": "Прибыльные (Тейк)", "key": "filter_profitable", "default": True},
                                    {"text": "Убыточные (Стоп)", "key": "filter_loss", "default": True},
                                ]
                            }
                        ]
                    },
                    {
                        "text": "Виртуальные сделки",
                        "children": [
                            {"text": "Стрелки входа (Buy/Sell)", "key": "virt_trades", "default": True},
                            {"text": "Стрелки Брекета (Векторы)", "key": "virt_vectors", "default": True},
                            {"text": "Номера попыток (#1..4)", "key": "virt_attempts", "default": True},
                            {"text": "Линия Stop Loss", "key": "virt_sl", "default": True},
                            {"text": "Линия Take Profit", "key": "virt_tp", "default": True},
                            {
                                "text": "Фильтр результата",
                                "children": [
                                    {"text": "Прибыльные (Тейк)", "key": "virt_filter_profitable", "default": True},
                                    {"text": "Убыточные (Стоп)", "key": "virt_filter_loss", "default": True},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        def add_nodes(parent_node, items, path=""):
            for entry in items:
                node_text = entry["text"]
                item = QTreeWidgetItem(parent_node, [node_text])
                current_path = f"{path}/{node_text}" if path else node_text
                children = entry.get("children")
                if children:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                    add_nodes(item, children, current_path)
                    if current_path in saved_expanded:
                        item.setExpanded(bool(saved_expanded[current_path]))
                    else:
                        item.setExpanded(True)
                else:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    key = entry.get("key")
                    item.setData(0, Qt.ItemDataRole.UserRole, key)
                    is_checked = saved_vis.get(key, entry.get("default", True))
                    item.setCheckState(0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)

        add_nodes(tree, tree_data)
        if not saved_expanded:
            tree.expandAll()

        tree.itemChanged.connect(self._on_tree_item_changed)
        tree.itemExpanded.connect(self._on_tree_expansion_changed)
        tree.itemCollapsed.connect(self._on_tree_expansion_changed)
        return tree

    def _on_tree_expansion_changed(self, item):
        """Срабатывает при раскрытии или сворачивании ветки дерева."""
        self.save_settings()

    def _on_tree_item_changed(self, item, column):
        """Срабатывает при изменении состояния чекбокса в дереве слоев."""
        if getattr(self, "_updating_tree", False):
            return
        QTimer.singleShot(15, self._apply_tree_visibility)

    def _apply_tree_visibility(self):
        """Считывает состояния всех чекбоксов и передает в холст графика."""
        if not hasattr(self, "tree_visibility"):
            return

        vis = {}

        def scan(node):
            key = node.data(0, Qt.ItemDataRole.UserRole)
            if key:
                vis[key] = (node.checkState(0) != Qt.CheckState.Unchecked)
            for i in range(node.childCount()):
                scan(node.child(i))

        for i in range(self.tree_visibility.topLevelItemCount()):
            scan(self.tree_visibility.topLevelItem(i))

        self.chart_canvas.update_visibility(vis)
        self.render_current_frame(auto_range=False)
        self.save_settings()

    def _create_bottom_bar(self):
        """Нижняя информационная полоска под графиком."""
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 1, 2, 1)

        self.lbl_status = QLabel("Статус: Загрузка...")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        lbl_legend = QLabel("🟢 Real Buy   🔴 Real Sell   🟡 Virt Buy   🟣 Virt Sell   ▲/▼ Фракталы   --- SL/TP/Уровни")
        lbl_legend.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(lbl_legend)

        return layout

    # ============================================================
    # Управление торговыми днями и файлами
    # ============================================================
    def _update_inst_label(self):
        """Обновляет заголовок инструмента с датой и таймфреймом."""
        fname = os.path.basename(self.default_file)
        m = re.search(r"(\d{2})(\d{2})(\d{2})", fname)
        if m:
            d_str = f"{m.group(3)}.{m.group(2)}.20{m.group(1)}"
            self.lbl_inst.setText(f"MIX-9.26  {d_str} [{self.current_tf}]")
        else:
            self.lbl_inst.setText(f"MIX-9.26 [{self.current_tf}]")

    def _scan_tick_files(self):
        """Находит все тиковые файлы на Y:/ и в подпапках, сортирует по дате."""
        found = []
        seen_paths = set()
        search_dirs = ["Y:/", "Y:/ticks", os.path.dirname(self.default_file)]

        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for pat in [os.path.join(d, "*.txt")]:
                for fpath in glob.glob(pat):
                    norm_path = os.path.normpath(fpath).replace("\\", "/")
                    if norm_path in seen_paths:
                        continue
                    seen_paths.add(norm_path)

                    fname = os.path.basename(norm_path)
                    # Проверяем шаблон имени тиков
                    m = re.search(r"(\d{2})(\d{2})(\d{2})", fname)
                    if m and any(k in fname.upper() for k in ["MX", "MIX", "RI", "SI", "SPB", "SR", "GZ"]):
                        y, mth, day = m.group(1), m.group(2), m.group(3)
                        date_key = f"20{y}-{mth}-{day}"
                        label = f"{day}.{mth}.20{y}  [{fname}]"
                        found.append((date_key, label, norm_path))
                    else:
                        try:
                            with open(norm_path, "r", encoding="utf-8", errors="replace") as f_test:
                                first_line = f_test.readline()
                                if "<TICKER>" in first_line:
                                    found.append((fname, fname, norm_path))
                        except Exception:
                            pass

        found.sort(key=lambda x: x[0])
        return found

    def _populate_day_selector(self, select_path=None):
        """Заполняет выпадающий список доступными торговыми днями."""
        if not hasattr(self, "combo_days"):
            return
        self.combo_days.blockSignals(True)
        self.combo_days.clear()

        files = self._scan_tick_files()
        target_path = os.path.normpath(select_path or self.default_file).replace("\\", "/")
        select_idx = 0

        for i, (date_key, label, fpath) in enumerate(files):
            self.combo_days.addItem(label, fpath)
            if os.path.normpath(fpath).replace("\\", "/") == target_path:
                select_idx = i

        if target_path and target_path not in [f[2] for f in files] and os.path.exists(target_path):
            fname = os.path.basename(target_path)
            self.combo_days.addItem(f"{fname}", target_path)
            select_idx = self.combo_days.count() - 1

        if self.combo_days.count() > 0:
            self.combo_days.setCurrentIndex(select_idx)

        self.combo_days.blockSignals(False)

    def _on_day_changed(self, index):
        """Вызывается при смене выбранного дня в выпадающем списке."""
        if index < 0:
            return
        fpath = self.combo_days.itemData(index)
        if not fpath:
            return

        norm_cur = os.path.normpath(self.default_file).replace("\\", "/")
        norm_new = os.path.normpath(fpath).replace("\\", "/")
        if norm_cur == norm_new:
            return

        self.switch_to_file(fpath)

    def _on_browse_file(self):
        """Диалог выбора произвольного файла тиков через проводник."""
        initial_dir = os.path.dirname(self.default_file) if os.path.exists(self.default_file) else "Y:/"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать файл торгового дня", initial_dir, "Файлы тиков (*.txt);;Все файлы (*.*)"
        )
        if file_path:
            norm_path = os.path.normpath(file_path).replace("\\", "/")
            self._populate_day_selector(select_path=norm_path)
            self.switch_to_file(norm_path)

    def switch_to_file(self, fpath):
        """Переключает STRG на новый тиковый файл и полностью обновляет состояние."""
        if not os.path.exists(fpath):
            self.lbl_status.setText(f"Ошибка: файл {fpath} не найден!")
            return

        self.pause_replay()
        self.default_file = fpath
        self._ticks_loaded = False

        self._update_inst_label()
        self.lbl_status.setText(f"Чтение тиков {os.path.basename(fpath)}...")
        self.load_and_render(reload_lua=True, auto_range=True)
        self.chart_canvas.getPlotItem().autoRange()
        self.save_settings()

    def _scan_strategy_files(self):
        r"""Сканирует известные папки на Y:\ на наличие Lua-стратегий и моков."""
        candidates = [
            (r"Y:\opening_strategy\mock_opening.lua", "mock_opening.lua"),
            (r"Y:\true_fractal\true_f_formock.lua", "true_f_formock.lua"),
            (r"Y:\support_pro\mock_test.lua", "mock_test.lua"),
        ]
        seen = set()
        result = []
        for path, name in candidates:
            if os.path.exists(path):
                norm = os.path.normpath(path).replace("\\", "/")
                seen.add(norm)
                result.append((norm, name))

        try:
            for root, dirs, files in os.walk("Y:/"):
                if any(x in root for x in [".git", ".venv", "__pycache__", "build", "dist"]):
                    continue
                for fname in files:
                    if fname.endswith(".lua") and ("mock" in fname.lower() or "formock" in fname.lower()):
                        full = os.path.normpath(os.path.join(root, fname)).replace("\\", "/")
                        if full not in seen:
                            seen.add(full)
                            result.append((full, fname))
        except Exception:
            pass

        return result

    def _populate_strategy_selector(self, select_path=None):
        """Заполняет выпадающий список доступных Lua-стратегий."""
        if not hasattr(self, "combo_strategy"):
            return
        self.combo_strategy.blockSignals(True)
        self.combo_strategy.clear()

        strategies = self._scan_strategy_files()
        target = os.path.normpath(select_path or self.strategy_file).replace("\\", "/")
        select_idx = 0

        for i, (path, name) in enumerate(strategies):
            self.combo_strategy.addItem(name, path)
            if path == target:
                select_idx = i

        if target and target not in [s[0] for s in strategies] and os.path.exists(target):
            fname = os.path.basename(target)
            self.combo_strategy.addItem(fname, target)
            select_idx = self.combo_strategy.count() - 1

        if self.combo_strategy.count() > 0:
            self.combo_strategy.setCurrentIndex(select_idx)

        self.combo_strategy.blockSignals(False)

    def _on_strategy_changed(self, index):
        """Вызывается при выборе стратегии из выпадающего списка."""
        if index < 0:
            return
        strat_path = self.combo_strategy.itemData(index)
        if not strat_path:
            return
        norm_cur = os.path.normpath(self.strategy_file).replace("\\", "/")
        norm_new = os.path.normpath(strat_path).replace("\\", "/")
        if norm_cur == norm_new:
            return
        self.switch_to_strategy(strat_path)

    def _on_browse_strategy(self):
        """Диалог выбора файла Lua-стратегии через проводник."""
        initial_dir = os.path.dirname(self.strategy_file) if os.path.exists(self.strategy_file) else "Y:/"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать Lua-стратегию", initial_dir, "Скрипты Lua (*.lua);;Все файлы (*.*)"
        )
        if file_path:
            norm_path = os.path.normpath(file_path).replace("\\", "/")
            self._populate_strategy_selector(select_path=norm_path)
            self.switch_to_strategy(norm_path)

    def switch_to_strategy(self, strat_path):
        """Переключает текущую Lua-стратегию и перезапускает расчет."""
        if not os.path.exists(strat_path):
            self.lbl_status.setText(f"Ошибка: файл стратегии {strat_path} не найден!")
            return

        self.pause_replay()
        self.strategy_file = strat_path
        self.runner = LuaStrategyRunner(self.strategy_file)
        self.last_trades = []
        self.last_levels = []
        self.last_stats = {}
        self.lbl_status.setText(f"Загрузка стратегии {os.path.basename(strat_path)}...")
        self.load_and_render(reload_lua=True, auto_range=False)
        self.lbl_status.setText(f"Статус: Подключена стратегия {os.path.basename(strat_path)}")
        self.save_settings()

    # ============================================================
    # Логика загрузки и воспроизведения
    # ============================================================
    def load_and_render(self, reload_lua=True, auto_range=False):
        """Загружает тики, выполняет Lua-стратегию и инициализирует плеер."""
        if not os.path.exists(self.default_file):
            self.lbl_status.setText(f"Файл {self.default_file} не найден!")
            return

        self._update_inst_label()

        if not self._ticks_loaded:
            self.lbl_status.setText(f"Чтение тиков {os.path.basename(self.default_file)}...")
            self.aggregator.load_file(self.default_file)
            self._ticks_loaded = True
            n_ticks = len(self.aggregator.df_ticks)
            self.slider_time.setMaximum(n_ticks - 1)
            self.current_tick_idx = n_ticks - 1

        # Запуск Lua-стратегии
        if reload_lua or not self.last_trades:
            strat_name = os.path.basename(self.strategy_file)
            self.lbl_status.setText(f"Выполнение Lua-стратегии {strat_name}...")
            self.last_trades, self.last_levels, self.last_stats = self.runner.run(
                self.aggregator.df_ticks, bar_period_sec=300
            )

        # Полные свечи под текущий ТФ и установка стабильной шкалы времени
        self.df_candles_full = self.aggregator.get_candles(self.current_tf)
        self.chart_canvas.set_full_timeline(self.df_candles_full)

        # Отрисовка текущего кадра
        self.render_current_frame(auto_range=auto_range)
        if auto_range:
            self.chart_canvas.getPlotItem().autoRange()

    def render_current_frame(self, auto_range=False):
        """Отрисовывает состояние рынка и стратегии в момент self.current_tick_idx."""
        if not self._ticks_loaded or self.aggregator.df_ticks.empty:
            return

        df_ticks = self.aggregator.df_ticks
        idx = max(0, min(self.current_tick_idx, len(df_ticks) - 1))
        curr_tick = df_ticks.iloc[idx]
        curr_time = curr_tick["DATETIME"]
        curr_price = float(curr_tick["PRICE"])

        # Обновляем цифровое табло
        self.lbl_replay_time.setText(curr_time.strftime("%H:%M:%S"))
        self.lbl_replay_price.setText(f"{int(curr_price):,} ".replace(",", " "))

        # Находим срез видимых свечей
        c_times = self.df_candles_full["time"].values
        target_np = np.datetime64(curr_time)
        c_idx = int(np.searchsorted(c_times, target_np, side="right"))

        if c_idx <= 0:
            c_idx = 1

        visible_candles = self.df_candles_full.iloc[:c_idx].copy()

        # Моделируем честное "живое дыхание" формирующейся свечи:
        # High и Low берутся строго по уже случившимся тикам внутри текущего бара (без заглядывания в будущее!)
        last_row_idx = visible_candles.index[-1]
        bar_start_time = visible_candles.loc[last_row_idx, "time"]

        tick_times = df_ticks["DATETIME"].values
        start_tick_idx = int(np.searchsorted(tick_times, np.datetime64(bar_start_time), side="left"))
        start_tick_idx = min(start_tick_idx, idx)

        bar_prices = df_ticks["PRICE"].values[start_tick_idx : idx + 1]
        if len(bar_prices) > 0:
            visible_candles.loc[last_row_idx, "open"] = float(bar_prices[0])
            visible_candles.loc[last_row_idx, "high"] = float(bar_prices.max())
            visible_candles.loc[last_row_idx, "low"] = float(bar_prices.min())
            visible_candles.loc[last_row_idx, "close"] = curr_price
            if "volume" in visible_candles.columns:
                bar_vols = df_ticks["VOL"].values[start_tick_idx : idx + 1]
                visible_candles.loc[last_row_idx, "volume"] = int(bar_vols.sum())

        # Отрисовка
        self.chart_canvas.render_candles(visible_candles, auto_range=auto_range)
        self.chart_canvas.render_signal_corridor(visible_candles)
        self.chart_canvas.render_classic_fractals(visible_candles)
        self.chart_canvas.render_plateaus(visible_candles)
        self.chart_canvas.render_fractal_levels(self.last_levels, visible_candles)
        self.chart_canvas.render_structure_breaks(visible_candles)
        self.chart_canvas.render_trades(self.last_trades, visible_candles)

        # Обновление PnL дашборда (Реальная и Виртуальная)
        self._update_pnl_dashboard(curr_time, curr_price)

        # Счётчик оставшихся перезаходов на текущем активном уровне
        real_trades_before = [t for t in self.last_trades if t.get("is_real") and np.datetime64(t["entry_time"]) <= target_np]
        if real_trades_before:
            last_tr = real_trades_before[-1]
            rem_t = 4 - last_tr.get("attempt", 0)
        else:
            rem_t = 4

        self.lbl_attempts.setText(f"{max(0, rem_t)} / 4")

        tf_labels = {"1M": "1 минута", "3M": "3 минуты", "5M": "5 минут", "15M": "15 минут", "1H": "1 час"}
        self.lbl_inst.setText(f"MIX-9.26 [{tf_labels.get(self.current_tf, self.current_tf)}]")
        self.lbl_status.setText(
            f"Статус: Время {curr_time.strftime('%H:%M:%S')} | Свечей {len(visible_candles)} | "
            f"Сделок: {len(real_trades_before)}/{len(self.last_trades)} | Перезаходов: {rem_t}/4"
        )

    # ============================================================
    # Управление плеером
    # ============================================================
    def toggle_play(self):
        if self.is_playing:
            self.pause_replay()
        else:
            self.start_replay()

    def start_replay(self):
        if self.current_tick_idx >= len(self.aggregator.df_ticks) - 1:
            self.current_tick_idx = 0
        self.is_playing = True
        self.btn_play.setText("⏸ Пауза")
        self.btn_play.setStyleSheet("background-color: #332014; color: #e67e22; border: 1px solid #7d4414;")
        self.replay_timer.start()

    def pause_replay(self):
        self.is_playing = False
        self.btn_play.setText("▶ Старт")
        self.btn_play.setStyleSheet("")
        self.replay_timer.stop()

    def step_tick_forward(self):
        """Шаг вперед (пропуская тики с одинаковой ценой до следующего изменения)."""
        self.pause_replay()
        if self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return
        prices = self.aggregator.df_ticks["PRICE"].values
        n_ticks = len(prices)
        if self.current_tick_idx < n_ticks - 1:
            curr_p = prices[self.current_tick_idx]
            idx = self.current_tick_idx + 1
            while idx < n_ticks and prices[idx] == curr_p:
                idx += 1
            self.current_tick_idx = min(idx, n_ticks - 1)
            self.slider_time.blockSignals(True)
            self.slider_time.setValue(self.current_tick_idx)
            self.slider_time.blockSignals(False)
            self.render_current_frame(auto_range=False)

    def step_tick_backward(self):
        """Шаг назад (пропуская тики с одинаковой ценой до предыдущего изменения)."""
        self.pause_replay()
        if self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return
        prices = self.aggregator.df_ticks["PRICE"].values
        if self.current_tick_idx > 0:
            curr_p = prices[self.current_tick_idx]
            idx = self.current_tick_idx - 1
            while idx >= 0 and prices[idx] == curr_p:
                idx -= 1
            self.current_tick_idx = max(0, idx)
            self.slider_time.blockSignals(True)
            self.slider_time.setValue(self.current_tick_idx)
            self.slider_time.blockSignals(False)
            self.render_current_frame(auto_range=False)

    def step_candle_forward(self):
        """Шаг вперед на 1 свечу текущего таймфрейма."""
        self.pause_replay()
        if self.df_candles_full.empty or self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return

        df_ticks = self.aggregator.df_ticks
        curr_time = df_ticks.iloc[self.current_tick_idx]["DATETIME"]
        c_times = self.df_candles_full["time"].values
        tick_times = df_ticks["DATETIME"].values
        target_np = np.datetime64(curr_time)

        curr_candle_idx = int(np.searchsorted(c_times, target_np, side="right")) - 1
        next_candle_idx = curr_candle_idx + 1

        if next_candle_idx < len(c_times):
            next_candle_time = c_times[next_candle_idx]
            next_tick_idx = int(np.searchsorted(tick_times, next_candle_time, side="left"))
            self.current_tick_idx = min(next_tick_idx, len(df_ticks) - 1)
        else:
            self.current_tick_idx = len(df_ticks) - 1

        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def step_candle_backward(self):
        """Шаг назад на 1 свечу текущего таймфрейма (без пропусков и зависаний)."""
        self.pause_replay()
        if self.df_candles_full.empty or self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return

        df_ticks = self.aggregator.df_ticks
        curr_time = df_ticks.iloc[self.current_tick_idx]["DATETIME"]
        c_times = self.df_candles_full["time"].values
        tick_times = df_ticks["DATETIME"].values
        target_np = np.datetime64(curr_time)

        curr_candle_idx = int(np.searchsorted(c_times, target_np, side="right")) - 1
        prev_candle_idx = curr_candle_idx - 1

        if prev_candle_idx >= 0:
            prev_candle_time = c_times[prev_candle_idx]
            prev_tick_idx = int(np.searchsorted(tick_times, prev_candle_time, side="left"))
            self.current_tick_idx = max(0, prev_tick_idx)
        else:
            self.current_tick_idx = 0

        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def step_forward(self):
        """Совместимость: шаг вперед тиками."""
        self.step_tick_forward()

    def step_backward(self):
        """Совместимость: шаг назад тиками."""
        self.step_tick_backward()

    def reset_replay(self):
        self.pause_replay()
        self.current_tick_idx = 0
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(0)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def show_all(self):
        """Возвращает график в стартовое положение: конец дня, все свечи, полный автоскейл."""
        self.pause_replay()
        if self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return

        n_ticks = len(self.aggregator.df_ticks)
        self.current_tick_idx = n_ticks - 1

        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)

        self.render_current_frame(auto_range=True)
        self.chart_canvas.getPlotItem().autoRange()
        self.lbl_status.setText("Статус: Показан весь торговый день (стартовое состояние)")

    def set_speed(self, speed_val):
        self.speed_multiplier = speed_val

    def on_slider_moved(self, val):
        self.current_tick_idx = val
        self.render_current_frame(auto_range=False)

    def _on_replay_timer_tick(self):
        # Шаг тиков за кадр в зависимости от скорости
        if self.speed_multiplier == 1:
            step = 1
        elif self.speed_multiplier == 5:
            step = 6
        elif self.speed_multiplier == 25:
            step = 35
        elif self.speed_multiplier == 100:
            step = 160
        else:  # MAX
            step = 700

        self.current_tick_idx += step

        if self.current_tick_idx >= len(self.aggregator.df_ticks) - 1:
            self.current_tick_idx = len(self.aggregator.df_ticks) - 1
            self.pause_replay()

        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)

        self.render_current_frame(auto_range=False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play()
        elif event.key() == Qt.Key.Key_Left:
            self.step_candle_backward()
        elif event.key() == Qt.Key.Key_Right:
            self.step_candle_forward()
        elif event.key() == Qt.Key.Key_Down:
            self.step_tick_backward()
        elif event.key() == Qt.Key.Key_Up:
            self.step_tick_forward()
        else:
            super().keyPressEvent(event)

    # ============================================================
    # Обработчики интерфейса
    # ============================================================
    def on_mode_clicked(self, mode_id):
        mode_names = {"MOCK": "МОК", "TEST": "ТЕСТ (Файл)", "LIVE": "БОЕВОЙ"}
        self.lbl_status.setText(f"Статус: Режим -> {mode_names.get(mode_id, mode_id)}")

    def on_top_btn_clicked(self, btn_name):
        if btn_name == "⟲ Сброс":
            self.chart_canvas.getPlotItem().autoRange()
            self.lbl_status.setText("Статус: Масштаб графика сброшен")
        elif btn_name == "🔍+":
            self.chart_canvas.getPlotItem().getViewBox().scaleBy((0.7, 0.7))
        elif btn_name == "🔍-":
            self.chart_canvas.getPlotItem().getViewBox().scaleBy((1.3, 1.3))
        else:
            self.lbl_status.setText(f"Статус: Нажата кнопка '{btn_name}'")

    def on_tf_changed(self, tf_name):
        if not tf_name:
            return
        self.current_tf = tf_name
        self._update_inst_label()
        self.df_candles_full = self.aggregator.get_candles(self.current_tf)
        self.chart_canvas.set_full_timeline(self.df_candles_full)
        self.render_current_frame(auto_range=False)
        self.save_settings()

    def on_tf_clicked(self, tf_name):
        """Алиас для переключения таймфрейма."""
        if hasattr(self, "combo_tf"):
            self.combo_tf.setCurrentText(tf_name)
        else:
            self.on_tf_changed(tf_name)

    def on_refresh_clicked(self):
        """Горячая перезагрузка текущей Lua-стратегии."""
        self.pause_replay()
        self.runner = LuaStrategyRunner(self.strategy_file)
        self.load_and_render(reload_lua=True, auto_range=False)
        self.lbl_status.setText(f"Статус: Стратегия {os.path.basename(self.strategy_file)} перезагружена, график обновлен!")

    def closeEvent(self, event):
        """Сохраняет настройки перед закрытием приложения."""
        self.save_settings()
        super().closeEvent(event)
