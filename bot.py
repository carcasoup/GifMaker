import telebot
import io
import zipfile
from PIL import Image
import os
from telebot import types

from secr import TOKEN

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Состояния для управления диалогом
class GifStates:
    NONE = None
    WAITING_FOR_ARCHIVE = "waiting_for_archive"
    WAITING_FOR_FPS = "waiting_for_fps"

# Хранилище данных пользователей
user_data = {}

# Помощник для получения и установки состояния
def get_state(chat_id):
    return user_data.get(chat_id, {}).get('state')

def set_state(chat_id, state):
    if chat_id not in user_data:
        user_data[chat_id] = {}
    user_data[chat_id]['state'] = state

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    set_state(chat_id, GifStates.NONE)
    bot.send_message(chat_id, "Привет! Для создания GIF отправь архив с фотографиями, используя команду /gif.")

# Обработчик команды /gif
@bot.message_handler(commands=['gif'])
def gif_command(message):
    chat_id = message.chat.id
    set_state(chat_id, GifStates.WAITING_FOR_ARCHIVE)
    bot.send_message(chat_id, "Отправь архив с фотографиями (ZIP, содержащий изображения) для создания GIF.")

# Обработчик архива ZIP
@bot.message_handler(content_types=['document'])
def handle_archive(message):
    chat_id = message.chat.id
    if get_state(chat_id) != GifStates.WAITING_FOR_ARCHIVE:
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        # Сохраняем байты архива
        user_data[chat_id]['archive'] = downloaded
        set_state(chat_id, GifStates.WAITING_FOR_FPS)
        bot.send_message(chat_id, "Теперь отправь количество кадров в секунду (FPS), например, 10 или 15.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении файла: {e}")
        set_state(chat_id, GifStates.NONE)

# Обработчик текста (FPS)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_fps(message):
    chat_id = message.chat.id
    if get_state(chat_id) != GifStates.WAITING_FOR_FPS:
        return
    text = message.text.strip()
    try:
        fps = int(text)
        if fps <= 0:
            raise ValueError()
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, отправь корректное положительное число для FPS.")
        return

    archive_bytes = user_data.get(chat_id, {}).get('archive')
    if not archive_bytes:
        bot.send_message(chat_id, "Ошибка: архив не найден. Начните заново командой /gif.")
        set_state(chat_id, GifStates.NONE)
        return

    # Обработка архива
    try:
        archive_io = io.BytesIO(archive_bytes)
        with zipfile.ZipFile(archive_io) as z:
            image_files = [
                f for f in z.namelist()
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
                   and not f.startswith("__MACOSX/")
                   and not os.path.basename(f).startswith("._")
            ]
            if not image_files:
                bot.send_message(chat_id, "В архиве не найдено изображений.")
                set_state(chat_id, GifStates.NONE)
                return

            image_files.sort()
            images = []
            for fname in image_files:
                with z.open(fname) as file:
                    img = Image.open(file)
                    images.append(img.copy())
                    img.close()
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при извлечении изображений из архива: {e}")
        set_state(chat_id, GifStates.NONE)
        return

    # Создание GIF
    try:
        gif_io = io.BytesIO()
        duration = int(1000 / fps)
        images[0].save(
            gif_io,
            format='GIF',
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0
        )
        gif_io.seek(0)
        # Отправка GIF с указанием имени файла
        doc = types.InputFile(gif_io, 'result.gif')
        bot.send_document(chat_id, doc, caption="Вот ваш GIF!")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при создании GIF: {e}")
    finally:
        set_state(chat_id, GifStates.NONE)
        user_data.pop(chat_id, None)

if __name__ == '__main__':
    bot.infinity_polling()
