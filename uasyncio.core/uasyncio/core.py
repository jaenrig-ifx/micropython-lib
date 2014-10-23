import time
import uheapq as heapq
import logging


log = logging.getLogger("asyncio")

type_gen = type((lambda: (yield))())

class EventLoop:

    def __init__(self):
        self.q = []
        self.cnt = 0

    def time(self):
        return time.time()

    def call_soon(self, callback, *args):
        self.call_at(0, callback, *args)

    def call_later(self, delay, callback, *args):
        self.call_at(self.time() + delay, callback, *args)

    def call_at(self, time, callback, *args):
        # Including self.cnt is a workaround per heapq docs
        log.debug("Scheduling %s", (time, self.cnt, callback, args))
        heapq.heappush(self.q, (time, self.cnt, callback, args))
#        print(self.q)
        self.cnt += 1

    def wait(self, delay):
        # Default wait implementation, to be overriden in subclasses
        # with IO scheduling
        log.debug("Sleeping for: %s", delay)
        time.sleep(delay)

    def run_forever(self):
        while True:
            if self.q:
                t, cnt, cb, args = heapq.heappop(self.q)
                log.debug("Next coroutine to run: %s", (t, cnt, cb, args))
#                __main__.mem_info()
                tnow = self.time()
                delay = t - tnow
                if delay > 0:
                    self.wait(delay)
            else:
                self.wait(-1)
                # Assuming IO completion scheduled some tasks
                continue
            if callable(cb):
                cb(*args)
            else:
                delay = 0
                try:
                    if args == ():
                        args = (None,)
                    log.debug("Coroutine %s send args: %s", cb, args)
                    ret = cb.send(*args)
                    log.debug("Coroutine %s yield result: %s", cb, ret)
                    if isinstance(ret, SysCall):
                        arg = ret.args[0]
                        if isinstance(ret, Sleep):
                            delay = arg
                        elif isinstance(ret, IORead):
#                            self.add_reader(ret.obj.fileno(), lambda self, c, f: self.call_soon(c, f), self, cb, ret.obj)
#                            self.add_reader(ret.obj.fileno(), lambda c, f: self.call_soon(c, f), cb, ret.obj)
                            self.add_reader(arg.fileno(), lambda cb, f: self.call_soon(cb, f), cb, arg)
                            continue
                        elif isinstance(ret, IOWrite):
                            self.add_writer(arg.fileno(), lambda cb, f: self.call_soon(cb, f), cb, arg)
                            continue
                        elif isinstance(ret, IOReadDone):
                            self.remove_reader(arg.fileno())
                        elif isinstance(ret, IOWriteDone):
                            self.remove_writer(arg.fileno())
                        elif isinstance(ret, StopLoop):
                            return arg
                    elif isinstance(ret, type_gen):
                        self.call_soon(ret)
                    elif ret is None:
                        # Just reschedule
                        pass
                    else:
                        assert False, "Unsupported coroutine yield value: %r (of type %r)" % (ret, type(ret))
                except StopIteration as e:
                    log.debug("Coroutine finished: %s", cb)
                    continue
                self.call_later(delay, cb, *args)

    def run_until_complete(self, coro):
        def _run_and_stop():
            yield from coro
            yield StopLoop(0)
        self.call_soon(_run_and_stop())
        self.run_forever()

    def close(self):
        pass


class SysCall:

    def __init__(self, *args):
        self.args = args

    def handle(self):
        raise NotImplementedError

class Sleep(SysCall):
    pass

class StopLoop(SysCall):
    pass

class IORead(SysCall):
    pass

class IOWrite(SysCall):
    pass

class IOReadDone(SysCall):
    pass

class IOWriteDone(SysCall):
    pass


def get_event_loop():
    return EventLoop()

def coroutine(f):
    return f

def async(coro):
    # We don't have Task bloat, so op is null
    return coro

def sleep(secs):
    yield Sleep(secs)