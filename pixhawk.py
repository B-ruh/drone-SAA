# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy
from coactor import CoActor

from dk import *

class PixhawkStartDronekit:
    def __init__(self, pixhawk_addr):
        # store Pixhawk's address
        self.addr = pixhawk_addr

# enable/disable sending pixhawk updates to the actor
# that sent the message
class PixhawkUpdateRequest:
    def __init__(self, enable=True):
        self.enable = enable

class Pixhawk(CoActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # schedule important callbacks
        self.register_cb(ActorExitRequest, self.msg_shutdown)
        self.register_cb(Initialize, self.msg_init)

        self.updatees = []

    async def msg_init(self, msg, sender):
        print("[PIX] Initializing!")
        self.init_data = copy.deepcopy(msg.data)

        # register callback for messages
        self.register_cb(PixhawkUpdate, self.msg_dk_update)
        self.register_cb(PixhawkUpdateRequest, self.msg_update_req)
        
        # tell the main actor system it's time to start dronekit
        self.send(self.init_data["actor_system"],
            PixhawkStartDronekit(self.myAddress))

        # wait for it to be ready
        await self.wait_msg(DronekitReady)
        
        print("[PIX] Done!")
        # unregister init callback
        self.unregister_cb(Initialize, self.msg_init)

    async def msg_shutdown(self, msg, sender):
        print("[PIX] Shutdown")

    async def msg_dk_update(self, msg, sender):
        # broadcast messages to the actors who want it
        for updatee in self.updatees:
            self.send(updatee, msg)

    async def msg_update_req(self, msg, sender):
        if msg.enable:
            self.updatees.append(sender)
        else:
            if sender in self.updatees:
                self.updatees.remove(sender)

# proxy for the vehicle
# receives PixhawkUpdates to update its parameters
# has methods to send commands to the Pixhawk manager as well
# and can call callbacks when specific paramters are updated
class VehicleProxy:
    def __init__(self, actor, pixhawk_addr):
        self.actor = actor
        self.pixhawk_addr = pixhawk_addr
        self._callbacks = []

    async def process_update(self, msg, sender):
        # update the parameter in question
        setattr(self, msg.attr_name, msg.value)
        # and call any callbacks
        cb = []
        for attr_name, fn, once in self._callbacks:
            if attr_name == msg.attr_name:
                self.actor.call_soon(lambda: fn(attr_name, msg.value))
                if once: continue
            cb.append((attr_name, fn, once))
        self._callbacks = cb

    def register_cb(self, attr_name, fn, once=False):
        self._callbacks.append((attr_name, fn, once))
