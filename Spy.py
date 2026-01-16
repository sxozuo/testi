"""
    🕵️ SpyMaster
    Система слежки с автоматическим сохранением всех данных и аватарок в Избранное.
    Оптимизировано для мгновенного детекта изменений BIO и Username.
"""

__version__ = (2.5.0)

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
    """Absolute Surveillance System (Aggressive Edition)"""
    
    strings = {
        "name": "SpyMaster",
        "target_set": "🎯 <b>Цель установлена:</b> <code>{}</code>",
        "status": "🕵️ <b>Слежка:</b> {}\n🎯 <b>Цель:</b> <code>{}</code>",
        "ava_new": "📸 <b>Архивация новой аватарки цели</b> <code>{}</code>",
        "ava_del": "🗑 <b>Цель</b> <code>{}</code> <b>удалила аватарку.</b>",
        "msg_edit": "📝 <b>ИЗМЕНЕНИЕ в</b> <code>{}</code>\n👤 <b>От:</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "bio_upd": "📝 <b>Изменение BIO у</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "name_upd": "👤 <b>Изменение Имени у</b> <code>{}</code>\n❌ <b>Было:</b> {}\n✅ <b>Стало:</b> {}",
        "user_upd": "🔗 <b>Изменение Username у</b> <code>{}</code>\n❌ <b>Было:</b> @{}\n✅ <b>Стало:</b> @{}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("target_id", 0, "ID цели", validator=loader.validators.TelegramID()),
            loader.ConfigValue("enabled", False, "Статус", validator=loader.validators.Boolean()),
            loader.ConfigValue("track_channels", [], "ID каналов", validator=loader.validators.Series(loader.validators.TelegramID()))
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
            self.cache["last_pfp_id"] = photos.photos[0].id if photos.photos else 0
            self.cache["bio"] = full_user.full_user.about or ""
            self.cache["username"] = user.username or ""
            self.cache["first_name"] = user.first_name or ""
            self.cache["last_name"] = user.last_name or ""
        except Exception as e:
            logger.error(f"Cache fill error: {e}")

    async def _check_profile(self):
        try:
            full_user = await self._client(GetFullUserRequest(self.config["target_id"]))
            user = full_user.users[0]
            tid = self.config["target_id"]

            new_bio = full_user.full_user.about or ""
            if new_bio != self.cache.get("bio"):
                await self._client.send_message("me", self.strings("bio_upd").format(tid, self.cache.get("bio") or "Пусто", new_bio or "Пусто"))
                self.cache["bio"] = new_bio

            if user.username != self.cache.get("username"):
                await self._client.send_message("me", self.strings("user_upd").format(tid, self.cache.get("username") or "None", user.username or "None"))
                self.cache["username"] = user.username

            if user.first_name != self.cache.get("first_name") or user.last_name != self.cache.get("last_name"):
                old_name = f"{self.cache.get('first_name', '')} {self.cache.get('last_name', '')}".strip()
                new_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                await self._client.send_message("me", self.strings("name_upd").format(tid, old_name, new_name))
                self.cache["first_name"] = user.first_name
                self.cache["last_name"] = user.last_name

            photos = await self._client(GetUserPhotosRequest(user_id=tid, offset=0, max_id=0, limit=1))
            current_pfp_id = photos.photos[0].id if photos.photos else 0
            if current_pfp_id != self.cache.get("last_pfp_id"):
                if current_pfp_id != 0:
                    await self._client.send_message("me", self.strings("ava_new").format(tid))
                    await self._client.send_file("me", photos.photos[0])
                else:
                    await self._client.send_message("me", self.strings("ava_del").format(tid))
                self.cache["last_pfp_id"] = current_pfp_id
        except Exception as e:
            logger.error(f"Profile check error: {e}")

    @loader.command(ru_doc="Захват цели")
    async def spycmd(self, message: Message):
        args = utils.get_args_raw(message)
        if not args: return await utils.answer(message, "❌ Укажи цель")
        entity = await self._client.get_entity(args)
        self.config["target_id"] = entity.id
        await self._fill_cache()
        await utils.answer(message, self.strings("target_set").format(entity.id))

    @loader.loop(interval=30)
    async def profile_loop(self):
        if self.config["enabled"] and self.config["target_id"]:
            await self._check_profile()

    @loader.watcher(out=False)
    async def watcher(self, message: Message):
        if not self.config["enabled"]: return
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
                "me",
                self.strings("msg_edit").format(cid, msg.from_id if hasattr(msg, 'from_id') else "System", old, msg.message)
            )
            self._db.set("SpyMaster", f"m_{cid}_{msg.id}", msg.message)

    @loader.command(ru_doc="Вкл/Выкл")
    async def spyoncmd(self, message: Message):
        self.config["enabled"] = not self.config["enabled"]
        if self.config["enabled"]: await self._fill_cache()
        await utils.answer(message, self.strings("status").format("АКТИВНА" if self.config["enabled"] else "ВЫКЛ", self.config["target_id"]))
