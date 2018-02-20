# navigation processor and related stuff

from thespian.actors import *
from messages import Initialize
import copy

from coactor import CoActor
from pixhawk import *

class Navigation(CoActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # schedule important callbacks
        self.register_cb(ActorExitRequest, self.msg_shutdown)
        self.register_cb(Initialize, self.msg_init)

    async def msg_init(self, msg, sender):
        print("[NAV] Initializing!")
        self.init_data = copy.deepcopy(msg.data)
        self.init_data["actor_system"] = sender

        # create the pixhawk manager
        self.pixhawk = self.createActor('pixhawk.Pixhawk')
        # and initialize it
        self.send(self.pixhawk, Initialize(**self.init_data))

        # now create a vehicle proxy
        self.vehicle = VehicleProxy(self.pixhawk)
        # register update callback
        self.register_cb(PixhawkUpdate, self.vehicle.process_update)
        # and request updates
        self.send(self.pixhawk, PixhawkUpdateRequest())
        
        print("[NAV] Done!")
        # unregister init callback
        self.unregister_cb(Initialize, self.msg_init)

    async def msg_shutdown(self, msg, sender):
        print("[NAV] Shutdown")