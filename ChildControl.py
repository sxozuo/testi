import asyncio
import re
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8241945653:AAFwDmguMaKys7vXAR4l7YNZ6Fwk5JeKnXg"
ADMIN_IDS = [103303270, 218946128]

FORBIDDEN_STUFF = r"(?i)(порно|porn|цп|cp|детское\s+видео|sell\s+stars|аккаунты\s+вк|tg\s+stars)"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect("fheta_base.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                warns INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        """)
        await db.commit()

async def get_main_chat():
    async with aiosqlite.connect("fheta_base.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'main_chat_id'") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

@dp.message(Command("start"), F.chat.type == "private")
async def fheta_start(message: types.Message):
    start_text = (
        f"<tg-emoji emoji_id='5431343743113471043'>🛡</tg-emoji> <b>Fheta Manager</b>\n"
        f"—————————————————\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Бот закреплен за чатом и работает в режиме мониторинга.\n\n"
        f"<tg-emoji emoji_id='5431505330369571011'>⚙️</tg-emoji> <b>Статус:</b> Активен\n"
        f"<tg-emoji emoji_id='5431523326265715104'>🔒</tg-emoji> <b>Доступ:</b> Приватный\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="💎 Профиль", callback_data="my_profile"),
        types.InlineKeyboardButton(text="🆘 Помощь", callback_data="help_info")
    )
    
    if message.from_user.id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="🔧 Перепривязать чат", callback_data="rebind_chat"))

    await message.answer(start_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "rebind_chat")
async def rebind_info(callback: types.CallbackQuery):
    await callback.message.answer("Введите <code>!привязать</code> в нужной группе.")
    await callback.answer()

@dp.callback_query(F.data == "my_profile")
async def show_profile_callback(callback: types.CallbackQuery):
    async with aiosqlite.connect("fheta_base.db") as db:
        async with db.execute("SELECT warns FROM users WHERE user_id = ?", (callback.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            warns = row[0] if row else 0
    await callback.message.answer(f"👤 <b>Профиль:</b> {callback.from_user.first_name}\n⚠️ Варны: {warns}/3")
    await callback.answer()

@dp.message(F.text == "!привязать", F.chat.type.in_({"group", "supergroup"}))
async def bind_chat_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with aiosqlite.connect("fheta_base.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('main_chat_id', ?)", (message.chat.id,))
        await db.commit()
    await message.answer(f"✅ Чат привязан!\nID: <code>{message.chat.id}</code>")

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def main_handler(message: types.Message):
    main_chat_id = await get_main_chat()
    if message.chat.id != main_chat_id:
        return

    if message.text and re.search(FORBIDDEN_STUFF, message.text):
        try:
            await message.delete()
            async with aiosqlite.connect("fheta_base.db") as db:
                await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username))
                await db.execute("UPDATE users SET warns = warns + 1 WHERE user_id = ?", (message.from_user.id,))
                await db.commit()
                cur = await db.execute("SELECT warns FROM users WHERE user_id = ?", (message.from_user.id,))
                warns = (await cur.fetchone())[0]

            if warns >= 3:
                await bot.ban_chat_member(message.chat.id, message.from_user.id)
                await message.answer(f"🚫 {message.from_user.first_name} забанен за нарушения.")
            else:
                await message.answer(f"⚠️ {message.from_user.first_name}, запрещенка удалена. Варны: {warns}/3")
            return
        except: pass

    if not message.text: return
    cmd = message.text.lower()
    user_id = message.from_user.id

    if user_id in ADMIN_IDS and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if cmd.startswith("!бан"):
            await bot.ban_chat_member(message.chat.id, target_id)
            await message.answer("✅ Забанен.")
        elif cmd.startswith("!варн"):
            async with aiosqlite.connect("fheta_base.db") as db:
                await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (target_id,))
                await db.execute("UPDATE users SET warns = warns + 1 WHERE user_id = ?", (target_id,))
                await db.commit()
            await message.answer("⚠️ Варн выдан.")
        elif cmd.startswith("!разварн"):
            async with aiosqlite.connect("fheta_base.db") as db:
                await db.execute("UPDATE users SET warns = 0 WHERE user_id = ?", (target_id,))
                await db.commit()
            await message.answer("✅ Варны сняты.")

    if message.reply_to_message:
        target = message.reply_to_message.from_user.first_name
        if cmd.startswith("кусь"):
            await message.answer(f"🦷 {message.from_user.first_name} куснул {target}")
        elif cmd.startswith("обнять"):
            await message.answer(f"🫂 {message.from_user.first_name} обнял {target}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛡 <b>ModBot запущен!</b>\n\n"
        "Команды:\n"
        "/trigger слово — добавить триггер\n"
        "/deltrigger слово — удалить триггер\n"
        "/listtriggers — список триггеров\n"
        "/cleartriggers — очистить все триггеры",
        parse_mode="HTML"
    )

@dp.message(Command("trigger"))
async def cmd_trigger(message: Message):
    if not is_admin(message.from_user.id):
        await message.delete()
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи слово: /trigger слово")
        return

    word = args[1].strip().strip('"\'').lower()
    TRIGGER_WORDS.add(word)
    await message.answer(f"✅ Триггер добавлен: <code>{word}</code>", parse_mode="HTML")

@dp.message(Command("deltrigger"))
async def cmd_deltrigger(message: Message):
    if not is_admin(message.from_user.id):
        await message.delete()
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи слово: /deltrigger слово")
        return

    word = args[1].strip().strip('"\'').lower()
    TRIGGER_WORDS.discard(word)
    await message.answer(f"🗑 Триггер удалён: <code>{word}</code>", parse_mode="HTML")

@dp.message(Command("listtriggers"))
async def cmd_listtriggers(message: Message):
    if not is_admin(message.from_user.id):
        return

    if not TRIGGER_WORDS:
        await message.answer("📭 Список триггеров пуст.")
        return

    words = "\n".join([f"• <code>{w}</code>" for w in sorted(TRIGGER_WORDS)])
    await message.answer(f"📋 <b>Триггер слова:</b>\n{words}", parse_mode="HTML")

@dp.message(Command("cleartriggers"))
async def cmd_cleartriggers(message: Message):
    if not is_admin(message.from_user.id):
        await message.delete()
        return

    TRIGGER_WORDS.clear()
    await message.answer("🗑 Все триггеры удалены.")

@dp.message()
async def check_message(message: Message):
    # Пропускаем сообщения от админов
    if is_admin(message.from_user.id):
        return

    should_delete = False

    # Проверяем текст
    if message.text and check_triggers(message.text):
        should_delete = True

    # Проверяем подпись к медиа
    if message.caption and check_triggers(message.caption):
        should_delete = True

    # Проверяем фото/медиа без текста — удаляем если предыдущее сообщение содержало триггер
    # Также удаляем медиа если оно пришло с триггер словом в подписи
    if message.photo or message.video or message.document or message.animation:
        if message.caption and check_triggers(message.caption):
            should_delete = True

    if should_delete:
        try:
            await message.delete()
            logger.info(f"Удалено сообщение от {message.from_user.id} в чате {message.chat.id}")
        except Exception as e:
            logger.error(f"Не удалось удалить: {e}")


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return

    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS пуст! Никто не сможет управлять ботом.")

    logger.info("ModBot запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
