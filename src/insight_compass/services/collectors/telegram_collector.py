# src/insight_compass/services/collectors/telegram_collector.py

# ==============================================================================
# "СЕРДЦЕ" СБОРА ДАННЫХ - TELEGRAM COLLECTOR (Версия 4.0 - Финальная)
# ==============================================================================
# Этот класс инкапсулирует ВСЮ логику взаимодействия с внешним API Telegram.
#
# ИЗМЕНЕНИЯ В ЭТОЙ ВЕРСИИ:
# 1. ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Исправлена фатальная ошибка `ModuleNotFoundError`.
#    Опечатка в пути импорта (`from ..schemas...`) заменена на корректный
#    абсолютный импорт (`from insight_compass.schemas...`).
#    Эта ошибка приводила к падению как API-сервера, так и Celery-воркера
#    в момент запуска.
# 2. Сохранены все предыдущие исправления по отказоустойчивости и корректной
#    работе с Telethon API.
# ==============================================================================

import asyncio
import logging
from datetime import date
from typing import Optional, AsyncIterator
from contextlib import asynccontextmanager

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    Message, User, Channel as TelethonChannel,
    MessageMediaPhoto, MessageMediaDocument, MessageMediaPoll,
    MessageReactions, DocumentAttributeFilename, DocumentAttributeVideo
)
from telethon.tl.functions.channels import GetFullChannelRequest

from telethon.errors import (
    ChannelPrivateError, FloodWaitError, UserDeactivatedBanError,
    MsgIdInvalidError, RPCError
)
from pydantic import ValidationError

# КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Заменяем некорректный относительный импорт на
# правильный абсолютный импорт от корня проекта 'insight_compass'.
# Это стандартная и самая надежная практика в Python.
from insight_compass.schemas.telegram_raw import (
    RawChannelModel, RawPostModel, RawCommentModel, MediaModel, ForwardInfoModel,
    PollModel, PollAnswerModel, AuthorDetailsModel
)
from insight_compass.core.config import settings
from insight_compass.services.collectors.base import BaseDataCollector
from insight_compass.db.session import sessionmanager
from insight_compass.db.repositories.telegram_account_repository import TelegramAccountRepository

logger = logging.getLogger(__name__)


class TelegramCollector(BaseDataCollector):
    """
    Реализация BaseDataCollector для сбора данных из Telegram-каналов.
    Инкапсулирует всю логику, связанную с Telethon.
    """
    def __init__(self, session_string: str, account_db_id: int):
        super().__init__()
        self.client: Optional[TelegramClient] = None
        if not session_string:
            raise ValueError("Строка сессии Telegram не может быть пустой.")
        if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
            raise ValueError("TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены в настройках.")
        self.session_string = session_string
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        self.account_db_id = account_db_id
        self._is_banned_in_session = False

    async def initialize(self) -> None:
        """Инициализирует и подключает Telegram клиент."""
        if self.client and self.client.is_connected():
            logger.debug("Клиент Telegram уже инициализирован и подключен.")
            return
        logger.info(f"Инициализация Telegram клиента для аккаунта ID={self.account_db_id}...")
        self.client = TelegramClient(
            StringSession(self.session_string), self.api_id, self.api_hash,
            connection_retries=5, retry_delay=5
        )
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                error_msg = f"Клиент Telethon для аккаунта ID={self.account_db_id} не авторизован."
                logger.error(error_msg)
                await self._mark_self_as_banned()
                raise ConnectionError(error_msg)
            logger.info(f"Клиент Telegram для аккаунта ID={self.account_db_id} успешно авторизован.")
        except UserDeactivatedBanError:
            await self._mark_self_as_banned()
            raise

    async def get_channel_info(self, channel_identifier: str) -> Optional[RawChannelModel]:
        """Получает полную информацию о канале, используя современный и надежный метод."""
        async with self._banned_account_handler():
            if not self.client: raise RuntimeError("Клиент Telegram не инициализирован.")
            
            try:
                entity = await self.client.get_entity(channel_identifier)
                full_channel_info = await self.client(GetFullChannelRequest(channel=entity))
                full_channel = full_channel_info.full_chat
                channel_entity = full_channel_info.chats[0]

                channel_id = channel_entity.id

                return RawChannelModel(
                    telegram_id=channel_id,
                    name=getattr(channel_entity, 'username', None),
                    title=getattr(channel_entity, 'title', 'Unknown Title'),
                    about=getattr(full_channel, 'about', None),
                    participants_count=getattr(full_channel, 'participants_count', None),
                    is_verified=getattr(channel_entity, 'verified', False),
                    is_scam=getattr(channel_entity, 'scam', False),
                )
            except (ValueError, TypeError, ChannelPrivateError) as e:
                logger.error(f"Не удалось найти или распознать сущность для '{channel_identifier}'. Ошибка: {e}")
                return None
            except RPCError as e:
                logger.error(f"Ошибка RPC при получении информации о канале {channel_identifier}: {e}", exc_info=True)
                return None

    async def iter_posts(self, channel_telegram_id: int, limit: Optional[int], offset_date: Optional[date], min_id: Optional[int]) -> AsyncIterator[RawPostModel]:
        """
        Асинхронный генератор для итерации по постам канала. Сделан отказоустойчивым.
        """
        async with self._banned_account_handler():
            if not self.client: raise RuntimeError("Клиент Telegram не инициализирован.")
            
            try:
                entity = await self.client.get_entity(channel_telegram_id)
            
            except (ValueError, TypeError, ChannelPrivateError) as e:
                logger.error(
                    f"Не удается получить доступ к каналу {channel_telegram_id}. "
                    f"Причины: неверный ID, это не канал, канал приватный/удален, нет доступа. "
                    f"Ошибка Telethon: {e}"
                )
                return

            kwargs = {'limit': limit}
            if offset_date: kwargs['offset_date'] = offset_date
            if min_id: 
                kwargs['min_id'] = min_id
                kwargs['reverse'] = True

            try:
                async for message in self.client.iter_messages(entity, **kwargs):
                    if not (message and isinstance(message, Message)): continue
                    channel_username = getattr(entity, 'username', None)
                    raw_post = await self._extract_raw_post_data(message, channel_username)
                    if raw_post:
                        yield raw_post
            except RPCError as e:
                logger.error(f"RPC ошибка при загрузке постов для канала {channel_telegram_id}: {e}", exc_info=True)

    async def get_comments_for_post(self, post_telegram_id: int, channel_telegram_id: int, last_known_comment_id: Optional[int]) -> AsyncIterator[RawCommentModel]:
        """Асинхронный генератор для сбора комментариев к посту."""
        async with self._banned_account_handler():
            if not self.client: raise RuntimeError("Клиент Telegram не инициализирован.")
            try:
                entity = await self.client.get_entity(channel_telegram_id)
                kwargs = {'reply_to': post_telegram_id, 'limit': settings.COMMENT_FETCH_LIMIT}
                if last_known_comment_id:
                    kwargs['min_id'] = last_known_comment_id
                
                async for comment in self.client.iter_messages(entity, **kwargs):
                    if not (comment and isinstance(comment, Message)): continue
                    raw_comment = await self._extract_raw_comment_data(comment)
                    if raw_comment:
                        yield raw_comment
            except (ValueError, TypeError, ChannelPrivateError):
                logger.warning(f"Не удалось получить доступ к каналу {channel_telegram_id} для сбора комментариев к посту {post_telegram_id}.")
                return
            except MsgIdInvalidError:
                logger.debug(f"Не удалось получить комментарии для поста {post_telegram_id} в канале {channel_telegram_id} (возможно, комментарии отключены или пост удален).")
            except RPCError as e:
                logger.error(f"RPC ошибка при получении комментариев для поста {post_telegram_id}: {e}", exc_info=True)

    async def get_single_post_by_id(self, channel_telegram_id: int, post_telegram_id: int) -> Optional[RawPostModel]:
        """Получает один конкретный пост по ID."""
        async with self._banned_account_handler():
            if not self.client: raise RuntimeError("Клиент Telegram не инициализирован.")
            try:
                entity = await self.client.get_entity(channel_telegram_id)
                messages = await self.client.get_messages(entity, ids=[post_telegram_id])
                if messages and isinstance(messages[0], Message):
                    channel_username = getattr(entity, 'username', None)
                    return await self._extract_raw_post_data(messages[0], channel_username)
            except (ValueError, TypeError, ChannelPrivateError):
                 logger.warning(f"Не удалось найти пост {post_telegram_id} в канале {channel_telegram_id} или получить к нему доступ.")
            except RPCError as e:
                logger.error(f"Ошибка RPC при получении поста {post_telegram_id} из канала {channel_telegram_id}: {e}", exc_info=True)
            return None

    # --- Вспомогательные методы-парсеры (без изменений) ---

    async def _extract_raw_post_data(self, message: Message, channel_username: Optional[str]) -> Optional[RawPostModel]:
        try:
            reply_to_id = message.reply_to.reply_to_msg_id if message.reply_to else None
            return RawPostModel(
                telegram_id=message.id, url=f"https://t.me/{channel_username}/{message.id}" if channel_username else None,
                text=message.text, created_at=message.date, views_count=message.views or 0,
                forwards_count=message.forwards or 0, reactions=self._extract_reactions_data(message),
                media=self._extract_media_data(message), forward_info=self._extract_forward_info(message),
                poll=self._extract_poll_data(message), reply_to_message_id=reply_to_id,
                grouped_id=message.grouped_id
            )
        except (ValidationError, Exception) as e:
            logger.error(f"Ошибка при извлечении данных поста TG_ID={message.id}: {e}", exc_info=True)
            return None

    async def _extract_raw_comment_data(self, message: Message) -> Optional[RawCommentModel]:
        try:
            sender = await message.get_sender()
            author_details_data = None
            if isinstance(sender, User):
                author_details_data = AuthorDetailsModel(telegram_id=sender.id, first_name=sender.first_name, last_name=sender.last_name, username=sender.username, is_bot=sender.bot or False)
            elif isinstance(sender, TelethonChannel):
                 author_details_data = AuthorDetailsModel(telegram_id=sender.id, first_name=sender.title)
            reply_to_id = message.reply_to.reply_to_msg_id if message.reply_to else None
            return RawCommentModel(
                telegram_id=message.id, text=message.text, created_at=message.date,
                reactions=self._extract_reactions_data(message), author_details=author_details_data,
                reply_to_comment_id=reply_to_id
            )
        except (ValidationError, Exception) as e:
            logger.error(f"Ошибка при извлечении данных комментария TG_ID={message.id}: {e}", exc_info=True)
            return None

    def _extract_reactions_data(self, message: Message) -> Optional[dict]:
        if not (message.reactions and isinstance(message.reactions, MessageReactions) and message.reactions.results): return None
        return {res.reaction.emoticon: res.count for res in message.reactions.results if hasattr(res, 'reaction') and hasattr(res.reaction, 'emoticon')}

    def _extract_media_data(self, message: Message) -> Optional[MediaModel]:
        if not message.media: return None
        media_type, doc_attrs = "unknown", {}
        if isinstance(message.media, MessageMediaPhoto): media_type = "photo"
        elif isinstance(message.media, MessageMediaDocument):
            is_video = False
            if message.document and message.document.attributes:
                for attr in message.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename): doc_attrs['file_name'] = attr.file_name
                    elif isinstance(attr, DocumentAttributeVideo): is_video=True; doc_attrs.update({'duration_seconds': attr.duration, 'width': attr.w, 'height': attr.h})
            media_type = "video" if is_video else "document"
            if message.document: doc_attrs.update({'mime_type': message.document.mime_type, 'size_bytes': message.document.size})
        return MediaModel(type=media_type, has_spoiler=getattr(message.media, 'spoiler', False), **doc_attrs)

    def _extract_poll_data(self, message: Message) -> Optional[PollModel]:
        if not (message.poll and isinstance(message.media, MessageMediaPoll)): return None
        poll, results, answers = message.media.poll, message.media.results, []
        if results and results.results:
            for answer, vote in zip(poll.answers, results.results): answers.append(PollAnswerModel(text=answer.text, voters=vote.voters))
        else: answers = [PollAnswerModel(text=ans.text, voters=0) for ans in poll.answers]
        return PollModel(question=poll.question, total_voters=results.total_voters if results and results.total_voters else 0, answers=answers)

    def _extract_forward_info(self, message: Message) -> Optional[ForwardInfoModel]:
        if not message.fwd_from: return None
        fwd, from_peer = message.fwd_from, getattr(fwd, 'from_id', None)
        from_channel_id = from_peer.id if isinstance(from_peer, TelethonChannel) else None
        return ForwardInfoModel(
            from_channel_id=from_channel_id, from_message_id=getattr(fwd, 'channel_post', None),
            sender_name=getattr(fwd, 'from_name', None), date=getattr(fwd, 'date', None)
        )

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected():
            logger.info(f"Отключение Telegram клиента для аккаунта ID={self.account_db_id}")
            await self.client.disconnect()
            self.client = None

    @asynccontextmanager
    async def _banned_account_handler(self):
        try:
            yield
        except UserDeactivatedBanError:
            await self._mark_self_as_banned()
            raise

    async def _mark_self_as_banned(self):
        if self._is_banned_in_session: return
        logger.critical(f"АККАУНТ ID={self.account_db_id} ЗАБАНЕН! Помечаем в БД...")
        async with sessionmanager.session() as db:
            repo = TelegramAccountRepository(db)
            await repo.mark_as_banned(self.account_db_id)
            await db.commit()
        self._is_banned_in_session = True