# queue_manager.py
from collections import deque

class QueueManager:
    def __init__(self):
        self.queue = deque()

    def add_user(self, nickname):
        """Adds a user to the queue if they are not already in it."""
        if nickname not in self.queue:
            self.queue.append(nickname)
            return True
        return False

    def pop_users(self, count=1):
        """Pops a specified number of users from the front of the queue."""
        if not self.queue:
            return []

        popped_users = []
        for _ in range(count):
            if self.queue:
                popped_users.append(self.queue.popleft())
            else:
                break
        return popped_users

    def get_queue(self):
        """Returns the current queue as a list."""
        return list(self.queue)

    def is_empty(self):
        """Checks if the queue is empty."""
        return not self.queue
