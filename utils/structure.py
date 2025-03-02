from __future__ import annotations


import asyncio
from typing import Optional, Type


class Node:
    def __init__(self, data=None, *, next_: Optional[Node] = None, prev: Optional[Node] = None) -> None:
        self.next_ = next_
        self.prev = prev
        self.data = data

class LinkedList:
    def __init__(self) -> None:
        self.head = None
        self.tail = None

    def remove_node(self, node: Node):
        n = node.next_
        p = node.prev
        if n:
            n.prev = p
        if p:
            p.next_ = n
        if node is self.tail:
            self.tail = p
        if node is self.head:
            self.head = n

    def add_node(self, node: Node):
        node.prev = self.tail
        if self.head is None:
            self.head = node
        if self.tail:
            self.tail.next_ = node
        self.tail = node

    def clear(self):
        # Abusing garbage collector
        self.head = self.tail = None

class AsyncLinkedList(LinkedList):
    def __init__(self) -> None:
        super().__init__()
        self.lock = asyncio.Lock()

    async def remove_node(self, node: Node):
        async with self.lock:
            super().remove_node(node)

    async def add_node(self, node: Node):
        async with self.lock:
            super().add_node(node)

