import logging
import discord
from dataclasses import dataclass

from typing import Dict, Optional, Union

from .structure import AsyncLinkedList, Node

logger = logging.getLogger(__name__)

# Uncomment below for debug purpose
formatter = logging.Formatter("[{asctime}] [{levelname:^7}] {name}: {message}", style='{')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)

@dataclass
class CacheData(Node):
    def __init__(self, data: discord.Message, keyid: str, *, next_: Optional[Node] = None, prev: Optional[Node] = None) -> None:
        super().__init__(data, next_=next_, prev=prev)
        self.keyid = keyid

class MessageCache:
    """
    Represent Cache of :class:`discord.Message` using LRU strategy
    """
    def __init__(self, maxlen=500) -> None:
        if maxlen < 1:
            raise ValueError("Max length must be 1 or greater")
        self.__cache: Dict[str, discord.Message] = {}
        self.__record: Dict[str, CacheData] = {}
        self.__q = AsyncLinkedList()
        self._maxlen = maxlen
        logger.debug("Created instance of MessageCache")

    @property
    def maxlen(self):
        return self._maxlen

    def get_message(self, key: str) -> Optional[discord.Message]:
        return self.__cache.get(key)

    def query_message_id(self, message_id: int) -> Optional[discord.Message]:
        # First lookup
        logger.debug("Query message: %s", message_id)
        if f"message-{message_id}" in self.__cache:
            return self.__cache[f"message-{message_id}"]

        for message in self.__cache.values():
            if message.id == message_id:
                return message
        return None

    async def add_message(self, message: discord.Message, custom_key: Optional[str] = None) -> None:
        if custom_key is not None and custom_key.startswith("message-"):
            raise KeyError("'message-' prefix is not allowed as custom key")
        logger.debug("Add message key %s", custom_key or message.id)
        # Add to hashmap
        self.__cache[custom_key or f"message-{message.id}"] = message
        # Add to list (For LRU Cache deleting)
        n = CacheData(message, custom_key or f"message-{message.id}")
        self.__record[custom_key or f"message-{message.id}"] = n
        await self.__q.add_node(n)
        while len(self.__cache) > self.maxlen and self.__q.head is not None:
            n: CacheData
            n = self.__q.head  # type: ignore
            self.__record.pop(n.keyid)
            self.__cache.pop(n.keyid)
            await self.__q.remove_node(n)
            logger.debug("Performing auto delete message key %s", n.keyid)


    async def remove_message(self, key: Union[str, int]) -> Optional[discord.Message]:
        if isinstance(key, int):
            if f"message-{key}" in self.__cache:
                if f"message-{key}" in self.__record:
                    n = self.__record.pop(f"message-{key}")
                    await self.__q.remove_node(n)
                logger.debug("Removed message key %s", key)
                return self.__cache.pop(f"message-{key}")

            key_del = None
            for name, message in self.__cache.items():
                if message.id == key:
                    key_del = name
                    break
            if key_del is not None:
                if f"message-{key_del}" in self.__record:
                    n = self.__record.pop(f"message-{key_del}")
                    await self.__q.remove_node(n)
                logger.debug("Removed message custom key %s", key_del)
                return self.__cache.pop(key_del)
        else:
            if key in self.__cache:
                if key in self.__record:
                    n = self.__record.pop(key)
                    await self.__q.remove_node(n)
                logger.debug("Removed message key %s", key)
                return self.__cache.pop(key)
        
        return None
    

    def clear(self) -> None:
        self.__cache.clear()
        self.__record.clear()
        self.__q.clear()