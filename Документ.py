"""
    🕵️ SpyMaster Ultimate
    Полный аудит цели: мониторинг удаленных/новых аватарок, изменений в профиле, 
    контроль сообщений в чатах и детекция правок/удалений постов в каналах.
"""

__version__ = (2, 1, 0)

# meta developer: @ShadowArchitect
# scope: hikka_only
# requires: aiohttp

import logging
import asyncio
import io
from .. import loader, utils
from herokutl.types import Message
from herokutl.tl.functions.photos import GetUserPhotosRequest
from herokutl.tl.types import UpdateEditMessage, UpdateEditChannelMessage

logger = logging.getLogger(__name__)

@loader.tds
class SpyMasterMod(loader.Module):
    """Absolute Surveillance System"""
    
    strings = {
        "name": "SpyMaster",
        "target_set": "🎯 <b>Цель установлена:</b> <code>{}</code>",
        "log_chat_set": "📂 <b>Чат логов:</b> <code>{}</code>",
        "status": "🕵️ <b>Слежка:</b> {}\n🎯 <b>Цель:</b> <code>{}</code>",
        "ava_new": "📸 <b>Новая аватарка у</b> <code>{}</code>",
        "ava_del": "🗑 <b>Аватарка удалена/изменена у</b> <code>{}</code>. Последняя сохранена ниже.",
        "msg_edit": "📝 <b>ИЗМЕНЕНИЕ в</b> <code>{}</code>\n👤 <b>От:</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "post_upd": "📢 <b>Действие в канале</b> <code>{}</code>\n📝 <b>Текст:</b> {}"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("target_id", 0, "ID цели", validator=loader.validators.TelegramID()),
            loader.ConfigValue("log_chat", 0, "ID чата для отчетов", validator=loader.validators.TelegramID()),
            loader.ConfigValue("enabled", False, "Статус работы", validator=loader.validators.Boolean()),
            loader.ConfigValue("track_channels", [], "Список ID каналов", validator=loader.validators.Series(loader.validators.TelegramID()))
        )
        self.cache = {}

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self.cache["pfp_count"] = 0
        if self.config["enabled"] and self.config["target_id"]:
            await self._check_pfp(initial=True)

    async def _check_pfp(self, initial=False):
        try:
            photos = await self._client(GetUserPhotosRequest(user_id=self.config["target_id"], offset=0, max_id=0, limit=1))
            if initial:
                self.cache["pfp_count"] = photos.count
                return
            
            if photos.count > self.cache["pfp_count"]:
                await self._client.send_message(self.config["log_chat"], self.strings("ava_new").format(self.config["target_id"]))
                await self._client.send_file(self.config["log_chat"], photos.photos[0])
            elif photos.count < self.cache["pfp_count"]:
                await self._client.send_message(self.config["log_chat"], self.strings("ava_del").format(self.config["target_id"]))
            
            self.cache["pfp_count"] = photos.count
        except: pass

    @loader.command(ru_doc="<id/link> - Захватить цель")
    async def spycmd(self, message: Message):
        args = utils.get_args_raw(message)
        entity = await self._client.get_entity(args)
        self.config["target_id"] = entity.id
        await self._check_pfp(initial=True)
        await utils.answer(message, self.strings("target_set").format(entity.id))

    @loader.command(ru_doc="Сделать этот чат логом")
    async def spylogcmd(self, message: Message):
        self.config["log_chat"] = message.chat_id
        await utils.answer(message, self.strings("log_chat_set").format(message.chat_id))

    @loader.loop(interval=120)
    async def pfp_loop(self):
        if self.config["enabled"] and self.config["target_id"] and self.config["log_chat"]:
            await self._check_pfp()

    @loader.watcher(out=False)
    async def watcher(self, message: Message):
        if not self.config["enabled"] or not self.config["log_chat"]: return
        if message.sender_id == self.config["target_id"] or message.chat_id in self.config["track_channels"]:
            self._db.set("SpyMaster", f"m_{message.chat_id}_{message.id}", message.text)

    @loader.raw_watcher()
    async def edit_handler(self, update):
        if not self.config["enabled"] or not isinstance(update, (UpdateEditMessage, UpdateEditChannelMessage)): return
        msg = update.message
        chat_id = msg.peer_id.channel_id if hasattr(msg.peer_id, 'channel_id') else (msg.peer_id.chat_id if hasattr(msg.peer_id, 'chat_id') else msg.peer_id.user_id)
        
        old = self._db.get("SpyMaster", f"m_{chat_id}_{msg.id}")
        if old and old != msg.message:
            await self._client.send_message(
                self.config["log_chat"],
                self.strings("msg_edit").format(chat_id, msg.from_id if hasattr(msg, 'from_id') else "System", old, msg.message)
            )
            self._db.set("SpyMaster", f"m_{chat_id}_{msg.id}", msg.message)

    @loader.command(ru_doc="Тумблер слежки")
    async def spyoncmd(self, message: Message):
        self.config["enabled"] = not self.config["enabled"]
        await utils.answer(message, self.strings("status").format("АКТИВНА" if self.config["enabled"] else "ВЫКЛ", self.config["target_id"]))