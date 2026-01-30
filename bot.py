import os
import random
import logging
import textwrap
import io
import json
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- КОНФИГУРАЦИЯ ---
# На сервере токен берем из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ОПРЕДЕЛЕНИЕ ПУТЕЙ ---
# Определяем, где лежит именно ЭТОТ файл (bot.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Все пути строим от BASE_DIR
PATH_MOON = os.path.join(BASE_DIR, "images", "moon_guardians")
PATH_SUN = os.path.join(BASE_DIR, "images", "sun_guardians")
PATH_QUOTES_JSON = os.path.join(BASE_DIR, "quotes.json")
PATH_QUOTE_BG = os.path.join(BASE_DIR, "images", "quote_background.jpg")
PATH_FONT = os.path.join(BASE_DIR, "fonts", "regular.ttf")

# Кнопки
BUTTON_MOON = "Хранители луны 🌙"
BUTTON_SUN = "Хранители солнца ☀️"
BUTTON_QUOTE = "Мудрость дня ✨"

# --- ФУНКЦИИ ---

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
    keyboard = [[BUTTON_MOON, BUTTON_SUN], [BUTTON_QUOTE]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Добро пожаловать! Выбери кнопку:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == BUTTON_MOON:
        await send_photo_from_folder(update, PATH_MOON)
    elif text == BUTTON_SUN:
        await send_photo_from_folder(update, PATH_SUN)
    elif text == BUTTON_QUOTE:
        await send_quote(update, context)

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
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()