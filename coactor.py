# actor type that uses coroutines

from thespian.actors import *
import traceback
from datetime import timedelta
import inspect

class CoActor(Actor):
    """CoActor is a subclass of Thespian's Actor which emulates an event
    loop to support coroutines based on incoming messages.

    Refer to the methods for the features this enables.
    """
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
                if hasattr(coro, 'send'):
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
        """Register a callback which is called when the
        desired type of message is received.

        mtype: The type of message. Received message msg is considered the same
          type when isinstance(msg, mtype) is True.

        cb: The callback to call. It's called like cb(msg, sender) where msg
          is the received message and sender is the address of the actor
          that sent it. The callback can either be a coroutine or regular
          function.
        """

        self._callbacks.append((mtype, cb))

    def unregister_cb(self, mtype, cb):
        """Unregister a callback registered with register_cb."""

        self._callbacks.remove((mtype, cb))

    async def sleep(self, seconds):
        """Asynchronously sleep for a specified number of seconds."""

        # instantiate new message waiter that waits for a WakeupMessage
        w = CoActor.MessageWaiter(WakeupMessage)
        # schedule a wakeup to be sent in the specified seconds
        self.wakeupAfter(timedelta(seconds=seconds), payload=w)
        while True:
            # use the message waiter to wait for a WakeupMessage
            msg, sender = await w
            # make sure it's for this wakeup
            if msg.payload == w: break

    async def wait_msg(self, mtype, validator=None):
        """Asynchronously wait for a specific type of message.

        mtype: The type of message. Received message msg is considered the same
          type when isinstance(msg, mtype) is True.

        validator: If not None, an additional function to validate the
          received message. Called like validator(msg, sender), where msg
          is the received message and sender is the address of the actor
          that sent it. If validator(msg, sender) == True and the message
          is the same type, the wait is over.
        """

        # wait for the message type
        w = CoActor.MessageWaiter(mtype)
        while True:
            # wait for a new message of that type
            msg, sender = await w
            # make sure it's one we want
            if validator is None or validator(msg, sender):
                return msg, sender

    def call_soon(self, fn):
        """Call a function soon.

        fn: The function to be called. Called with no arguments.
          Can be a regular function, coroutine function, or 
          coroutine object.
        """

        # append it to call soon list
        self._call_soon.append(fn)
        # and send a call soon message to trigger the call,
        # (assuming we haven't sent one since the last time)
        # as call soon routines are only called when any message
        # is received
        if not self._call_soon_sent:
            self._call_soon_sent = True
            self.send(self.myAddress, CoActor.CallSoon())

class FutureInvalidState(Exception):
    """Exception raised when an invalid operation is performed on a Future."""

    pass

class Future:
    """Basic Future implementation for CoActors

    * Instantiate with fut = Future(actor).
      actor: the actor that instantiated the future

    * Wait for it to have a result like result = await fut.
      Only coroutines within the actor that instantiated the future can
      await the future.

    * Check if it has a result with fut.has_result.
      Get the result with fut.result.

    * Set the result with fut.set_result(something)
      Gives result to all coroutines awaiting on the future.
      Once result is set, trying to set another result throws
      FutureInvalidState.
    """

    def __init__(self, actor):
        """Initialize the future.

        actor: CoActor object the future is associated with.
          Only coroutines within that CoActor can await on the future.
        """

        self.actor = actor
        self._waiters = []

        self.has_result = False
        self.result = None

    def set_result(self, result):
        """Set the result of the future.

        Unwaits all coroutines that were waiting on the result.
        Throws FutureInvalidState if the result has already been set.
        """

        if self.has_result:
            raise FutureInvalidState()

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
