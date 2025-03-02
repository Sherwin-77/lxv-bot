import unittest
from structure import AsyncLinkedList, Node


class Test(unittest.IsolatedAsyncioTestCase):
    async def test_add_one_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        await ll.add_node(a)
        self.assertEqual(ll.head, a)
        self.assertEqual(ll.tail, a)

    async def test_add_two_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        await ll.add_node(a)
        await ll.add_node(b)
        self.assertEqual(ll.head, a)
        self.assertEqual(ll.tail, b)
        self.assertEqual(a.next_, b)
        self.assertEqual(b.next_, None)
        self.assertEqual(a.prev, None)
        self.assertEqual(b.prev, a)

    async def test_add_nodes(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)

        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        self.assertEqual(ll.head, a)
        self.assertEqual(ll.tail, d)

    async def test_remove_one_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)
        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        await ll.remove_node(b)
        self.assertEqual(a.next_, c)
        self.assertEqual(c.prev, a)

    async def test_remove_head_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)
        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        await ll.remove_node(a)
        self.assertEqual(ll.head, b)
        self.assertEqual(b.prev, None)

    async def test_remove_tail_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)
        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        await ll.remove_node(d)
        self.assertEqual(ll.tail, c)
        self.assertEqual(c.next_, None)

    async def test_remove_one_two_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)
        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        await ll.remove_node(a)
        await ll.remove_node(b)
        await ll.remove_node(c)
        self.assertEquals(ll.head, ll.tail, d)
        self.assertEquals(d.prev, d.next_, None)

    async def test_remove_last_node(self):
        ll = AsyncLinkedList()
        a = Node(1)
        b = Node(2)
        c = Node(3)
        d = Node(4)
        await ll.add_node(a)
        await ll.add_node(b)
        await ll.add_node(c)
        await ll.add_node(d)
        await ll.remove_node(a)
        await ll.remove_node(b)
        await ll.remove_node(c)
        await ll.remove_node(d)
        self.assertEquals(ll.head, ll.tail, None)


if __name__ == "__main__":
    unittest.main()