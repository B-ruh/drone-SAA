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

        # did something handle it?
        was_handled = False

        # keep list of coros made from this message so they don't see
        # the message twice
        new_coros = []

        # helper function to send a new value into a coroutine
        # then deal with the thing it wants to await on
        def send_coro(coro, obj):
            try:
                wobj = coro.send(obj)
            except StopIteration:
                # coro is completely finished
                return
            except:
                # oh heck
                traceback.print_exc()
                return

            if isinstance(wobj, Future):
                # it wants to wait on a future
                # add it to the future's waiters
                wobj._waiters.append(coro)
            else:
                # something else, handle that once all coros
                # are processed
                new_coros.append((wobj, coro))

        if isinstance(msg, CoActor.CallSoon):
            self._call_soon_sent = False
            was_handled = True

        # 0th step: execute the call soon callbacks
        if len(self._call_soon) > 0:
            cs = self._call_soon
            self._call_soon = []
            for coro in cs:
                if hasattr(coro, 'send'):
                    # it's a coroutine object that needs a new value
                    # send a new one into it
                    send_coro(coro, None)
                elif not inspect.iscoroutinefunction(coro):
                    # it's a boring old function
                    # just call it
                    coro()
                else:
                    # it's a coroutine function, which needs to be called
                    # to produce a coroutine object, so do that then send
                    # a new value into it
                    send_coro(coro(), None)

        # first step: see if any callbacks need to be processed
        for mtype, cb in self._callbacks:
            if isinstance(msg, mtype):
                was_handled = True
                # call the callback and get a coroutine
                coro = cb(msg, sender)
                # now send to it to get it running
                send_coro(coro, None)

        # second step: see if any coros were waiting on that message
        mtype = type(msg)
        if mtype in self._pending_coros:
            was_handled = True
            coros = self._pending_coros[mtype]
            del self._pending_coros[mtype]
            for coro in coros:
                # send the new message into the coroutine
                send_coro(coro, (msg, sender))
        
        # third step: prepare the coros for next message
        for wobj, coro in new_coros:
            if isinstance(wobj, CoActor.MessageWaiter):
                mtype = wobj.mtype
                if mtype not in self._pending_coros:
                    self._pending_coros[mtype] = []
                self._pending_coros[mtype].append(coro)
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
        # instantiate new message waiter that waits for a WakeupMessage
        w = CoActor.MessageWaiter(WakeupMessage)
        # schedule a wakeup to be sent in the specified seconds
        self.wakeupAfter(timedelta(seconds=seconds), payload=w)
        while True:
            # use the message waiter to wait for a WakeupMessage
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
        # and send a call soon message to trigger the call,
        # (assuming we haven't sent one since the last time)
        # as call soon routines are only called when any message
        # is received
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
        if not self.has_result:
            yield self
        return self.result
