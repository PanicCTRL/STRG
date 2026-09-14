"""
fractal_zigzag.py
Модуль вычисления эталонного канонического Зиг-Зага (TradingView Zig Zag):
- Построение свингов по величине отклонения цены (Deviation / Min Swing Threshold, по умолчанию 0.9%)
- Проекция активного луча (Calculate projected pivots) к текущему максимуму/минимуму
- Расчет 5-баровых фракталов Билла Вильямса для отображения на графике
"""

import numpy as np
import pandas as pd


def calculate_fractal_zigzag(df_candles, dev_percent=0.9, min_swing_pts=None, pivot_legs=4, calculate_projected=True):
    """
    Рассчитывает эталонный канонический Зиг-Заг TradingView по отклонению цены (Deviation).

    :param df_candles: DataFrame со свечами (open, high, low, close, time, bar_idx)
    :param dev_percent: Порог разворота в % (по умолчанию 0.9%)
    :param min_swing_pts: Альтернативный фиксированный порог в пунктах (если задан, приоритет над dev_percent)
    :param pivot_legs: Ноги точек разворота (TradingView Depth, для совместимости настроек)
    :param calculate_projected: Проецировать ли текущий незакрытый луч до текущего экстремума
    :return: (df_candles, pivots)
      pivots: список словарей {
          'idx': int,           # Индекс бара в df_candles
          'bar_idx': float,     # Значение bar_idx для отрисовки на оси X
          'time': pd.Timestamp, # Время бара
          'price': float,       # Цена экстремума (High или Low)
          'type': 'HIGH'/'LOW', # Тип пивота
          'projected': bool     # True для завершающего активного луча
      }
    """
    if df_candles is None or len(df_candles) < 2:
        return df_candles, []

    # Обратная совместимость, если первым параметром передали mode='macro'
    if isinstance(dev_percent, str):
        dev_percent = 0.9

    df = df_candles.copy()
    n = len(df)

    highs = df["high"].values
    lows = df["low"].values
    bar_indices = df["bar_idx"].values if "bar_idx" in df.columns else np.arange(n)
    times = df["time"].values if "time" in df.columns else np.arange(n)

    # 1. 5-баровые фракталы Вильямса (для графических маркеров на свечах)
    f_up = np.full(n, np.nan)
    f_down = np.full(n, np.nan)

    if n >= 5:
        for i in range(2, n - 2):
            if (highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and
                highs[i] > highs[i + 1] and highs[i] > highs[i + 2]):
                f_up[i] = highs[i]

            if (lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and
                lows[i] < lows[i + 1] and lows[i] < lows[i + 2]):
                f_down[i] = lows[i]

    df["fractal_up"] = f_up
    df["fractal_down"] = f_down

    # 2. Канонический Зиг-Заг TradingView (по отклонению цены / Deviation)
    pivots = []
    trend = 0  # 1 = UP, -1 = DOWN
    curr_high = highs[0]
    curr_high_idx = 0
    curr_low = lows[0]
    curr_low_idx = 0

    for i in range(1, n):
        h = highs[i]
        l = lows[i]

        dev_high = min_swing_pts if min_swing_pts is not None else curr_high * (dev_percent / 100.0)
        dev_low = min_swing_pts if min_swing_pts is not None else curr_low * (dev_percent / 100.0)

        if trend == 0:
            if h - curr_low >= dev_low:
                pivots.append({
                    "idx": curr_low_idx,
                    "bar_idx": float(bar_indices[curr_low_idx]),
                    "time": times[curr_low_idx],
                    "price": float(curr_low),
                    "type": "LOW"
                })
                trend = 1
                curr_high = h
                curr_high_idx = i
            elif curr_high - l >= dev_high:
                pivots.append({
                    "idx": curr_high_idx,
                    "bar_idx": float(bar_indices[curr_high_idx]),
                    "time": times[curr_high_idx],
                    "price": float(curr_high),
                    "type": "HIGH"
                })
                trend = -1
                curr_low = l
                curr_low_idx = i
            else:
                if h > curr_high:
                    curr_high = h
                    curr_high_idx = i
                if l < curr_low:
                    curr_low = l
                    curr_low_idx = i

        elif trend == 1:
            if h >= curr_high:
                curr_high = h
                curr_high_idx = i
            elif curr_high - l >= dev_high:
                pivots.append({
                    "idx": curr_high_idx,
                    "bar_idx": float(bar_indices[curr_high_idx]),
                    "time": times[curr_high_idx],
                    "price": float(curr_high),
                    "type": "HIGH"
                })
                trend = -1
                curr_low = l
                curr_low_idx = i

        elif trend == -1:
            if l <= curr_low:
                curr_low = l
                curr_low_idx = i
            elif h - curr_low >= dev_low:
                pivots.append({
                    "idx": curr_low_idx,
                    "bar_idx": float(bar_indices[curr_low_idx]),
                    "time": times[curr_low_idx],
                    "price": float(curr_low),
                    "type": "LOW"
                })
                trend = 1
                curr_high = h
                curr_high_idx = i

    # Проекция незакрытого динамического луча на текущей формирующейся свече (индекс n - 1)
    if calculate_projected and n > 0:
        last_i = n - 1
        last_bar = float(bar_indices[last_i])
        last_time = times[last_i]
        last_high = float(highs[last_i])
        last_low = float(lows[last_i])

        if trend == 1:
            if curr_high_idx == last_i:
                # Текущая свеча сама является вершиной -> линия идет ВВЕРХ к максимуму текущей свечи
                pivots.append({
                    "idx": last_i,
                    "bar_idx": last_bar,
                    "time": last_time,
                    "price": last_high,
                    "type": "HIGH",
                    "projected": True
                })
            else:
                # Вершина была раньше, а сейчас идет откат -> вершина на curr_high_idx,
                # а от нее линия идет ВНИЗ к МИНИМУМУ текущей свечи!
                pivots.append({
                    "idx": curr_high_idx,
                    "bar_idx": float(bar_indices[curr_high_idx]),
                    "time": times[curr_high_idx],
                    "price": float(curr_high),
                    "type": "HIGH",
                    "projected": True
                })
                pivots.append({
                    "idx": last_i,
                    "bar_idx": last_bar,
                    "time": last_time,
                    "price": last_low,
                    "type": "LOW",
                    "projected": True
                })
        elif trend == -1:
            if curr_low_idx == last_i:
                # Текущая свеча сама является низиной -> линия идет ВНИЗ к минимуму текущей свечи
                pivots.append({
                    "idx": last_i,
                    "bar_idx": last_bar,
                    "time": last_time,
                    "price": last_low,
                    "type": "LOW",
                    "projected": True
                })
            else:
                # Низина была раньше, а сейчас идет отскок -> низина на curr_low_idx,
                # а от нее линия идет ВВЕРХ к МАКСИМУМУ текущей свечи!
                pivots.append({
                    "idx": curr_low_idx,
                    "bar_idx": float(bar_indices[curr_low_idx]),
                    "time": times[curr_low_idx],
                    "price": float(curr_low),
                    "type": "LOW",
                    "projected": True
                })
                pivots.append({
                    "idx": last_i,
                    "bar_idx": last_bar,
                    "time": last_time,
                    "price": last_high,
                    "type": "HIGH",
                    "projected": True
                })

    return df, pivots
