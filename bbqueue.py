import numpy as np

class BoundingBoxesQueue:
    def __init__(self, max_size):
        self._queue = []
        self.max_size = max_size

    @property
    def size(self):
        return len(self._queue)

    def enqueue(self, item):
        self._queue.append(item)
        if self.size > self.max_size:
            del self._queue[0]

    def concatenate(self):
        return np.concatenate(self._queue, axis=0)
