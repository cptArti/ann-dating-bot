import logging
from datetime import datetime, timedelta
import telebot
from telebot import types
import gspread
from threading import Thread
from flask import Flask

logging.basicConfig(level=logging.INFO)

# УБЕДИСЬ, ЧТО ТВОЙ ТОКЕН ТУТ НА МЕСТЕ!
BOT_TOKEN = '8064709996:AAHKdGrsZhhtxTYb5i0urtEwfYlrSYRMKgA'
bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}

# --- ОБМАНКА ДЛЯ СЕРВЕРА (ФЕЙКОВЫЙ ВЕБ-САЙТ) ---
app = Flask('')

@app.route('/')
def home():
    return "Бот работает стабильно!"

def run_flask():
    # Render передает порт динамически в переменные окружения, берем его или ставим 8080
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()


# --- ФУНКЦИЯ ЗАПИСИ В ГУГЛ-ТАБЛИЦУ ---
def append_to_sheet(username, date, meet_format):
    try:
        client = gspread.service_account(filename='credentials.json')
        sheet = client.open("Дневник Свиданий").sheet1
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        row = [current_time, username, date, meet_format]
        sheet.append_row(row)
        logging.info(f"Данные успешно записаны в таблицу для {username}")
    except Exception as e:
        logging.error(f"Ошибка при записи в Гугл-Таблицу: {e}")


# --- ГЕНЕРАЦИЯ КЛАВИАТУР ---

def get_keyboard_step_1():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="Да! ❤️", callback_data="yes"),
        types.InlineKeyboardButton(text="Нет 😢", callback_data="no_1")
    )
    return markup

def get_keyboard_step_2():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text="ДА! 🥰", callback_data="yes"),
        types.InlineKeyboardButton(text="Нет... 💔", callback_data="no_2")
    )
    return markup

def get_dates_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    today = datetime.now()
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i in range(7):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime(f"%d.%m ({days_of_week[current_date.weekday()]})")
        callback_data = current_date.strftime("date_%d.%m.%Y")
        markup.add(types.InlineKeyboardButton(text=date_str, callback_data=callback_data))
    return markup

def get_format_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(text="Уютный ресторан/кафе 🍽️", callback_data="format_restaurant"),
        types.InlineKeyboardButton(text="Поход в кино 🍿", callback_data="format_cinema"),
        types.InlineKeyboardButton(text="Приготовить ужин дома и посмотреть фильм 🏠", callback_data="format_home"),
        types.InlineKeyboardButton(text="Прогулка с кофе/парк ☕", callback_data="format_walk"),
        types.InlineKeyboardButton(text="Сделай для меня сюрприз! ✨", callback_data="format_surprise")
    )
    return markup


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПЕРЕХОДОВ ---

def go_to_date_selection(chat_id):
    user_data[chat_id]["status"] = "wait_date_select"
    bot.send_message(chat_id=chat_id, text="Ура! 🎉 Выбери удобную дату на ближайшей неделе (или напиши её текстом, например, 15.06):", reply_markup=get_dates_keyboard())

def go_to_format_selection(chat_id, selected_date):
    user_data[chat_id]["date"] = selected_date
    user_data[chat_id]["status"] = "wait_format_select"
    bot.send_message(chat_id=chat_id, text=f"Отлично, {selected_date} принято! 📅\n\nА теперь выбери формат свидания (кнопкой или текстом):", reply_markup=get_format_keyboard())

def finish_interview(chat_id, chosen_format, from_user):
    format_titles = {
        "restaurant": "Уютный ресторан/кафе 🍽️",
        "cinema": "Поход в кино 🍿",
        "home": "Ужин дома и фильм 🏠",
        "walk": "Прогулка с кофе/парк ☕",
        "surprise": "Сюрприз! ✨"
    }
    friendly_format = format_titles.get(chosen_format, chosen_format)
    date = user_data[chat_id].get("date", "Не выбрана")
    username = from_user.username or from_user.first_name
    user_data[chat_id]["status"] = "completed"
    
    bot.send_message(chat_id=chat_id, text=f"Превосходно! 🥰\n\n📌 **Итог нашей встречи:**\n📅 Дата: {date}\n🎭 Формат: {friendly_format}\n\nЯ уже готовлюсь и очень жду! 🍾✨\nЛюблю тебя!!", parse_mode="Markdown")
    append_to_sheet(username, date, friendly_format)


# --- ХЕНДЛЕРЫ ---

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_data[message.chat.id] = {"status": "wait_date_agree"}
    bot.send_message(chat_id=message.chat.id, text="Привет! У меня к тебе важный вопрос... ✨\n\nХочешь ли ты пойти со мной на свидание?", reply_markup=get_keyboard_step_1())

@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    text = message.text.lower().strip()
    if chat_id not in user_data or user_data[chat_id].get("status") == "completed":
        bot.send_message(chat_id, "Чтобы начать сначала, введи команду /start 🚀")
        return
    status = user_data[chat_id].get("status")

    if status == "wait_date_agree":
        if text in ["да", "да!", "хочу", "давай", "пошли", "yes", "ок", "хорошо"]:
            go_to_date_selection(chat_id)
            return
        elif text in ["нет", "не хочу", "не", "no", "неа"]:
            bot.send_message(chat_id, "Может, стоит подумать ещё раз? 😉", reply_markup=get_keyboard_step_2())
            return
        else:
            bot.send_message(chat_id, "Я пока не понял твой answer... Напиши 'Да' или 'Нет' 😊")
            return
    elif status == "wait_date_select":
        if len(text) >= 4 and ("." in text or "," in text):
            clean_date = text.replace(",", ".")
            go_to_format_selection(chat_id, clean_date)
            return
        else:
            bot.send_message(chat_id=chat_id, text="Пожалуйста, выбери одну из дат на кнопках выше 📅 или напиши её в формате ДД.ММ (например: 14.06):")
            return
    elif status == "wait_format_select":
        if "ресторан" in text or "кафе" in text or "поесть" in text or "🍽️" in text:
            finish_interview(chat_id, "restaurant", message.from_user)
            return
        elif "кино" in text or "фильм в кино" in text or "🍿" in text:
            finish_interview(chat_id, "cinema", message.from_user)
            return
        elif "дома" in text or "ужин" in text or "приготовить" in text or "🏠" in text:
            finish_interview(chat_id, "home", message.from_user)
            return
        elif "прогулка" in text or "парк" in text or "кофе" in text or "☕" in text:
            finish_interview(chat_id, "walk", message.from_user)
            return
        elif "сюрприз" in text or "секрет" in text or "✨" in text:
            finish_interview(chat_id, "surprise", message.from_user)
            return
        else:
            bot.send_message(chat_id=chat_id, text="Интересный вариант! Но выбери, пожалуйста, что-то из этого:\n1. Ресторан 🍽️\n2. Поход в кино 🍿\n3. Ужин дома и фильм 🏠\n4. Прогулка ☕\n5. Сюрприз ✨\n(Можно текстом или кнопкой!)")
            return

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"status": "wait_date_agree"}

    if call.data == "no_1":
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Может, стоит подумать ещё раз? 😉", reply_markup=get_keyboard_step_2())
        bot.answer_callback_query(call.id)
    elif call.data == "no_2":
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Хм, кажется, кнопка 'Нет' сломалась... 🔧\nДавай попробуем еще раз! Выбора особо нет :)", reply_markup=get_keyboard_step_2())
        bot.answer_callback_query(call.id)
    elif call.data == "yes":
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
        go_to_date_selection(chat_id)
        bot.answer_callback_query(call.id)
    elif call.data.startswith("date_"):
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
        selected_date = call.data.split("_")[1]
        go_to_format_selection(chat_id, selected_date)
        bot.answer_callback_query(call.id)
    elif call.data.startswith("format_"):
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
        chosen_format = call.data.split("_")[1]
        finish_interview(chat_id, chosen_format, call.from_user)
        bot.answer_callback_query(call.id)


if __name__ == "__main__":
    bot.remove_webhook()
    
    # СНАЧАЛА ЗАПУСКАЕМ ВЕБ-СЕРВЕР ДЛЯ ОБМАНА ОБЛАКА
    keep_alive()
    print("Фейковый сайт запущен для Render...")
    
    # ТЕПЕРЬ ЗАПУСКАЕМ БОТА В ОБЫЧНОМ РЕЖИМЕ
    print("Бот успешно запущен и обновлен новыми форматами...")
    bot.infinity_polling()