# import numpy as np

# class BoundingBoxesQueue:
#     def __init__(self, max_size):
#         self._queue = []
#         self.size = 0
#         self.max_size = 10

#     def enqueue(self, item):
#         self._queue.append(item)
#         if self.size < self.max_size:
#             self.size += 1
#         else:
#             del self._queue[0]
#             self.size -= 1
    
#     def concatenate(self):
#         return np.concatenate(self._queue,axis=0)
