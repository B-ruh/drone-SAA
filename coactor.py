# actor type that uses coroutines

from thespian.actors import *
import traceback
from datetime import timedelta
import inspect

class CoActor(Actor):
    # class that yields message information when awaited
    class MessageWaiter:
        def __init__(self, mtype):
            self.mtype = mtype
        def __await__(self):
            return (yield self)

    # dummy message for call_soon
    class CallSoon:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initialize our own state
        self._callbacks = []
        self._pending_coros = {}
        self._call_soon = []
        self._call_soon_sent = False

    def receiveMessage(self, msg, sender):
        # we've got a message

        was_handled = False

        # keep list of coros made from this message so they don't see
        # the message twice
        new_coros = []

        def send_coro(coro, obj):
            try:
                wobj = coro.send(obj)
            except StopIteration:
                wobj = None
            except:
                # oh heck
                traceback.print_exc()
                return
            if wobj is not None:
                new_coros.append((wobj, coro))

        # 0th step: execute the call soon callbacks
        if isinstance(msg, CoActor.CallSoon):
            self._call_soon_sent = False
            was_handled = True

        if len(self._call_soon) > 0:
            cs = self._call_soon
            self._call_soon = []
            for coro in cs:
                if hasattr(coro, 'send'):
                    send_coro(coro, None)
                elif not inspect.iscoroutinefunction(coro):
                    #print("called it!")
                    coro()
                else:
                    send_coro(coro(), None)

        # first step: see if any callbacks need to be processed
        for mtype, cb in self._callbacks:
            if isinstance(msg, mtype):
                was_handled = True
                # call the callback and get a coroutine
                coro = cb(msg, sender)
                # now send it to get it running
                send_coro(coro, None)

        # second step: see if any coros were waiting on that message
        if type(msg) in self._pending_coros:
            coros = self._pending_coros[type(msg)]
            del self._pending_coros[type(msg)]
            for coro in coros:
                was_handled = True
                # send the new message into the coroutine
                send_coro(coro, (msg, sender))
        
        # third step: prepare the coros for next message
        for wobj, coro in new_coros:
            if isinstance(wobj, CoActor.MessageWaiter):
                mtype = wobj.mtype
                if mtype not in self._pending_coros:
                    self._pending_coros[mtype] = []
                self._pending_coros[mtype].append(coro)
            elif isinstance(wobj, Future):
                wobj._waiters.append(coro)
            else:
                raise Exception("weird coro: {}".format(coro))

        if not was_handled:
            print("{} didn't handle: {}, {}".format(self.myAddress, msg, sender))

    def register_cb(self, mtype, cb):
        self._callbacks.append((mtype, cb))

    def unregister_cb(self, mtype, cb):
        self._callbacks.remove((mtype, cb))

    # sleep for a specified number of seconds asynchronously
    async def sleep(self, seconds):
        # instantiate new message waiter
        w = CoActor.MessageWaiter(WakeupMessage)
        # schedule a wakeup to be sent in the specified seconds
        self.wakeupAfter(timedelta(seconds=seconds), payload=w)
        while True:
            # wait for a new wakeupmessage
            msg, sender = await w
            # make sure it's for this wakeup
            if msg.payload == w: break

    # wait for a specific message type asynchronously
    # optionally pass a validator function that takes the
    # message and sender and returns True if it is indeed the message
    # that is being waited for
    async def wait_msg(self, mtype, validator=None):
        # wait for the message type
        w = CoActor.MessageWaiter(mtype)
        while True:
            # wait for a new message of that type
            msg, sender = await w
            # make sure it's one we want
            if validator is None or validator(msg, sender):
                return msg, sender

    # schedule a coroutine to be called
    def call_soon(self, coro):
        # append it to call soon list
        self._call_soon.append(coro)
        # and send a call soon message to trig ger the call
        # (assuming we haven't sent one since the last time)
        if not self._call_soon_sent:
            self._call_soon_sent = True
            self.send(self.myAddress, CoActor.CallSoon())

# basic implementation of futures for CoActors
# set its result to alert all waiters
# await it to get its result
class Future:
    def __init__(self, actor):
        self.actor = actor
        self._waiters = []

        self.has_result = False
        self.result = None

    # tell the future the result
    def set_result(self, result):
        self.result = result
        self.has_result = True
        # unwait everybody who was waiting on us
        for waiter in self._waiters:
            self.actor.call_soon(waiter)
        self._waiters = []

    def __await__(self):
        yield self
        return self.result
