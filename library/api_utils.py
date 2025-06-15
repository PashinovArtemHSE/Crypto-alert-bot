"""
Модуль с универсальными функциями для работы с API криптобирж.
"""

import aiohttp
import logging
from configparser import ConfigParser

config = ConfigParser()
config.read('config.ini')
BASE_URL = config['api']['binance_base_url']


async def fetch_price(symbol):
    """
    Получает текущую цену торговой пары с Binance API.

    Args:
        symbol (str): Торговая пара (например 'BTCUSDT')

    Returns:
        float: Текущая цена или None в случае ошибки
    """
    url = f'{BASE_URL}/ticker/price?symbol={symbol.upper()}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logging.error(f"Ошибка API: {resp.status}")
                    return None
                data = await resp.json()
                return float(data['price'])
    except Exception as e:
        logging.error(f"Ошибка при получении цены: {e}")
        return None


async def fetch_klines(symbol, interval='1m', limit=60):
    """
    Получает данные для построения графика.

    Args:
        symbol (str): Торговая пара
        interval (str): Интервал данных (1m, 5m и т.д.)
        limit (int): Количество точек данных

    Returns:
        list: Данные или None при ошибке
    """
    url = f'{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit={limit}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logging.error(f"Ошибка API: {resp.status}")
                    return None
                return await resp.json()
    except Exception as e:
        logging.error(f"Ошибка при получении исторических данных: {e}")
        return None
