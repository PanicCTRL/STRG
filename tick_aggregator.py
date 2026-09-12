"""
tick_aggregator.py
Быстрый парсер тиков и сборщик японских свечей (OHLCV) + расчёт фракталов.
"""

import pandas as pd
import numpy as np
from datetime import datetime


class TickAggregator:
    def __init__(self, file_path=None):
        self.file_path = file_path
        self.df_ticks = None

    def load_file(self, file_path=None):
        """Быстро загружает тиковый файл Финама (DATE, TIME, LAST, VOL)."""
        if file_path:
            self.file_path = file_path
        if not self.file_path:
            return False

        # Формат Финама: <TICKER>,<PER>,<DATE>,<TIME>,<LAST>,<VOL>
        df = pd.read_csv(
            self.file_path,
            usecols=[2, 3, 4, 5],
            names=["DATE", "TIME", "PRICE", "VOL"],
            header=0,
            dtype={"DATE": str, "TIME": str, "PRICE": float, "VOL": int}
        )

        # Собираем datetime: YYYYMMDD + HHMMSS
        # Дополняем TIME нулями слева до 6 символов, если нужно (например 65906 -> 065906)
        time_str = df["TIME"].str.zfill(6)
        dt_str = df["DATE"] + time_str
        df["DATETIME"] = pd.to_datetime(dt_str, format="%Y%m%d%H%M%S")

        df = df.sort_values("DATETIME", kind="stable").reset_index(drop=True)
        self.df_ticks = df
        return True

    def get_candles(self, tf_str="5M"):
        """
        Агрегирует тики в свечи OHLCV под заданный таймфрейм:
        '1M', '3M', '5M', '15M', '1H'
        """
        if self.df_ticks is None or self.df_ticks.empty:
            return pd.DataFrame()

        # Маппинг таймфреймов в формат pandas resample
        tf_map = {
            "1M": "1min",
            "3M": "3min",
            "5M": "5min",
            "15M": "15min",
            "1H": "1h"
        }
        rule = tf_map.get(tf_str, "5min")

        # Ресэмплинг
        df_resampled = self.df_ticks.set_index("DATETIME")
        ohlc = df_resampled["PRICE"].resample(rule, closed="left", label="left").ohlc()
        volume = df_resampled["VOL"].resample(rule, closed="left", label="left").sum()

        candles = pd.concat([ohlc, volume], axis=1).dropna().reset_index()
        candles.columns = ["time", "open", "high", "low", "close", "volume"]

        # Добавляем unix timestamp в секундах и индекс баров
        candles["timestamp"] = candles["time"].astype("int64") // 10**9
        candles["bar_idx"] = np.arange(len(candles))

        # Считаем фракталы
        candles = self.calculate_fractals(candles)
        return candles

    @staticmethod
    def calculate_fractals(df_candles):
        """
        Классический расчет 5-баровых фракталов Билла Вильямса:
        - Up Fractal: High[i] выше High[i-2], High[i-1], High[i+1], High[i+2]
        - Down Fractal: Low[i] ниже Low[i-2], Low[i-1], Low[i+1], Low[i+2]
        """
        df = df_candles.copy()
        n = len(df)
        df["fractal_up"] = np.nan
        df["fractal_down"] = np.nan

        if n < 5:
            return df

        highs = df["high"].values
        lows = df["low"].values

        for i in range(2, n - 2):
            # Проверка верхнего фрактала (High)
            if (highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and
                highs[i] > highs[i + 1] and highs[i] > highs[i + 2]):
                df.at[i, "fractal_up"] = highs[i]

            # Проверка нижнего фрактала (Low)
            if (lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and
                lows[i] < lows[i + 1] and lows[i] < lows[i + 2]):
                df.at[i, "fractal_down"] = lows[i]

        return df
