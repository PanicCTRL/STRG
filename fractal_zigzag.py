"""
fractal_zigzag.py
Модуль вычисления фрактального Зиг-Зага (Коробочка №1).
- Чистые 5-баровые фракталы Билла Вильямса
- Построение макроструктуры (Major Swings / Trend Legs):
  * При обновлении минимума (перелоу) в нисходящей волне промежуточные откаты схлопываются,
    продлевая движение от начального High напрямую к новому Low.
  * При обновлении максимума (перехай) в восходящей волне промежуточные откаты схлопываются,
    продлевая движение от начального Low напрямую к новому High.
- Поддержка сквозного анализа любого таймфрейма (M5, M15, etc.)
"""

import numpy as np
import pandas as pd


def filter_macro_swings(pivots):
    """
    Фильтрует сырые чередующиеся пивоты по правилам макроструктуры Доу:
    схлопывает внутренние откаты при продолжении тренда (перехай / перелоу).
    """
    if not pivots or len(pivots) < 2:
        return pivots

    confirmed_legs = []

    anchor = pivots[0]
    state = "DOWN" if anchor["type"] == "HIGH" else "UP"
    highest = anchor if state == "UP" else None
    lowest = anchor if state == "DOWN" else None
    last_high = None
    last_low = None

    for p in pivots[1:]:
        if state == "UP":
            if p["type"] == "HIGH":
                if highest is None or p["price"] >= highest["price"]:
                    highest = p
                    last_low = None
                    last_high = None
                else:
                    last_high = p
            elif p["type"] == "LOW":
                if highest is not None and last_high is not None and last_low is not None:
                    # Разворот вниз: цена пробила минимум отката last_low
                    if p["price"] < last_low["price"]:
                        confirmed_legs.append(anchor)
                        anchor = highest
                        lowest = p
                        highest = None
                        last_high = None
                        last_low = None
                        state = "DOWN"
                        continue
                last_low = p

        elif state == "DOWN":
            if p["type"] == "LOW":
                if lowest is None or p["price"] <= lowest["price"]:
                    lowest = p
                    last_high = None
                    last_low = None
                else:
                    last_low = p
            elif p["type"] == "HIGH":
                if lowest is not None and last_low is not None and last_high is not None:
                    # Разворот вверх: цена пробила максимум отскока last_high
                    if p["price"] > last_high["price"]:
                        confirmed_legs.append(anchor)
                        anchor = lowest
                        highest = p
                        lowest = None
                        last_high = None
                        last_low = None
                        state = "UP"
                        continue
                last_high = p

    # Добавляем финальные незакрытые колена
    if anchor not in confirmed_legs:
        confirmed_legs.append(anchor)
    if state == "UP" and highest and highest not in confirmed_legs:
        confirmed_legs.append(highest)
    elif state == "DOWN" and lowest and lowest not in confirmed_legs:
        confirmed_legs.append(lowest)

    return confirmed_legs


def calculate_fractal_zigzag(df_candles, mode="macro"):
    """
    Рассчитывает чередующийся Зиг-Заг по подтверждённым 5-баровым фракталам.

    :param df_candles: DataFrame со свечами (open, high, low, close, time, bar_idx)
    :param mode: 'macro' (макроструктура Доу, схлопывание откатов) или 'raw' (сырые фракталы)
    :return: (df_candles, pivots)
      pivots: список словарей {
          'idx': int,           # Индекс бара в df_candles
          'bar_idx': float,     # Значение bar_idx для отрисовки на оси X
          'time': pd.Timestamp, # Время бара
          'price': float,       # Цена экстремума (High или Low)
          'type': 'HIGH'/'LOW'  # Тип пивота
      }
    """
    if df_candles is None or len(df_candles) < 5:
        return df_candles, []

    df = df_candles.copy()
    n = len(df)

    highs = df["high"].values
    lows = df["low"].values
    bar_indices = df["bar_idx"].values if "bar_idx" in df.columns else np.arange(n)
    times = df["time"].values if "time" in df.columns else np.arange(n)

    # 1. Вычисляем 5-баровые фракталы, если их еще нет в DataFrame
    f_up = np.full(n, np.nan)
    f_down = np.full(n, np.nan)

    for i in range(2, n - 2):
        if (highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and
            highs[i] > highs[i + 1] and highs[i] > highs[i + 2]):
            f_up[i] = highs[i]

        if (lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and
            lows[i] < lows[i + 1] and lows[i] < lows[i + 2]):
            f_down[i] = lows[i]

    df["fractal_up"] = f_up
    df["fractal_down"] = f_down

    # 2. Построение сырого чередующегося Зиг-Зага (ЗигЗаг по подтвержденным фракталам)
    # Фрактал на баре idx подтверждается на баре idx + 2.
    raw_pivots = []

    for i in range(2, n):
        idx = i - 2
        has_up = not np.isnan(f_up[idx])
        has_down = not np.isnan(f_down[idx])

        if has_up:
            p_val = float(f_up[idx])
            b_x = float(bar_indices[idx])
            t_val = times[idx]

            if not raw_pivots:
                raw_pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"})
            elif raw_pivots[-1]["type"] == "HIGH":
                # Тот же тип: если новый High выше текущего -> переносим пик выше
                if p_val > raw_pivots[-1]["price"]:
                    raw_pivots[-1] = {"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"}
            else:
                # Чередование: после LOW пришел HIGH -> фиксируем новую вершину
                raw_pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"})

        if has_down:
            p_val = float(f_down[idx])
            b_x = float(bar_indices[idx])
            t_val = times[idx]

            if not raw_pivots:
                raw_pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"})
            elif raw_pivots[-1]["type"] == "LOW":
                # Тот же тип: если новый Low ниже текущего -> переносим дно ниже
                if p_val < raw_pivots[-1]["price"]:
                    raw_pivots[-1] = {"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"}
            else:
                # Чередование: после HIGH пришел LOW -> фиксируем новую низину
                raw_pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"})

    if mode == "macro":
        pivots = filter_macro_swings(raw_pivots)
    else:
        pivots = raw_pivots

    return df, pivots
