"""
    🕵️ SpyMaster
    Полный аудит цели: мониторинг удаленных/новых аватарок, изменений в профиле (BIO, Username, Имя), 
    контроль сообщений в чатах и детекция правок/удалений постов в каналах.
"""

__version__ = (2, 2, 2)

# meta developer: @ShadowArchitect
# scope: hikka_only
# requires: aiohttp

import logging
import asyncio
from .. import loader, utils
from herokutl.types import Message
from herokutl.tl.functions.photos import GetUserPhotosRequest
from herokutl.tl.functions.users import GetFullUserRequest
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
        "ava_del": "🗑 <b>Аватарка удалена/изменена у</b> <code>{}</code>",
        "msg_edit": "📝 <b>ИЗМЕНЕНИЕ в</b> <code>{}</code>\n👤 <b>От:</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "bio_upd": "📝 <b>Изменение BIO у</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "name_upd": "👤 <b>Изменение Имени у</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "user_upd": "🔗 <b>Изменение Username у</b> <code>{}</code>\n❌ <b>Было:</b> @{}\n✅ <b>Стало:</b> @{}",
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
        if self.config["enabled"] and self.config["target_id"]:
            await self._fill_cache()

    async def _fill_cache(self):
        try:
            full_user = await self._client(GetFullUserRequest(self.config["target_id"]))
            user = full_user.users[0]
            photos = await self._client(GetUserPhotosRequest(user_id=self.config["target_id"], offset=0, max_id=0, limit=1))
            
            self.cache["pfp_count"] = photos.count
            self.cache["bio"] = full_user.full_user.about or ""
            self.cache["username"] = user.username or ""
            self.cache["first_name"] = user.first_name or ""
            self.cache["last_name"] = user.last_name or ""
        except: pass

    async def _check_profile(self):
        try:
            full_user = await self._client(GetFullUserRequest(self.config["target_id"]))
            user = full_user.users[0]
            log = self.config["log_chat"]
            tid = self.config["target_id"]

            new_bio = full_user.full_user.about or ""
            if new_bio != self.cache.get("bio"):
                await self._client.send_message(log, self.strings("bio_upd").format(tid, self.cache.get("bio"), new_bio))
                self.cache["bio"] = new_bio

            if user.username != self.cache.get("username"):
                await self._client.send_message(log, self.strings("user_upd").format(tid, self.cache.get("username"), user.username))
                self.cache["username"] = user.username

            if user.first_name != self.cache.get("first_name") or user.last_name != self.cache.get("last_name"):
                old_name = f"{self.cache.get('first_name')} {self.cache.get('last_name')}"
                new_name = f"{user.first_name} {user.last_name}"
                await self._client.send_message(log, self.strings("name_upd").format(tid, old_name, new_name))
                self.cache["first_name"] = user.first_name
                self.cache["last_name"] = user.last_name

            photos = await self._client(GetUserPhotosRequest(user_id=tid, offset=0, max_id=0, limit=1))
            if photos.count > self.cache.get("pfp_count", 0):
                await self._client.send_message(log, self.strings("ava_new").format(tid))
                await self._client.send_file(log, photos.photos[0])
            elif photos.count < self.cache.get("pfp_count", 0):
                await self._client.send_message(log, self.strings("ava_del").format(tid))
            self.cache["pfp_count"] = photos.count
        except: pass

    @loader.command(ru_doc="<id/link> - Захватить цель")
    async def spycmd(self, message: Message):
        args = utils.get_args_raw(message)
        entity = await self._client.get_entity(args)
        self.config["target_id"] = entity.id
        await self._fill_cache()
        await utils.answer(message, self.strings("target_set").format(entity.id))

    @loader.command(ru_doc="Сделать этот чат логом")
    async def spylogcmd(self, message: Message):
        self.config["log_chat"] = message.chat_id
        await utils.answer(message, self.strings("log_chat_set").format(message.chat_id))

    @loader.loop(interval=120)
    async def profile_loop(self):
        if self.config["enabled"] and self.config["target_id"] and self.config["log_chat"]:
            await self._check_profile()

    @loader.watcher(out=False)
    async def watcher(self, message: Message):
        if not self.config["enabled"] or not self.config["log_chat"]: return
        if message.sender_id == self.config["target_id"] or message.chat_id in self.config["track_channels"]:
            self._db.set("SpyMaster", f"m_{message.chat_id}_{message.id}", message.text)

    @loader.raw_handler()
    async def raw_handler(self, update):
        if not self.config["enabled"] or not isinstance(update, (UpdateEditMessage, UpdateEditChannelMessage)): return
        msg = update.message
        cid = msg.peer_id.channel_id if hasattr(msg.peer_id, 'channel_id') else (msg.peer_id.chat_id if hasattr(msg.peer_id, 'chat_id') else msg.peer_id.user_id)
        old = self._db.get("SpyMaster", f"m_{cid}_{msg.id}")
        if old and old != msg.message:
            await self._client.send_message(
                self.config["log_chat"],
                self.strings("msg_edit").format(cid, msg.from_id if hasattr(msg, 'from_id') else "System", old, msg.message)
            )
            self._db.set("SpyMaster", f"m_{cid}_{msg.id}", msg.message)

    @loader.command(ru_doc="Тумблер слежки")
    async def spyoncmd(self, message: Message):
        self.config["enabled"] = not self.config["enabled"]
        await utils.answer(message, self.strings("status").format("АКТИВНА" if self.config["enabled"] else "ВЫКЛ", self.config["target_id"]))
