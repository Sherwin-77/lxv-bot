from collections import OrderedDict
import logging
import discord
from dataclasses import dataclass

from typing import Any, Optional, Union

from .structure import Node

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
    def __init__(
        self, data: discord.Message, keyid: str, *, next_: Optional[Node] = None, prev: Optional[Node] = None
    ) -> None:
        super().__init__(data, next_=next_, prev=prev)
        self.keyid = keyid


class MessageCache:
    """
    Represent Cache of :class:`discord.Message` using LRU strategy
    """

    def __init__(self, maxlen=500) -> None:
        if maxlen < 1:
            raise ValueError("Max length must be 1 or greater")
        self.__cache = OrderedDict()
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

    def add_message(self, message: discord.Message, custom_key: Optional[str] = None) -> None:
        if custom_key is not None and custom_key.startswith("message-"):
            raise KeyError("'message-' prefix is not allowed as custom key")
        logger.debug("Add message key %s", custom_key or message.id)
        # Add to hashmap
        self.__cache[custom_key or f"message-{message.id}"] = message
        self.__cache.move_to_end(custom_key or f"message-{message.id}")

        while len(self.__cache) > self._maxlen:
            self.__cache.popitem(last=False)

    def remove_message(self, key: Union[str, int]) -> Optional[discord.Message]:
        if isinstance(key, int):
            if f"message-{key}" in self.__cache:
                logger.debug("Removed message key %s", key)
                return self.__cache.pop(f"message-{key}")

            key_del = None
            for name, message in self.__cache.items():
                if message.id == key:
                    key_del = name
                    break
            if key_del is not None:
                return self.__cache.pop(key_del)
        else:
            if key in self.__cache:
                logger.debug("Removed message key %s", key)
                return self.__cache.pop(key)

        return None

    def clear(self) -> None:
        self.__cache.clear()
        logger.debug("Cleared cache")


class LRUCache:
    """
    A generic Least Recently Used (LRU) cache implementation.
    When the cache reaches its capacity, the least recently used item is removed.
    """

    def __init__(self, maxlen=100) -> None:
        if maxlen < 1:
            raise ValueError("Max length must be 1 or greater")
        self.__cache = OrderedDict()
        self._maxlen = maxlen
        logger.debug("Created instance of LRUCache")

    @property
    def maxlen(self):
        return self._maxlen

    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache. Returns None if not found."""
        if key in self.__cache:
            # Move to end to mark as recently used
            self.__cache.move_to_end(key)
            return self.__cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        """Add an item to the cache or update if key exists."""
        if key in self.__cache:
            self.__cache.pop(key)
        self.__cache[key] = value
        self.__cache.move_to_end(key)

        # Remove oldest item if we're over capacity
        if len(self.__cache) > self._maxlen:
            self.__cache.popitem(last=False)

    def remove(self, key: str) -> Optional[Any]:
        """Remove an item from the cache and return it."""
        if key in self.__cache:
            logger.debug("Removed item with key %s", key)
            return self.__cache.pop(key)
        return None

    def clear(self) -> None:
        """Clear all items from the cache."""
        self.__cache.clear()
        logger.debug("Cleared cache")

    def __len__(self) -> int:
        """Return the current size of the cache."""
        return len(self.__cache)
