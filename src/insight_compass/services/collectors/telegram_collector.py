# --- START OF FILE src/insight_compass/services/collectors/telegram_collector.py ---

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Dict, Optional, AsyncIterator

import telethon
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import ChannelPrivateError
from telethon.tl.types import (Message, MessageMediaDocument,
                               MessageMediaPhoto, MessageReactions)
from pydantic import ValidationError

# ИСПРАВЛЕНИЕ: Используем абсолютный импорт от корня проекта 'insight_compass'.
# Это стандартный и самый надежный способ импорта в Python-проектах.
from insight_compass.core.config import settings
from insight_compass.services.collectors.base import BaseDataCollector
from insight_compass.schemas.telegram_raw import (
    RawPostModel, RawCommentModel, MediaModel, ForwardInfoModel
)

logger = logging.getLogger(__name__)

class TelegramCollector(BaseDataCollector):
    """
    Реализация BaseDataCollector для сбора данных из Telegram-каналов.
    Использует библиотеку Telethon и Pydantic для валидации данных.
    """
    def __init__(self, session_string: str):
        super().__init__()
        self.session_string = session_string
        self.client: Optional[TelegramClient] = None

    async def initialize(self) -> None:
        """
        Инициализирует и подключает Telethon клиент.
        """
        if self.session_string:
            logger.info("Initializing Telegram client with session string.")
            self.client = TelegramClient(
                StringSession(self.session_string),
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH
            )
        else:
            logger.warning("Session string not provided. Telethon client might not work as expected without it.")
            self.client = TelegramClient(
                'anon_session',
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH
            )
        
        await self.client.connect()
        if not await self.client.is_user_authorized():
            logger.error("Telethon client is not authorized. Session string might be invalid or expired.")
            raise ConnectionError("Telethon client not authorized.")


    async def get_channel_info(self, channel_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о Telegram-канале по username или ID.
        """
        if not self.client:
            raise RuntimeError("Telegram client not initialized.")
        try:
            entity = await self.client.get_entity(channel_identifier)
            if entity:
                channel_id_str = str(entity.id)
                if channel_id_str.startswith('-100'):
                    db_id = int(channel_id_str[4:])
                else:
                    db_id = entity.id

                return {
                    'telegram_id': db_id,
                    'username': getattr(entity, 'username', None),
                    'title': getattr(entity, 'title', getattr(entity, 'username', f"Channel_{db_id}")),
                }
            return None
        except ValueError:
            logger.error(f"Cannot find any entity corresponding to '{channel_identifier}'")
            return None
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_identifier}: {e}")
            return None

    async def iter_posts(
        self,
        channel_telegram_id: int,
        limit: Optional[int] = settings.POST_FETCH_LIMIT,
        offset_date: Optional[date] = None,
        min_id: Optional[int] = None
    ) -> AsyncIterator[RawPostModel]:
        """
        Асинхронно итерируется по постам канала с гибкими параметрами.
        """
        if not self.client:
            raise RuntimeError("Telegram client not initialized.")
        
        try:
            full_channel_id = int(f"-100{channel_telegram_id}")
            entity = await self.client.get_entity(full_channel_id)
        except (ValueError, TypeError, ChannelPrivateError) as e:
            logger.error(f"Cannot access channel with ID {channel_telegram_id}. It may be private or invalid. Error: {e}")
            return

        kwargs = {'limit': limit}
        if offset_date:
            kwargs['offset_date'] = offset_date
            logger.info(f"Исторический сбор для канала {channel_telegram_id}: посты с {offset_date}, лимит {limit}.")
        elif min_id:
            kwargs['min_id'] = min_id
            kwargs['reverse'] = True 
            logger.info(f"Сбор новых постов для канала {channel_telegram_id}: посты новее ID {min_id}.")
        else:
             logger.info(f"Сбор последних {limit} постов для канала {channel_telegram_id} (первоначальный).")

        try:
            async for message in self.client.iter_messages(entity, **kwargs):
                if message and message.id and isinstance(message, Message):
                    raw_post = self._extract_raw_post_data(message)
                    if raw_post:
                        yield raw_post
        except Exception as e:
            logger.error(f"Error fetching posts for channel {channel_telegram_id}: {e}", exc_info=True)

    async def get_comments_for_post(self, post_telegram_id: int, channel_telegram_id: int, last_known_comment_id: Optional[int] = None) -> AsyncIterator[RawCommentModel]:
        """
        Собирает комментарии для поста, валидирует их и возвращает в виде Pydantic-моделей.
        """
        if not self.client:
            raise RuntimeError("Telegram client not initialized.")

        try:
            full_channel_id = int(f"-100{channel_telegram_id}")
            
            kwargs = {
                'reply_to': post_telegram_id,
                'limit': settings.COMMENT_FETCH_LIMIT
            }
            if last_known_comment_id:
                kwargs['min_id'] = last_known_comment_id

            async for comment in self.client.iter_messages(full_channel_id, **kwargs):
                if comment and comment.id and isinstance(comment, Message):
                    raw_comment = self._extract_raw_comment_data(comment)
                    if raw_comment:
                        yield raw_comment
        
        except telethon.errors.rpcerrorlist.MsgIdInvalidError as e:
            logger.debug(f"Could not fetch comments for post {post_telegram_id} (likely no comment section or deleted): {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching comments for post {post_telegram_id}: {e}", exc_info=True)
            raise

    async def get_single_post_by_id(self, channel_telegram_id: int, post_telegram_id: int) -> Optional[RawPostModel]:
        """
        Запрашивает информацию об ОДНОМ конкретном посте по его ID.
        """
        if not self.client:
            raise RuntimeError("Telegram client not initialized.")
        
        try:
            full_channel_id = int(f"-100{channel_telegram_id}")
            messages = await self.client.get_messages(full_channel_id, ids=[post_telegram_id])
            
            if messages and isinstance(messages[0], Message):
                return self._extract_raw_post_data(messages[0])

        except Exception as e:
            logger.error(f"Error fetching single post {post_telegram_id} from channel {channel_telegram_id}: {e}", exc_info=True)
        
        return None

    def _extract_raw_post_data(self, message: Message) -> Optional[RawPostModel]:
        """
        Извлекает данные из объекта Message и валидирует их.
        """
        try:
            reactions_data = None
            if message.reactions and isinstance(message.reactions, MessageReactions) and message.reactions.results:
                reactions_data = {
                    reaction.emoticon: reaction_count.count
                    for reaction_count in message.reactions.results
                    if hasattr(reaction_count, 'reaction') and hasattr(reaction_count.reaction, 'emoticon')
                    for reaction in [reaction_count.reaction] 
                }

            media_data = None
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    media_data = MediaModel(type='photo')
                elif isinstance(message.media, MessageMediaDocument):
                    media_data = MediaModel(type='document')
                else:
                    media_data = MediaModel(type='unknown')
            
            forward_info_data = None
            if message.fwd_from:
                fwd = message.fwd_from
                from_id = getattr(fwd, 'from_id', None)
                from_channel_id = None
                if from_id and hasattr(from_id, 'channel_id'):
                    from_channel_id = int(str(getattr(from_id, 'channel_id', '0')))

                forward_info_data = ForwardInfoModel(
                    from_channel_id=from_channel_id,
                    from_message_id=getattr(fwd, 'channel_post', None),
                    sender_name=getattr(fwd, 'from_name', None),
                    date=getattr(fwd, 'date', None)
                )

            raw_post = RawPostModel(
                telegram_id=message.id,
                text=message.text,
                created_at=message.date,
                views_count=message.views or 0,
                forwards_count=message.forwards or 0,
                reactions=reactions_data,
                media=media_data,
                forward_info=forward_info_data,
            )
            return raw_post
        except ValidationError as e:
            logger.error(f"Pydantic validation failed for post TG_ID={message.id}. Data will be skipped. Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during post extraction TG_ID={message.id}. Data will be skipped. Error: {e}", exc_info=True)
            return None

    def _extract_raw_comment_data(self, message: Message) -> Optional[RawCommentModel]:
        """
        Извлекает данные из комментария и валидирует их.
        """
        try:
            reactions_data = None
            if message.reactions and isinstance(message.reactions, MessageReactions) and message.reactions.results:
                reactions_data = {
                    reaction.emoticon: reaction_count.count
                    for reaction_count in message.reactions.results
                    if hasattr(reaction_count, 'reaction') and hasattr(reaction_count.reaction, 'emoticon')
                    for reaction in [reaction_count.reaction]
                }
            
            author_id = getattr(message, 'sender_id', None)

            raw_comment = RawCommentModel(
                telegram_id=message.id,
                text=message.text,
                created_at=message.date,
                author_id=author_id,
                reactions=reactions_data,
            )
            return raw_comment
        except ValidationError as e:
            logger.error(f"Pydantic validation failed for comment TG_ID={message.id}. Data will be skipped. Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during comment extraction TG_ID={message.id}. Data will be skipped. Error: {e}", exc_info=True)
            return None

    def normalize_post_data(self, raw_post: RawPostModel) -> dict:
        """
        Преобразует Pydantic-модель в словарь для записи в БД.
        """
        return raw_post.model_dump(exclude_unset=True)

    def normalize_comment_data(self, raw_comment: RawCommentModel) -> dict:
        """
        Преобразует Pydantic-модель в словарь для записи в БД.
        """
        return raw_comment.model_dump(exclude_unset=True)

    async def disconnect(self) -> None:
        """Отключает Telethon клиент."""
        if self.client and self.client.is_connected():
            logger.info("Disconnecting Telegram client.")
            await self.client.disconnect()

# --- END OF FILE src/insight_compass/services/collectors/telegram_collector.py ---