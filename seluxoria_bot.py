import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ChatPermissions
from aiogram.utils import executor
from google.cloud import vision

TOKEN = "7743549770:AAEetsOTSrVEPHnp1sNMp5K6LND4V7jtrzM"
LOG_CHAT_ID = "4755542987"
WEATHER_API_KEY = "b19646131ca413e97c6f718fa036291c"
GOOGLE_APPLICATION_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Подключение к БД для хранения предупреждений и рангов
conn = sqlite3.connect("moderation.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    warnings INTEGER DEFAULT 0,
    role TEXT DEFAULT 'user'
)
""")
conn.commit()

# Роли пользователей
ROLES = {"owner": 3, "admin": 2, "moderator": 1, "user": 0}
MOD_ACTIONS = {"mute", "warn"}
ADMIN_ACTIONS = MOD_ACTIONS | {"ban", "unban", "kick"}
OWNER_ACTIONS = ADMIN_ACTIONS | {"setrole"}

# Фильтрация контента через Google Vision API
vision_client = vision.ImageAnnotatorClient()
async def is_inappropriate_image(file_path):
    with open(file_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = vision_client.safe_search_detection(image=image)
    safe_search = response.safe_search_annotation
    if safe_search.adult >= 3 or safe_search.violence >= 3:
        return True
    return False

# Проверка роли
def get_user_role(user_id):
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else "user"

def has_permission(user_id, action):
    role = get_user_role(user_id)
    if action in OWNER_ACTIONS and role == "owner":
        return True
    if action in ADMIN_ACTIONS and role in {"admin", "owner"}:
        return True
    if action in MOD_ACTIONS and role in {"moderator", "admin", "owner"}:
        return True
    return False

# /help команда
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    help_text = """
    🤖 *Функции бота:*
    🔹 `/mute @user time` – Замутить участника
    🔹 `/warn @user` – Выдать предупреждение (3 предупреждения = мут)
    🔹 `/ban @user` – Забанить участника
    🔹 `/unban @user` – Разбанить участника
    🔹 `/kick @user` – Исключить из чата
    🔹 `/weather город` – Узнать погоду
    🔹 `/time город` – Узнать время
    🔹 `/setrole @user роль` – Назначить роль (только владелец)
    🔹 Бот фильтрует NSFW/жестокий контент 🔞
    """
    await message.reply(help_text, parse_mode="Markdown")

# Назначение ролей
@dp.message_handler(commands=['setrole'])
async def set_role(message: types.Message):
    if not has_permission(message.from_user.id, "setrole"):
        return await message.reply("❌ У вас нет прав на изменение ролей!")
    try:
        target_user = message.reply_to_message.from_user.id
        role = message.text.split()[1]
        if role not in ROLES:
            return await message.reply("❌ Некорректная роль! (user, moderator, admin, owner)")
        cursor.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)", (target_user, role))
        conn.commit()
        await message.reply(f"✅ Роль пользователя обновлена до {role}!")
    except:
        await message.reply("❌ Используйте: `/setrole @user роль`")

# Авто-сообщения для предотвращения спящего режима
async def keep_alive():
    while True:
        await bot.send_message(LOG_CHAT_ID, "лунный кролек всегда к вашим услугам")
        await asyncio.sleep(600)

# Основной запуск бота
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(keep_alive())
    executor.start_polling(dp, skip_updates=True)
