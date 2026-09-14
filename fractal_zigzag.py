"""
fractal_zigzag.py
Модуль вычисления фрактального Зиг-Зага (Коробочка №1).
- Чистые 5-баровые фракталы Билла Вильямса
- Строгое чередование вершин и низин: HIGH -> LOW -> HIGH -> LOW
- Обновление экстремума при продолжении волны в ту же сторону
- Поддержка сквозного анализа любого таймфрейма (M5, M15, etc.)
"""

import numpy as np
import pandas as pd


def calculate_fractal_zigzag(df_candles):
    """
    Рассчитывает чередующийся Зиг-Заг по подтверждённым 5-баровым фракталам.

    :param df_candles: DataFrame со свечами (open, high, low, close, time, bar_idx)
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

    # 2. Построение чередующегося Зиг-Зага (ЗигЗаг по подтвержденным фракталам)
    # Фрактал на баре idx подтверждается на баре idx + 2.
    pivots = []

    for i in range(2, n):
        idx = i - 2
        has_up = not np.isnan(f_up[idx])
        has_down = not np.isnan(f_down[idx])

        if has_up:
            p_val = float(f_up[idx])
            b_x = float(bar_indices[idx])
            t_val = times[idx]

            if not pivots:
                pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"})
            elif pivots[-1]["type"] == "HIGH":
                # Тот же тип: если новый High выше текущего -> переносим пик выше
                if p_val > pivots[-1]["price"]:
                    pivots[-1] = {"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"}
            else:
                # Чередование: после LOW пришел HIGH -> фиксируем новую вершину
                pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "HIGH"})

        if has_down:
            p_val = float(f_down[idx])
            b_x = float(bar_indices[idx])
            t_val = times[idx]

            if not pivots:
                pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"})
            elif pivots[-1]["type"] == "LOW":
                # Тот же тип: если новый Low ниже текущего -> переносим дно ниже
                if p_val < pivots[-1]["price"]:
                    pivots[-1] = {"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"}
            else:
                # Чередование: после HIGH пришел LOW -> фиксируем новую низину
                pivots.append({"idx": idx, "bar_idx": b_x, "time": t_val, "price": p_val, "type": "LOW"})

    return df, pivots