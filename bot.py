import os
import random
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Включаем логирование, чтобы видеть ошибки в консоли сервера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Названия кнопок
BUTTON_MOON = "Хранители луны 🌙"
BUTTON_SUN = "Хранители солнца ☀️"

# Пути к папкам с изображениями
# Мы предполагаем, что папки лежат в той же директории, что и бот
PATH_MOON = "images/moon_guardians"
PATH_SUN = "images/sun_guardians"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение и устанавливает клавиатуру."""
    keyboard = [
        [BUTTON_MOON, BUTTON_SUN]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Выбери свою сторону:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки."""
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == BUTTON_MOON:
        await send_random_photo(update, PATH_MOON)
    elif text == BUTTON_SUN:
        await send_random_photo(update, PATH_SUN)
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки на клавиатуре.")

async def send_random_photo(update: Update, folder_path: str):
    """Выбирает случайный файл из папки и отправляет его."""
    try:
        # Проверяем существование папки
        if not os.path.exists(folder_path):
            await update.message.reply_text(f"Ошибка: Папка {folder_path} не найдена на сервере.")
            return

        # Получаем список всех файлов в папке
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        
        if not files:
            await update.message.reply_text("В этой папке пока нет изображений.")
            return

        # Выбираем случайное фото
        random_file = random.choice(files)
        file_path = os.path.join(folder_path, random_file)

        # Отправляем фото
        with open(file_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text("Произошла ошибка при загрузке изображения.")

def main():
    """Запуск бота."""
    # Токен берем из переменных окружения для безопасности
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        print("Ошибка: Переменная окружения TELEGRAM_TOKEN не задана!")
        return

    # Создаем приложение
    application = Application.builder().token(token).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()