from collections import deque
from contextlib import contextmanager
import random
from threading import Lock
from time import time


class DowntimePronePool(object):
    """
    A thread-safe bucket of servers (or other things) that may have downtime.

    Tries to return a "live" server from the bucket on request, retiring "dead"
    servers for a time to give them a chance to recover before offering them
    again.

    Actually testing whether an server is dead is expressly outside the scope
    of this class (for decoupling) and outside the period of its lock (since it
    could take a long time). Thus, we explicitly embrace the race condition
    where 2 threads are testing a server simultaneously, get different
    results, and call ``mark_dead`` and then ``mark_live`` fairly close
    together. It's not at all clear which is the correct state in that case, so
    we just let the winner win. If flapping is a common case, we could add flap
    detection later and class flappers as failures, immune to ``mark_live``.
    """
    def __init__(self, servers, revival_delay):
        """
        :arg servers: A list of servers (or whatever things you like)
        :arg revival_delay: The number of seconds to wait before reviving a
            dead server
        """
        self.live = servers
        self.dead = deque()  # [(time to reinstate, url), ...], oldest first
        self.revival_delay = revival_delay
        self.lock = Lock()  # a lock around live and dead

    def get(self):
        """
        Return a random server and a bool indicating whether it was from the
        dead list.

        We prefer to return live servers. However, if all servers are marked
        dead, return one of those in case it's come back to life earlier than
        expected. This fallback is O(n) rather than O(1), but it's all dwarfed
        by IO anyway.
        """
        with self._locking():
            # Revive any servers whose times have come:
            now = time()
            while self.dead and now >= self.dead[0][0]:
                self.live.append(self.dead.popleft()[1])

            try:
                return random.choice(self.live), False
            except IndexError:  # live is empty.
                return random.choice(self.dead)[1], True  # O(n) but rare

    def mark_dead(self, server):
        """
        Guarantee that this server won't be returned again until a period of
        time has passed, unless all servers are dead.

        If the given server is already on the dead list, do nothing. We
        wouldn't want to push its revival time farther away.
        """
        with self._locking():
            try:
                self.live.remove(server)
            except ValueError:
                # Another thread has marked this server dead since this one
                # got ahold of it, or we handed them a dead server to begin
                # with.
                pass
            else:
                self.dead.append((time() + self.revival_delay, server))

    def mark_live(self, server):
        """
        Move a server from the dead list to the live one.

        If the server wasn't dead, do nothing.

        This is intended to be used only in the case where ``get()`` falls back
        to returning a dead server and we find out it isn't acting dead after
        all.
        """
        with self._locking():
            for i, (revival_time, cur_server) in enumerate(self.dead):
                if cur_server == server:
                    self.live.append(server)
                    del self.dead[i]
                    break
            # If it isn't found, it's already been revived, and that's okay.

    @contextmanager
    def _locking(self):
        self.lock.acquire()
        yield
        self.lock.release()
