import telebot
import fitz
from PIL import Image, ImageDraw, ImageFont
from telebot import types
import threading
import os
import schedule
import time
from pytz import timezone
from datetime import datetime

# Токен вашего Telegram бота
BOT_TOKEN = '5767428724:AAHVsTsrkqLnAoEMmWTMdLXA8fC_jRHkykE'

# Создаем объект бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения состояний пользователей
user_states = {}

GROUP_CHAT_ID = "-1001916885105"
last_comment = None  # Для хранения последнего комментария
global homework_assigned
homework_assigned = False

log_chat_id = -1002044002900  # ID чата для логирования ошибок

# Устанавливаем временную зону Амстердама
amsterdam_tz = timezone('Europe/Amsterdam')

# Функция для отправки сообщений об ошибках
def send_error_log(message):
    try:
        bot.send_message(log_chat_id, f"Ошибка: {message}")
    except Exception as e:
        print(f"Не удалось отправить сообщение об ошибке: {e}")

# Функция для ежедневной проверки работы бота
def daily_check():
    try:
        bot.send_message(log_chat_id, "Бот работает нормально.")
    except Exception as e:
        send_error_log(f"Ошибка при отправке ежедневного уведомления: {e}")

def remind_teacher():
    global homework_assigned
    if not homework_assigned:
        chat_id = GROUP_CHAT_ID
        message = "@RinaPolianskaya Пожалуйста, задайте домашнее задание!\n\nДомашнего задание нет или урок не состоялся, команда - /no"
        bot.send_message(chat_id, message)

def check_homework_assigned():
    if not homework_assigned:
        remind_teacher()

def reset_homework_status():
    global homework_assigned
    homework_assigned = False

def send_homework_notification():
    try:
        chat_id = GROUP_CHAT_ID
        message = "Незабываем делать домашнее задание!"
        if last_comment:
            message += f"\n\nНапоминаю: {last_comment}"
        bot.send_message(chat_id, message)
    except Exception as e:
        send_error_log(f"Ошибка при отправке уведомления о домашнем задании: {type(e).__name__} - {str(e)}")

@bot.message_handler(commands=['no'])
def handle_no_homework_command(message):
    global homework_assigned
    homework_assigned = True
    bot.send_message(message.chat.id, "Домашнее задание отменено.")

@bot.message_handler(commands=['start'])
def handle_start_command(message):
    print("Received /start command")
    chat_id = GROUP_CHAT_ID

    user_id = message.from_user.id
    if user_id not in user_states:
        user_states[user_id] = {'step': None}
    user_states[user_id]['step'] = 'book'

    bot.send_message(chat_id, "Задаем домашнее задание\nВыберите книгу (1 - Vocabulary, 2 - Student's Book):")

@bot.message_handler(func=lambda message: message.text)
def handle_text_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    print(f"Received message from user {user_id}: {message.text}")

    if user_id not in user_states or 'step' not in user_states[user_id]:
        print(f"No active state for user {user_id}. Ignoring the message.")
        return

    step = user_states[user_id]['step']

    if step == 'book':
        user_states[user_id]['book'] = int(message.text)
        bot.send_message(chat_id, "Введите номер страницы:")
        user_states[user_id]['step'] = 'page'
    elif step == 'page':
        user_states[user_id]['page'] = int(message.text)
        bot.send_message(chat_id, "Введите задание (с комментарием):")
        user_states[user_id]['step'] = 'comment'
    elif step == 'comment':
        user_states[user_id]['comment'] = message.text
        global last_comment
        last_comment = message.text

        pdf_file_path = {
            1: "/BOT/EnglishBot/English_Vocabulary_in_Use_Pre_Intermediate_amp_Intermediate_2017.pdf",
            2: "/BOT/EnglishBot/New_English_File_-_Intermediate-_Student_39_s_Book.pdf",
        }

        book = user_states[user_id]['book']
        page_number = user_states[user_id]['page']
        comment = user_states[user_id]['comment']

        if book not in pdf_file_path:
            bot.send_message(chat_id, "Номер книги не верен")
            return

        pdf_file = pdf_file_path[book]

        # Генерируем имя файла для изображения
        image_file_path = f"page_{page_number}.jpg"

        # Открываем PDF-файл и извлекаем страницу в изображение
        pdf_document = fitz.open(pdf_file)
        if page_number < 0 or page_number >= len(pdf_document):
            bot.send_message(chat_id, "Недопустимый номер страницы.")
            return

        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap()
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Добавляем комментарий на изображение
        draw = ImageDraw.Draw(image)
        text_position = (10, 10)
        text_color = (255, 0, 0)
        outline_color = (255, 255, 255)  # Цвет обводки букв (белый)
        font_path = "/BOT/EnglishBot/ARIAL.TTF"
        font_size = 35
        font = ImageFont.truetype(font_path, font_size)

        # Создаем обводку букв
        for offset in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            outline_position = (text_position[0] + offset[0], text_position[1] + offset[1])
            draw.text(outline_position, comment, fill=outline_color, font=font)

        draw.text(text_position, comment, fill=text_color, font=font)
        image.save(image_file_path, "JPEG", quality=90)

        # Закрываем PDF-файл
        pdf_document.close()

        # Отправляем изображение с комментарием пользователю
        with open(image_file_path, 'rb') as image_file:
            bot.send_photo(chat_id, image_file)

        bot.send_message(chat_id, "Домашнее заданее задано! Спасибо")
        global homework_assigned
        homework_assigned = True

        # Удаляем файл после отправки
        os.remove(image_file_path)

        if user_id in user_states:
            print(f"Deleting state for user {user_id}")
            del user_states[user_id]  # Удаляем состояние пользователя
        else:
            print(f"No state found for user {user_id}")

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Настройка расписания с учетом амстердамского времени
    schedule.every().tuesday.at("09:00").do(reset_homework_status)
    schedule.every().day.at("20:00").do(check_homework_assigned)
    schedule.every().friday.at("14:00").do(send_homework_notification)
    schedule.every().monday.at("14:00").do(send_homework_notification)
    schedule.every().day.at("10:00").do(daily_check)

    # Установим время в амстердамском часовом поясе
    for job in schedule.jobs:
        job.at_time = amsterdam_tz.localize(datetime.strptime(job.at_time, "%H:%M").time())

    threading.Thread(target=run_schedule).start()

    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=1)
        except Exception as e:
            error_message = f"Ошибка: {type(e).__name__} - {str(e)}"
            print(error_message)
            send_error_log(error_message)
            time.sleep(10)
