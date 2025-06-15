"""
Модуль для построения графиков цен криптовалют.
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from io import BytesIO


def create_price_plot(data, symbol):
    """
    Создает график цен из данных.

    Args:
        data (list): Данные от API
        symbol (str): Название торговой пары

    Returns:
        BytesIO: Буфер с изображением графика
    """
    if not data or len(data) == 0:
        raise ValueError("Нет данных для построения графика")

    try:
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close"] = df["close"].astype(float)

        plt.style.use('seaborn')
        plt.figure(figsize=(10, 4))
        plt.plot(df["timestamp"], df["close"], label=f'{symbol}', linewidth=2)

        mean_price = np.mean(df["close"])
        std_price = np.std(df["close"])

        plt.axhline(mean_price, color='orange', linestyle='--', label='Среднее')
        plt.fill_between(df["timestamp"], mean_price - std_price, mean_price + std_price, color='orange',
                         alpha=0.1, label='±1σ')

        plt.title(f"{symbol} – последние 60 минут", pad=20)
        plt.xlabel("Время", labelpad=10)
        plt.ylabel("Цена", labelpad=10)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()

        return buf
    except Exception as e:
        plt.close()
        raise RuntimeError(f"Ошибка при построении графика: {str(e)}")
