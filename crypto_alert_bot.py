"""
Главный скрипт Telegram бота для отслеживания цен криптовалют.
"""

import logging
import asyncio
from telegram import BotCommand
from configparser import ConfigParser
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, JobQueue
)
from library.api_utils import fetch_price

"""Импорт обработчиков из папки scripts"""
try:
    from scripts.bot_handlers import (
        start, list_conditions, info, plot_command,
        handle_plot_pair, set_command, handle_set_params,
        delete_command, handle_delete_pair, user_settings,
        AWAITING_PLOT_PAIR, AWAITING_SET_PARAMS, AWAITING_DELETE_PAIR
    )
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from scripts.bot_handlers import (
        start, list_conditions, info, plot_command,
        handle_plot_pair, set_command, handle_set_params,
        delete_command, handle_delete_pair, user_settings,
        AWAITING_PLOT_PAIR, AWAITING_SET_PARAMS, AWAITING_DELETE_PAIR
    )

"""Настройка логирования"""
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

"""Чтение конфигурации"""
config = ConfigParser()
config.read('config.ini')
TOKEN = config['telegram']['token']
CHECK_INTERVAL = int(config['api']['check_interval'])


async def check_conditions(app: Application):
    """Фоновая задача для проверки условий трекинга"""
    logger.info("Фоновая проверка условий запущена.")
    while True:
        try:
            for user_id, conditions in list(user_settings.items()):
                for cond in conditions:
                    current_price = await fetch_price(cond['symbol'])
                    if current_price is None:
                        continue

                    last_checked_price = cond.get('last_checked_price', cond['start_price'])
                    change = ((current_price - last_checked_price) / last_checked_price) * 100

                    cond['last_checked_price'] = current_price

                    if abs(change) >= cond['percent']:
                        old_price = cond['last_notified_price']
                        cond['last_notified_price'] = current_price

                        text = (
                            f"📢 {cond['symbol']}: цена изменилась на {cond['percent']}%\n"
                            f"Старая цена: {old_price:.6f}\n"
                            f"Новая цена: {current_price:.6f}\n"
                            f"Изменение: {change:.2f}%\n"
                            f"Отслеживание продолжается..."
                        )
                        await app.bot.send_message(chat_id=user_id, text=text)

            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Ошибка в check_conditions: {e}")
            await asyncio.sleep(60)


def main():
    """Основная функция инициализации бота"""
    app = Application.builder().token(TOKEN).build()

    """Настройка обработчиков команд"""
    plot_handler = ConversationHandler(
        entry_points=[CommandHandler('plot', plot_command)],
        states={AWAITING_PLOT_PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plot_pair)]},
        fallbacks=[]
    )

    set_handler = ConversationHandler(
        entry_points=[CommandHandler('set', set_command)],
        states={AWAITING_SET_PARAMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_params)]},
        fallbacks=[]
    )

    delete_handler = ConversationHandler(
        entry_points=[CommandHandler('delete', delete_command)],
        states={AWAITING_DELETE_PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_pair)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_conditions))
    app.add_handler(CommandHandler('info', info))
    app.add_handler(plot_handler)
    app.add_handler(set_handler)
    app.add_handler(delete_handler)

    """Создаем JobQueue после инициализации Application"""
    app.job_queue.run_repeating(
        lambda ctx: asyncio.create_task(check_conditions(app)),
        interval=CHECK_INTERVAL,
        first=10
    )

    """Настройка меню команд"""
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            BotCommand("start", "Запустить бота"),
            BotCommand("set", "Задать условие отслеживания"),
            BotCommand("list", "Список текущих условий"),
            BotCommand("plot", "Показать график"),
            BotCommand("delete", "Удалить условие отслеживания"),
            BotCommand("info", "Информация о боте")
        ])

    app.post_init = post_init
    app.run_polling()


if __name__ == '__main__':
    main()
