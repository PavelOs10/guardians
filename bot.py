import os
import random
import logging
import textwrap
import io
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- КОНФИГУРАЦИЯ ---
# На сервере токен берем из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ОПРЕДЕЛЕНИЕ  ПУТЕЙ ---
# Определяем, где лежит именно ЭТОТ файл (bot.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Все пути строим от BASE_DIR
PATH_MOON = os.path.join(BASE_DIR, "images", "moon_guardians")
PATH_SUN = os.path.join(BASE_DIR, "images", "sun_guardians")
PATH_QUOTES_JSON = os.path.join(BASE_DIR, "quotes.json")
PATH_DAY_FORECASTS_JSON = os.path.join(BASE_DIR, "day_forecasts.json")
PATH_QUOTE_BG = os.path.join(BASE_DIR, "images", "quote_background.jpg")
PATH_PERSONAL_BG = os.path.join(BASE_DIR, "images", "personal_card_bg.jpg")
PATH_FONT = os.path.join(BASE_DIR, "fonts", "regular.ttf")

# Кнопки
BUTTON_MOON = "Хранители луны 🌙"
BUTTON_SUN = "Хранители солнца ☀️"
BUTTON_QUOTE = "Мудрость дня ✨"
BUTTON_PERSONAL = "Индивидуальная карта дня 🔮"

# Состояния для ConversationHandler
GET_BIRTHDAY = 1

# --- ФУНКЦИИ ---

def simplify_number(num):
    """Упрощает число до диапазона 1-22 (нумерологическое сложение, но останавливаемся на 22)."""
    # Если число уже от 1 до 22, возвращаем как есть
    if 1 <= num <= 22:
        return num
    
    # Упрощаем до тех пор, пока не получим число от 1 до 22
    while num > 22:
        # Складываем все цифры числа
        num = sum(int(digit) for digit in str(num))
        # Если после сложения получилось больше 22, продолжаем
        # Но если получилось 22 или меньше - останавливаемся
    
    return num

def calculate_personal_day(birth_day, current_day=None):
    """Рассчитывает персональный день для пользователя по правилам."""
    # Упрощаем день рождения до 1-22
    birth_simple = simplify_number(birth_day)
    
    # Получаем текущий день месяца
    if current_day is None:
        current_day = datetime.now().day
    
    # Упрощаем текущий день до 1-22
    current_simple = simplify_number(current_day)
    
    # Складываем упрощенные числа
    raw_sum = birth_simple + current_simple
    
    # Упрощаем результат до 1-22
    personal_day = simplify_number(raw_sum)
    
    # Логирование для отладки
    logger.info(f"Расчет: {birth_day}→{birth_simple} + {current_day}→{current_simple} = {raw_sum}→{personal_day}")
    
    return personal_day, birth_simple, current_simple

def load_quotes():
    """Загружает цитаты из JSON."""
    if not os.path.exists(PATH_QUOTES_JSON):
        logger.error(f"Файл JSON не найден по пути: {PATH_QUOTES_JSON}")
        return []
    
    try:
        with open(PATH_QUOTES_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения JSON: {e}")
        return []

def load_day_forecasts():
    """Загружает прогнозы дней из JSON."""
    if not os.path.exists(PATH_DAY_FORECASTS_JSON):
        logger.error(f"Файл прогнозов не найден по пути: {PATH_DAY_FORECASTS_JSON}")
        return {}
    
    try:
        with open(PATH_DAY_FORECASTS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения JSON прогнозов: {e}")
        return {}

def get_personal_card_image():
    """Возвращает универсальное изображение для индивидуальной карты."""
    try:
        if os.path.exists(PATH_PERSONAL_BG):
            img = Image.open(PATH_PERSONAL_BG)
            img = img.convert("RGB")
            img = img.resize((800, 600), Image.Resampling.LANCZOS)
            
            bio = io.BytesIO()
            bio.name = 'personal_card.jpg'
            img.save(bio, 'JPEG', quality=90)
            bio.seek(0)
            return bio
        else:
            logger.warning(f"Фоновое изображение не найдено: {PATH_PERSONAL_BG}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке изображения карты: {e}")
        return None

def create_quote_image(quote_data):
    """Рисует картинку с цитатой, вписывая её в заданную рамку."""
    text = quote_data.get('text', '')
    author = quote_data.get('author', '')

    try:
        # Пытаемся открыть фон
        if os.path.exists(PATH_QUOTE_BG):
            img = Image.open(PATH_QUOTE_BG).convert("RGB")
        else:
            logger.warning(f"Фон {PATH_QUOTE_BG} не найден, использую заливку.")
            img = Image.new('RGB', (800, 600), color=(20, 20, 40))

        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        # --- НАСТРОЙКИ РАМКИ ---
        ref_w, ref_h = 800, 600
        scale_x = width / ref_w
        scale_y = height / ref_h

        # Отступы
        margin_left = 115 * scale_x
        margin_right = 110 * scale_x
        margin_top = 132 * scale_y
        margin_bottom = 110 * scale_y

        # Безопасная зона
        box_width = width - margin_left - margin_right
        box_height = height - margin_top - margin_bottom
        
        box_center_x = margin_left + (box_width / 2)
        box_center_y = margin_top + (box_height / 2)
        
        # --- ПОДБОР ШРИФТА ---
        font_size = int(box_width / 14)
        min_font_size = 14
        
        final_wrapped_text = ""
        final_font = None
        final_font_author = None
        final_text_h = 0
        final_author_h = 0
        spacer = 0

        # Уменьшаем шрифт, пока текст не влезет
        while font_size >= min_font_size:
            try:
                if os.path.exists(PATH_FONT):
                    font = ImageFont.truetype(PATH_FONT, font_size)
                    font_author = ImageFont.truetype(PATH_FONT, int(font_size * 0.7))
                else:
                    font = ImageFont.load_default()
                    font_author = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
                font_author = ImageFont.load_default()

            avg_char_width = font_size * 0.55 
            chars_per_line = int(box_width / avg_char_width)
            if chars_per_line < 1: chars_per_line = 1
            
            wrapped_text = textwrap.fill(text, width=chars_per_line)

            bbox_text = draw.textbbox((0, 0), wrapped_text, font=font)
            text_h = bbox_text[3] - bbox_text[1]
            
            bbox_author = draw.textbbox((0, 0), author, font=font_author)
            author_h = bbox_author[3] - bbox_author[1]
            
            spacer = font_size * 1.2
            total_block_h = text_h + spacer + author_h
            
            if total_block_h <= box_height:
                final_wrapped_text = wrapped_text
                final_font = font
                final_font_author = font_author
                final_text_h = text_h
                final_author_h = author_h
                break
            
            font_size -= 2
        
        if final_font is None:
             final_wrapped_text = wrapped_text
             final_font = font
             final_font_author = font_author
             final_text_h = text_h
             final_author_h = author_h

        # --- ОТРИСОВКА ---
        total_content_height = final_text_h + spacer + final_author_h
        start_y = box_center_y - (total_content_height / 2)
        
        # Рисуем Цитату
        quote_y = start_y + (final_text_h / 2)
        draw.text(
            (box_center_x, quote_y), 
            final_wrapped_text, 
            font=final_font, 
            fill="white", 
            anchor="mm", 
            align="center"
        )
        
        # Рисуем Автора
        author_y = start_y + final_text_h + spacer + (final_author_h / 2)
        author_x = width - margin_right
        
        draw.text(
            (author_x, author_y), 
            author,
            font=final_font_author, 
            fill="#DDDDDD", 
            anchor="rm", 
            align="right"
        )

        bio = io.BytesIO()
        bio.name = 'quote.jpg'
        img.save(bio, 'JPEG')
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"Ошибка при создании картинки: {e}")
        return None

# --- ОБРАБОТЧИКИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [BUTTON_MOON, BUTTON_SUN],
        [BUTTON_QUOTE, BUTTON_PERSONAL]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Добро пожаловать! Выбери кнопку:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == BUTTON_MOON:
        await send_photo_from_folder(update, PATH_MOON)
    elif text == BUTTON_SUN:
        await send_photo_from_folder(update, PATH_SUN)
    elif text == BUTTON_QUOTE:
        await send_quote(update, context)
    elif text == BUTTON_PERSONAL:
        await ask_birthday(update, context)
    else:
        # Если пользователь ввел что-то другое, покажем стартовое меню
        await start(update, context)

async def ask_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает дату рождения у пользователя."""
    await update.message.reply_text(
        "🔮 *Индивидуальная карта дня*\n\n"
        "Введите день вашего рождения (число от 1 до 31):\n"
        "Например: 15\n\n"
        "Месяц и год не важны, только день месяца.",
        parse_mode="Markdown"
    )
    return GET_BIRTHDAY

async def get_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает введенный день рождения и показывает персональную карту."""
    try:
        user_input = update.message.text.strip()
        birth_day = int(user_input)
        
        if birth_day < 1 or birth_day > 31:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректный день рождения (число от 1 до 31)."
            )
            return GET_BIRTHDAY
        
        # Рассчитываем персональный день
        current_day = datetime.now().day
        personal_day, birth_simple, current_simple = calculate_personal_day(birth_day, current_day)
        
        # Загружаем прогнозы
        forecasts = load_day_forecasts()
        
        if str(personal_day) not in forecasts:
            await update.message.reply_text(
                f"❌ Прогноз для дня {personal_day} не найден.\n"
                f"Ваш расчет: {birth_day} → {birth_simple} + {current_day} → {current_simple} = {personal_day}"
            )
            return ConversationHandler.END
        
        # Получаем прогноз
        forecast_data = forecasts[str(personal_day)]
        
        # Форматируем подробное описание расчета
        calculation_steps = f"📊 *Детальный расчет:*\n"
        calculation_steps += f"• Ваш день рождения: {birth_day}\n"
        
        if birth_day != birth_simple:
            calculation_steps += f"• Упрощаем: {birth_day} → {birth_simple} (нумерологическое сложение)\n"
        
        calculation_steps += f"• Сегодняшний день: {current_day}\n"
        
        if current_day != current_simple:
            calculation_steps += f"• Упрощаем: {current_day} → {current_simple} (нумерологическое сложение)\n"
        
        calculation_steps += f"• Складываем: {birth_simple} + {current_simple} = {birth_simple + current_simple}\n"
        
        if (birth_simple + current_simple) != personal_day:
            calculation_steps += f"• Упрощаем результат: {birth_simple + current_simple} → {personal_day}\n"
        
        # Создаем красивый текст для подписи
        caption = (
            f"✨ *ВАША ИНДИВИДУАЛЬНАЯ КАРТА ДНЯ* ✨\n\n"
            f"{calculation_steps}\n"
            f"🎯 *Ваш число сегодня: {personal_day}*\n"
            f"🔮 *Энергия дня: {forecast_data.get('title', '')}*\n\n"
            f"⭐ *Позитив дня:*\n"
            f"{forecast_data.get('positive', '')}\n\n"
            f"⚠️ *Негатив дня:*\n"
            f"{forecast_data.get('negative', '')}\n\n"
            f"💫 *Совет дня:*\n"
            f"{forecast_data.get('advice', '')}\n\n"
            f"────────────\n"
            f"_Пусть этот день принесет вам гармонию и успех!_"
        )
        
        # Показываем действие загрузки
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_photo"
        )
        
        # Получаем универсальное изображение
        img_bio = get_personal_card_image()
        
        if img_bio:
            await update.message.reply_photo(
                photo=img_bio,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            # Если изображение не найдено, отправляем только текст
            await update.message.reply_text(
                caption,
                parse_mode="Markdown"
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите ЧИСЛО от 1 до 31.\n"
            "Например: 15 или 3 или 27"
        )
        return GET_BIRTHDAY
    except Exception as e:
        logger.error(f"Ошибка при расчете карты дня: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при расчете. Попробуйте позже."
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог отменен. Используйте кнопки меню для навигации."
    )
    return ConversationHandler.END

async def send_photo_from_folder(update: Update, folder_path: str):
    if not os.path.exists(folder_path):
        logger.error(f"Путь не найден: {folder_path}")
        await update.message.reply_text(f"Ошибка: папка не найдена.\nОжидался путь: {folder_path}")
        return

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not files:
        await update.message.reply_text("В этой папке пусто.")
        return

    random_file = random.choice(files)
    with open(os.path.join(folder_path, random_file), 'rb') as photo:
        await update.message.reply_photo(photo=photo)

async def send_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = load_quotes()
    if not quotes:
        await update.message.reply_text(f"Не удалось найти цитаты.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    
    quote = random.choice(quotes)
    img_bio = create_quote_image(quote)
    
    if img_bio:
        await update.message.reply_photo(photo=img_bio, caption="Мудрость дня ✨")
    else:
        await update.message.reply_text("Не удалось создать картинку.")

def main():
    if not TOKEN:
        print("ОШИБКА: Переменная окружения TELEGRAM_TOKEN не задана!")
        return

    print(f"--- ЗАПУСК БОТА ---")
    print(f"Базовая директория: {BASE_DIR}")
    print(f"Токен: {'установлен' if TOKEN else 'НЕ НАЙДЕН'}")
    
    # Проверяем необходимые файлы
    print("\n--- ПРОВЕРКА ФАЙЛОВ ---")
    required_files = [
        (PATH_QUOTES_JSON, "quotes.json"),
        (PATH_DAY_FORECASTS_JSON, "day_forecasts.json"),
        (PATH_FONT, "fonts/regular.ttf"),
        (PATH_PERSONAL_BG, "images/personal_card_bg.jpg"),
        (PATH_QUOTE_BG, "images/quote_background.jpg"),
    ]
    
    for path, name in required_files:
        if os.path.exists(path):
            print(f"✓ {name}")
        else:
            print(f"✗ {name} - НЕ НАЙДЕН")
    
    print("\n--- ЗАГРУЗКА ДАННЫХ ---")
    
    # Загружаем цитаты для проверки
    quotes = load_quotes()
    print(f"Цитаты: {len(quotes)} записей")
    
    # Загружаем прогнозы для проверки
    forecasts = load_day_forecasts()
    print(f"Прогнозы: {len(forecasts)} дней")
    
    print("\n--- ЗАПУСК БОТА ---")
    
    application = Application.builder().token(TOKEN).build()
    
    # ConversationHandler для индивидуальной карты
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f'^{BUTTON_PERSONAL}$'), ask_birthday)
        ],
        states={
            GET_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthday)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^/'), cancel)
        ],
        allow_reentry=True
    )
    
    # Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен и готов к работе...")
    print("Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()