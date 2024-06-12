import telebot
import psycopg2
from telebot import types
from config import API_TOKEN, DATABASE_URL

# Инициализация бота с токеном из config.py
bot = telebot.TeleBot(API_TOKEN)

# Функция для подключения к базе данных
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Подключение к базе данных и создание таблиц, если они не существуют
conn = get_db_connection()
conn.autocommit = True
cursor = conn.cursor()

def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES students(id),
            subject VARCHAR(50) NOT NULL,
            score INTEGER NOT NULL CHECK (score <= 100)
        )
    """)

create_tables()
conn.close()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Добро пожаловать! Введите /register для регистрации, /enter_scores для ввода баллов ЕГЭ, /view_scores для просмотра баллов или /delete_scores для удаления баллов.")

# Обработчик /register
@bot.message_handler(commands=['register'])
def register_student(message):
    msg = bot.reply_to(message, "Введите ваше имя:")
    bot.register_next_step_handler(msg, process_first_name_step, message.from_user.id)

def process_first_name_step(message, user_id):
    try:
        first_name = message.text
        msg = bot.reply_to(message, "Введите вашу фамилию:")
        bot.register_next_step_handler(msg, process_last_name_step, user_id, first_name)
    except Exception as e:
        bot.reply_to(message, 'Ошибка')

def process_last_name_step(message, user_id, first_name):
    try:
        last_name = message.text
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO students (user_id, first_name, last_name) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING RETURNING id", (user_id, first_name, last_name))
        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(message, f"Регистрация успешна, {first_name} {last_name}! Введите свои баллы /enter_scores")
    except Exception as e:
        bot.reply_to(message, 'Ошибка при регистрации')
        conn.rollback()

# Обработчик /enter_scores
@bot.message_handler(commands=['enter_scores'])
def enter_scores(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
    student = cursor.fetchone()
    cursor.close()
    conn.close()

    if student:
        msg = bot.reply_to(message, "Введите предмет:")
        bot.register_next_step_handler(msg, process_subject_step, student[0])
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Введите /register для регистрации.")

def process_subject_step(message, student_id):
    try:
        subject = message.text
        msg = bot.reply_to(message, "Введите балл (от 0 до 100):")
        bot.register_next_step_handler(msg, process_score_step, student_id, subject)
    except Exception as e:
        bot.reply_to(message, 'Ошибка')

def process_score_step(message, student_id, subject):
    try:
        score = int(message.text)
        if score < 0 or score > 100:
            bot.reply_to(message, "Балл должен быть в диапазоне от 0 до 100. Попробуйте снова.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scores (student_id, subject, score) VALUES (%s, %s, %s)", (student_id, subject, score))
        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(message, "Балл успешно сохранен!")
    except ValueError:
        bot.reply_to(message, "Введите корректное число.")
    except Exception as e:
        bot.reply_to(message, 'Ошибка при сохранении баллов')
        conn.rollback()

# Обработчик /view_scores
@bot.message_handler(commands=['view_scores'])
def view_scores(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
    student = cursor.fetchone()

    if student:
        cursor.execute("SELECT subject, score FROM scores WHERE student_id = %s", (student[0],))
        scores = cursor.fetchall()

        if scores:
            response = "Ваши баллы ЕГЭ:\n"
            for score in scores:
                response += f"{score[0]}: {score[1]}\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "У вас пока нет сохраненных баллов ЕГЭ.")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Введите /register для регистрации.")

    cursor.close()
    conn.close()

# Обработчик /delete_scores
@bot.message_handler(commands=['delete_scores'])
def delete_scores(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = %s", (user_id,))
    student = cursor.fetchone()

    if student:
        cursor.execute("DELETE FROM scores WHERE student_id = %s", (student[0],))
        conn.commit()
        bot.reply_to(message, "Все ваши баллы ЕГЭ были удалены.")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Введите /register для регистрации.")

    cursor.close()
    conn.close()

# Запуск бота
bot.polling()
