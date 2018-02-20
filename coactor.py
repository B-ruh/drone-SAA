# actor type that uses coroutines

from thespian.actors import *
import traceback
from datetime import timedelta

class CoActor(Actor):
    # class that yields message information when awaited
    class MessageWaiter:
        def __init__(self, mtype):
            self.mtype = mtype
        def __await__(self):
            return (yield self)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initialize our own state
        self._callbacks = []
        self._pending_coros = {}

    def receiveMessage(self, msg, sender):
        # we've got a message

        was_handled = False

        # keep list of coros made from this message so they don't see
        # the message twice
        new_coros = []

        # first step: see if any callbacks need to be processed
        for mtype, cb in self._callbacks:
            if isinstance(msg, mtype):
                was_handled = True
                # call the callback and get a coroutine
                coro = cb(msg, sender)
                # now send it to get it running
                try:
                    msgwaiter = coro.send(None)
                except StopIteration:
                    # oh, the coroutine finished already
                    msgwaiter = None
                except:
                    # oh heck
                    traceback.print_exc()
                    continue
                if msgwaiter is not None:
                    # stash the coro so it's called when
                    # its next message comes in
                    new_coros.append((msgwaiter, coro))

        # second step: see if any coros were waiting on that message
        if type(msg) in self._pending_coros:
            coros = self._pending_coros[type(msg)]
            del self._pending_coros[type(msg)]
            for coro in coros:
                was_handled = True
                # send the new message into the coroutine
                try:
                    msgwaiter = coro.send((msg, sender))
                except StopIteration:
                    # coroutine is finished
                    msgwaiter = None
                except:
                    # oh heck
                    traceback.print_exc()
                    continue
                if msgwaiter is not None:
                    # stash the coro so it's called when
                    # its next message comes in
                    new_coros.append((msgwaiter, coro))
        
        # third step: prepare the coros for next message
        for msgwaiter, coro in new_coros:
            mtype = msgwaiter.mtype
            if mtype not in self._pending_coros:
                self._pending_coros[mtype] = []
            self._pending_coros[mtype].append(coro)

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
