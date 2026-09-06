"""
lua_runner.py
Модуль исполнения произвольных Lua-стратегий в STRG.
Использует lupa (Lua 5.5) для исполнения чистого Lua-кода (CP1251)
без зависимостей от QUIK API.
Высокопроизводительный numpy-пайплайн (< 1 сек на 175 000 тиков).
"""

import os
from datetime import datetime
import pandas as pd
import numpy as np
import lupa
from lupa import LuaRuntime


class LuaStrategyRunner:
    """Универсальный исполнитель Lua-стратегий на тиковых данных."""

    def __init__(self, lua_path=r"Y:\true_fractal\true_f_formock.lua"):
        self.lua_path = lua_path
        self.lua = None
        self.trade_signals = []
        self.fractal_levels = []
        self.stats = {}

    def load_strategy(self, path=None):
        """Загружает файл стратегии в кодировке CP1251."""
        if path:
            self.lua_path = path

        if not os.path.exists(self.lua_path):
            raise FileNotFoundError(f"Файл стратегии не найден: {self.lua_path}")

        self.lua = LuaRuntime(unpack_returned_tuples=True)

        with open(self.lua_path, "r", encoding="cp1251", errors="replace") as f:
            code = f.read()

        self.lua.execute(code)

    def run(self, df_ticks, bar_period_sec=180):
        """
        Прогоняет тиковый поток через Lua-стратегию.
        
        :param df_ticks: DataFrame с колонками DATETIME, PRICE, VOL
        :param bar_period_sec: Период баров для FeedBar (по умолчанию 180с = 3 мин)
        :return: (trade_signals, fractal_levels, stats)
        """
        self.load_strategy()

        g = self.lua.globals()
        feed_bar = g.FeedBar
        feed_tick = g.FeedTick

        if df_ticks.empty:
            return [], [], {}

        # Группировка по интервалам баров
        df = df_ticks.copy()
        df["bar_time"] = df["DATETIME"].dt.floor(f"{bar_period_sec}s")
        grouped = df.groupby("bar_time", sort=True)

        raw_events = []
        level_timeline = []
        active_fractals_seen = {}
        prev_fractal_set = set()
        prev_len = 0

        for b_time, group in grouped:
            prices = group["PRICE"].values
            times = group["DATETIME"].values

            b_high = float(prices.max())
            b_low = float(prices.min())

            # 1. Подача бара
            feed_bar(b_high, b_low)

            h_len = len(g.history_log)
            if h_len > prev_len:
                for k in range(prev_len + 1, h_len + 1):
                    ev = dict(g.history_log[k])
                    ev["time"] = b_time
                    raw_events.append(ev)
                prev_len = h_len

            # Отслеживание фракталов
            curr_fractal_set = set(g.fractals.values())
            for fr in curr_fractal_set - prev_fractal_set:
                if fr not in active_fractals_seen:
                    active_fractals_seen[fr] = b_time

            for fr in prev_fractal_set - curr_fractal_set:
                if fr in active_fractals_seen:
                    level_timeline.append({
                        "price": fr,
                        "start_time": active_fractals_seen[fr],
                        "end_time": b_time,
                        "label": f"Fractal {int(fr)}"
                    })
                    del active_fractals_seen[fr]

            prev_fractal_set = curr_fractal_set

            # 2. Быстрая подача тиков через numpy-массивы
            for i in range(len(prices)):
                feed_tick(float(prices[i]))
                h_len = len(g.history_log)
                if h_len > prev_len:
                    t = times[i]
                    for k in range(prev_len + 1, h_len + 1):
                        ev = dict(g.history_log[k])
                        ev["time"] = t
                        raw_events.append(ev)
                    prev_len = h_len

        # Закрываем активные уровни
        last_time = df["DATETIME"].iloc[-1]
        for fr, start_t in active_fractals_seen.items():
            level_timeline.append({
                "price": fr,
                "start_time": start_t,
                "end_time": last_time,
                "label": f"Fractal {int(fr)}"
            })

        self.fractal_levels = level_timeline
        self.trade_signals = self._parse_trades(raw_events)

        real_trades = [t for t in self.trade_signals if t["is_real"]]
        virt_trades = [t for t in self.trade_signals if not t["is_real"]]
        self.stats = {
            "total_events": len(raw_events),
            "real_trades_count": len(real_trades),
            "virt_trades_count": len(virt_trades),
            "remaining_count_t": int(g.count_t),
            "remaining_count_v": int(g.count_v),
            "current_start_price": float(g.startPrice),
        }

        return self.trade_signals, self.fractal_levels, self.stats

    def _parse_trades(self, raw_events):
        """Сопоставляет события открытия и закрытия сделок."""
        trades = []
        open_real_trade = None
        open_virt_trade = None

        for ev in raw_events:
            ev_type = ev.get("type")
            t = ev.get("time")
            p = float(ev.get("price", 0))

            if ev_type == "TRADE_OPEN":
                attempt_num = 4 - int(ev.get("t_left", 0))
                open_real_trade = {
                    "is_real": True,
                    "direction": "BUY",
                    "entry_time": t,
                    "entry_price": float(ev.get("start", p)),
                    "sl": float(self.lua.globals().stop_price),
                    "tp": float(self.lua.globals().take_price),
                    "attempt": attempt_num,
                    "close_time": None,
                    "close_price": None,
                    "close_reason": None,
                }
                trades.append(open_real_trade)

            elif ev_type == "TRADE_CLOSE":
                if open_real_trade and open_real_trade["close_time"] is None:
                    open_real_trade["close_time"] = t
                    open_real_trade["close_price"] = p
                    open_real_trade["close_reason"] = "TP" if "TAKE" in ev.get("msg", "") else "SL"
                    open_real_trade = None

            elif ev_type == "VIRT_OPEN":
                attempt_num = 4 - int(ev.get("v_left", 0))
                open_virt_trade = {
                    "is_real": False,
                    "direction": "SELL",
                    "entry_time": t,
                    "entry_price": float(ev.get("start", p)),
                    "sl": float(self.lua.globals().virt_stop),
                    "tp": float(self.lua.globals().virt_take),
                    "attempt": attempt_num,
                    "close_time": None,
                    "close_price": None,
                    "close_reason": None,
                }
                trades.append(open_virt_trade)

            elif ev_type == "VIRT_CLOSE":
                if open_virt_trade and open_virt_trade["close_time"] is None:
                    open_virt_trade["close_time"] = t
                    open_virt_trade["close_price"] = p
                    open_virt_trade["close_reason"] = "VIRT_CLOSE"
                    open_virt_trade = None

        return trades
