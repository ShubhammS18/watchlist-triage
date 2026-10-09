"""SHA-256 counter stream. Block n of stream NAME is sha256("<seed>|<NAME>|<n>").

Each block gives four 64-bit integers. Integers only: no random module, no floats,
no clock. The same seed and stream name always give the same numbers on any platform.
"""
import hashlib

_TWO_64 = 1 << 64


class Stream:
    def __init__(self, seed, name):
        self._prefix = f"{seed}|{name}|".encode("utf-8")
        self._block = 0
        self._words = ()
        self._next = 4  # forces the first block to be hashed on first use

    def next_u64(self):
        if self._next == 4:
            digest = hashlib.sha256(self._prefix + str(self._block).encode("ascii")).digest()
            self._words = tuple(int.from_bytes(digest[k:k + 8], "big") for k in (0, 8, 16, 24))
            self._block += 1
            self._next = 0
        word = self._words[self._next]
        self._next += 1
        return word

    def below(self, n):
        """Uniform integer in [0, n). Rejection sampling removes modulo bias."""
        if n <= 0:
            raise ValueError("n must be positive")
        limit = _TWO_64 - (_TWO_64 % n)
        while True:
            word = self.next_u64()
            if word < limit:
                return word % n

    def randint(self, low, high):
        """Uniform integer in [low, high], both ends included."""
        if high < low:
            raise ValueError("high must not be below low")
        return low + self.below(high - low + 1)

    def choice(self, items):
        if not items:
            raise ValueError("cannot choose from an empty sequence")
        return items[self.below(len(items))]

    def shuffle(self, items):
        """Fisher-Yates, in place. Returns the same list for convenience."""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items
