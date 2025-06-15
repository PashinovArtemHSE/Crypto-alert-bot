"""
Модуль с обработчиками команд Telegram бота.
"""

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from library.api_utils import fetch_price
import aiohttp
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from io import BytesIO
from configparser import ConfigParser

config = ConfigParser()
config.read('config.ini')
MAX_PAIRS_PER_USER = int(config['limits']['max_pairs_per_user'])

"""Глобальная переменная для хранения настроек пользователей"""
user_settings = {}

"""Этапы диалога"""
AWAITING_PLOT_PAIR, AWAITING_SET_PARAMS, AWAITING_DELETE_PAIR = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для отслеживания аномалий цен криптовалют.\n\n"
        "🧭 Возможности:\n"
        "/set – задать условия отслеживания\n"
        "/list – список текущих условий\n"
        "/plot – показать график\n"
        "/delete – удалить условие отслеживания\n"
        "/info - информация о боте\n\n"
    )


async def list_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /list"""
    user_id = update.effective_user.id
    user_data = user_settings.get(user_id, [])
    if not user_data:
        await update.message.reply_text("📭 У вас нет активных условий.")
        return

    text = "📋 Ваши условия:\n"
    for entry in user_data:
        text += f"🔹 {entry['symbol']} | {entry['percent']}%\n"
    await update.message.reply_text(text)


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /info"""
    await update.message.reply_text(
        "ℹ️ <b>Информация о боте</b>\n\n"
        "Этот бот помогает отслеживать резкие изменения цен криптовалют на Binance.\n\n"
        "<b>Возможности:</b>\n"
        "🔹 Отслеживание изменений цены в процентах за указанный период\n"
        "🔹 Автоматическое уведомление при достижении порога\n"
        "🔹 График изменения цены за последний час\n"
        "🔹 Удобные кнопки команд\n\n"
        "<b>Команды и примеры:</b>\n"
        "📝 <b>/set</b> – задать условие отслеживания:\n"
        "Пример: <code>/set</code> → <code>BTCUSDT 5</code>\n\n"
        "📋 <b>/list</b> – список ваших условий\n\n"
        "📈 <b>/plot</b> – график пары:\n"
        "Пример: <code>/plot</code> → <code>ETHUSDT</code>.\n\n"
        "🗑 <b>/delete</b> – удалить условие отслеживания:\n"
        "Пример: <code>/delete</code> → <code>BTCUSDT</code>.",
        parse_mode='HTML',
    )


async def plot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /plot"""
    await update.message.reply_text("📈 Введите торговую пару для построения графика, например: BTCUSDT")
    return AWAITING_PLOT_PAIR


async def handle_plot_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода пары для /plot"""
    symbol = update.message.text.strip().upper()
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=60)
    url = (
        f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&'
        f'startTime={int(start_time.timestamp() * 1000)}&endTime={int(end_time.timestamp() * 1000)}'
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        if not isinstance(data, list) or len(data) == 0:
            await update.message.reply_text("❌ Невозможно получить данные или пара не найдена.")
            return ConversationHandler.END

        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close"] = df["close"].astype(float)

        mean_price = np.mean(df["close"])
        std_price = np.std(df["close"])

        plt.figure(figsize=(10, 4))
        plt.plot(df["timestamp"], df["close"], label=f'{symbol}')
        plt.axhline(mean_price, color='orange', linestyle='--', label='Среднее')
        plt.fill_between(df["timestamp"], mean_price - std_price, mean_price + std_price, color='orange', alpha=0.1,
                         label='±1σ')
        plt.title(f"{symbol} – последние 60 минут")
        plt.xlabel("Время")
        plt.ylabel("Цена")
        plt.grid(True)
        plt.legend()

        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        await update.message.reply_photo(photo=buf)
    except Exception as e:
        logger.error(f"Ошибка при построении графика: {e}")
        await update.message.reply_text("❌ Ошибка при построении графика.")
    return ConversationHandler.END


async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /set"""
    await update.message.reply_text("⚙ Введите параметры в формате: ПАРА ПРОЦЕНТ\nПример: BTCUSDT 5")
    return AWAITING_SET_PARAMS


async def handle_set_params(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода параметров для /set"""
    user_id = update.effective_user.id
    parts = update.message.text.strip().split()
    if len(parts) != 2:
        await update.message.reply_text("❌ Неверный формат. Используйте: ПАРА ПРОЦЕНТ")
        return ConversationHandler.END

    symbol, percent = parts
    try:
        percent = float(percent)
        if percent < 0.01 or percent > 100:
            await update.message.reply_text("❌ Процент должен быть между 0.01 и 100")
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Неверные данные.")
        return ConversationHandler.END

    current_price = await fetch_price(symbol)
    if current_price is None:
        await update.message.reply_text("❌ Не удалось получить текущую цену.")
        return ConversationHandler.END

    """Проверяем количество уже отслеживаемых пар"""
    user_pairs = user_settings.get(user_id, [])
    if len(user_pairs) >= MAX_PAIRS_PER_USER:
        await update.message.reply_text(f"❌ Вы уже отслеживаете максимальное количество пар ({MAX_PAIRS_PER_USER}).")
        return ConversationHandler.END

    """Проверяем, не отслеживается ли уже эта пара"""
    for entry in user_pairs:
        if entry['symbol'] == symbol.upper():
            await update.message.reply_text(f"❌ Пара {symbol.upper()} уже отслеживается.")
            return ConversationHandler.END

    entry = {
        'symbol': symbol.upper(),
        'percent': percent,
        'start_price': current_price,
        'last_notified_price': current_price,
        'last_checked_price': current_price
    }

    user_settings.setdefault(user_id, []).append(entry)
    await update.message.reply_text(
        f"✅ Буду отслеживать {symbol.upper()} на изменение {percent}%.\n"
        f"Текущая цена: {current_price:.6f}"
    )
    return ConversationHandler.END


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /delete"""
    await update.message.reply_text("🗑 Введите торговую пару для удаления из отслеживания, например: BTCUSDT")
    return AWAITING_DELETE_PAIR


async def handle_delete_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода пары для удаления"""
    user_id = update.effective_user.id
    symbol = update.message.text.strip().upper()

    user_data = user_settings.get(user_id, [])
    new_conditions = [cond for cond in user_data if cond['symbol'] != symbol]

    if len(new_conditions) == len(user_data):
        await update.message.reply_text(f"⚠️ У вас не было условий для {symbol}.")
        return ConversationHandler.END

    if new_conditions:
        user_settings[user_id] = new_conditions
    else:
        user_settings.pop(user_id, None)

    await update.message.reply_text(f"✅ Все условия для {symbol} удалены.")
    return ConversationHandler.END
