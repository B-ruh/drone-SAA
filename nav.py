# navigation processor and related stuff

from thespian.actors import *
from messages import Initialize
import copy

from coactor import CoActor, Future
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
        self.vehicle = VehicleProxy(self, self.pixhawk)
        # register update callback
        self.register_cb(PixhawkUpdate, self.vehicle.process_update)
        # and request updates
        self.send(self.pixhawk, PixhawkUpdateRequest())

        print("[NAV] Done!")
        # unregister init callback
        self.unregister_cb(Initialize, self.msg_init)

        # and schedule main loop
        self.call_soon(self.nav)

    async def nav(self):
        await self.vehicle.wait_ready()
        print("[NAV] Testing liftoff")
        await self.takeoff()

        print("[NAV] Beginning main loop")
        while True:
            await self.vehicle.wait_for_next('mode')
            print("The new mode is: {}".format(self.vehicle.mode))

    async def takeoff(self):
        #print("[NAV] Waiting for vehicle to be armable")
        # maybe should actually do this

        if self.vehicle.armed:
            print("[NAV] Returning to launch")
            self.vehicle.set_mode("RTL")
            while self.vehicle.armed:
                await self.vehicle.wait_for_next('armed')

        self.vehicle.set_mode("STABILIZE")

        print("[NAV] Arming motors")
        await self.vehicle.arm_motors(True)

        print("[NAV] Taking off!")
        self.vehicle.set_mode("GUIDED")
        await self.vehicle.takeoff(20) # meters

        print("[NAV] Beginning mission")
        self.vehicle.set_mode("AUTO")


    async def msg_shutdown(self, msg, sender):
        print("[NAV] Shutdown")