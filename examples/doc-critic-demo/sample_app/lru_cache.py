"""A small least-recently-used (LRU) cache for the doc-critic worked example.

Kept deliberately tiny so the learning-track documents can be checked against real,
runnable code. This is the source of truth the code-grounded review axis reads.
"""
from collections import OrderedDict


class LRUCache:
    """A least-recently-used cache with a fixed capacity."""

    def __init__(self, capacity: int = 100):
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._store: "OrderedDict[str, object]" = OrderedDict()

    def get(self, key):
        """Return the value stored under key, marking it most recently used.

        A miss raises KeyError — it does not return None. Callers handle the miss.
        """
        value = self._store[key]            # raises KeyError when key is absent
        self._store.move_to_end(key)        # mark as most recently used
        return value

    def set(self, key, value):
        """Store value under key; evict the least-recently-used item if over capacity."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)  # drop the least recently used item


if __name__ == "__main__":
    cache = LRUCache(capacity=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")                 # touch "a": now "b" is the least recently used
    cache.set("c", 3)              # full -> evict "b"
    print("a" in cache._store, "b" in cache._store, "c" in cache._store)
    try:
        cache.get("b")
    except KeyError:
        print("get('b') raised KeyError (a miss is not None)")
    print("default capacity is", LRUCache().capacity)
