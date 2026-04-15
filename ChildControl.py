import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage


BOT_TOKEN = "8241945653:AAFwDmguMaKys7vXAR4l7YNZ6Fwk5JeKnXg"
ADMIN_IDS = [103303270, 218946128]


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Стартовые триггер слова
TRIGGER_WORDS = set([
    "детей", "дети", "ребёнок", "ребенок",
    "порно", "секс", "nude", "naked",
    "cp", "csam", "pedo",
])

def check_triggers(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for word in TRIGGER_WORDS:
        if word.lower() in text_lower:
            return True
    return False

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