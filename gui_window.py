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
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QButtonGroup, QSlider, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
import theme
from chart_canvas import ChartCanvas
from tick_aggregator import TickAggregator
from lua_runner import LuaStrategyRunner


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("STRG — Strategy Monitor & Market Replayer")
        self.resize(1200, 750)

        # Движок данных
        self.current_tf = "5M"
        self.default_file = "Y:/MXU6_260901_260901.txt"
        self.aggregator = TickAggregator(self.default_file)
        self.df_candles_full = pd.DataFrame()

        # Исполнитель Lua-стратегии
        self.strategy_file = r"Y:\true_fractal\true_f_formock.lua"
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

        # Ряд 0: Шаг назад (тики)
        self.btn_step_back = QPushButton("⏮ Шаг")
        self.btn_step_back.setProperty("class", "ReplayBtn")
        self.btn_step_back.setToolTip("Шаг назад (1 тик)")
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

        # Ряд 0: Шаг вперед (тики)
        self.btn_step_fwd = QPushButton("⏭ Шаг")
        self.btn_step_fwd.setProperty("class", "ReplayBtn")
        self.btn_step_fwd.setToolTip("Шаг вперед (1 тик)")
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

    def _create_right_panel(self):
        """Создает правую панель управления в строгом стиле QUIK."""
        panel = QFrame()
        panel.setObjectName("RightPanel")
        panel.setFixedWidth(155)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(6)

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

        layout.addSpacing(4)

        # Таймфреймы
        lbl_tf_title = QLabel("ТАЙМФРЕЙМ")
        lbl_tf_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_tf_title)

        self.tf_group = QButtonGroup(self)
        self.tf_buttons = {}

        for tf_name in ["1M", "3M", "5M", "15M", "1H"]:
            btn = QPushButton(tf_name)
            btn.setCheckable(True)
            btn.setProperty("class", "TfBtn")
            btn.clicked.connect(lambda checked, name=tf_name: self.on_tf_clicked(name))
            self.tf_group.addButton(btn)
            layout.addWidget(btn)
            self.tf_buttons[tf_name] = btn

        self.tf_buttons["5M"].setChecked(True)

        layout.addSpacing(4)

        # Стратегия Lua
        lbl_strat_title = QLabel("СТРАТЕГИЯ LUA")
        lbl_strat_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_strat_title)

        self.lbl_strat_name = QLabel("true_f_formock.lua")
        self.lbl_strat_name.setStyleSheet(
            "font-size: 10px; color: #cccccc; border: 1px solid #333333; padding: 4px; background: #161616;"
        )
        layout.addWidget(self.lbl_strat_name)

        layout.addSpacing(4)

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

        layout.addStretch()

        # Перезаходы
        lbl_att_title = QLabel("ПЕРЕЗАХОДЫ")
        lbl_att_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #666666; border: none;")
        layout.addWidget(lbl_att_title)

        self.lbl_attempts = QLabel("4 / 4")
        self.lbl_attempts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_attempts.setStyleSheet(
            "background-color: #242010; color: #d4b106; font-size: 12px; font-weight: bold; "
            "padding: 4px; border: 1px solid #453c15;"
        )
        layout.addWidget(self.lbl_attempts)

        return panel

    def _create_bottom_bar(self):
        """Нижняя информационная полоска под графиком."""
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 1, 2, 1)

        self.lbl_status = QLabel("Статус: Загрузка...")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        lbl_legend = QLabel("🟢 Real Buy   🔴 Real Sell   🟡 Virt Buy   🟣 Virt Sell   --- SL/TP/Fractal")
        lbl_legend.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(lbl_legend)

        return layout

    # ============================================================
    # Логика загрузки и воспроизведения
    # ============================================================
    def load_and_render(self, reload_lua=True, auto_range=False):
        """Загружает тики, выполняет Lua-стратегию и инициализирует плеер."""
        if not os.path.exists(self.default_file):
            self.lbl_status.setText(f"Файл {self.default_file} не найден!")
            return

        if not self._ticks_loaded:
            self.lbl_status.setText(f"Чтение тиков {os.path.basename(self.default_file)}...")
            self.aggregator.load_file(self.default_file)
            self._ticks_loaded = True
            n_ticks = len(self.aggregator.df_ticks)
            self.slider_time.setMaximum(n_ticks - 1)
            self.current_tick_idx = n_ticks - 1

        # Запуск Lua-стратегии
        if reload_lua or not self.last_trades:
            self.lbl_status.setText("Выполнение Lua-стратегии true_f_formock.lua...")
            self.last_trades, self.last_levels, self.last_stats = self.runner.run(
                self.aggregator.df_ticks, bar_period_sec=180
            )

        # Полные свечи под текущий ТФ и установка стабильной шкалы времени
        self.df_candles_full = self.aggregator.get_candles(self.current_tf)
        self.chart_canvas.set_full_timeline(self.df_candles_full)

        # Отрисовка текущего кадра
        self.render_current_frame(auto_range=auto_range)

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

        # Моделируем "живое дыхание" последней свечи (Candle Morphing)
        last_row_idx = visible_candles.index[-1]
        visible_candles.loc[last_row_idx, "close"] = curr_price
        if curr_price > visible_candles.loc[last_row_idx, "high"]:
            visible_candles.loc[last_row_idx, "high"] = curr_price
        if curr_price < visible_candles.loc[last_row_idx, "low"]:
            visible_candles.loc[last_row_idx, "low"] = curr_price

        # Отрисовка
        self.chart_canvas.render_candles(visible_candles, auto_range=auto_range)
        self.chart_canvas.render_fractal_levels(self.last_levels, visible_candles)
        self.chart_canvas.render_trades(self.last_trades, visible_candles)

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
        """Шаг вперед на 1 тик."""
        self.pause_replay()
        if self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return
        n_ticks = len(self.aggregator.df_ticks)
        if self.current_tick_idx < n_ticks - 1:
            self.current_tick_idx += 1
            self.slider_time.blockSignals(True)
            self.slider_time.setValue(self.current_tick_idx)
            self.slider_time.blockSignals(False)
            self.render_current_frame(auto_range=False)

    def step_tick_backward(self):
        """Шаг назад на 1 тик."""
        self.pause_replay()
        if self.aggregator.df_ticks is None or self.aggregator.df_ticks.empty:
            return
        if self.current_tick_idx > 0:
            self.current_tick_idx -= 1
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

    def on_tf_clicked(self, tf_name):
        self.current_tf = tf_name
        self.df_candles_full = self.aggregator.get_candles(self.current_tf)
        self.chart_canvas.set_full_timeline(self.df_candles_full)
        self.render_current_frame(auto_range=False)

    def on_refresh_clicked(self):
        self.load_and_render(reload_lua=True, auto_range=False)
        self.lbl_status.setText("Статус: Lua-скрипт перезагружен, график обновлен!")
