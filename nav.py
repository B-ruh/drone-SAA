# navigation processor and related stuff

from thespian.actors import *
from messages import Initialize
import copy

from coactor import CoActor, Future
from pixhawk import *

# sent to the navigation if the drone is about to hit something
class DroneInDanger:
    def __init__(self, danger=True):
        self.danger = danger

class Navigation(CoActor):
    @staticmethod
    def actorSystemCapabilityCheck(capabilities, requirements=None):
        return capabilities.get("nav_system", False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # schedule important callbacks
        self.register_cb(ActorExitRequest, self.msg_shutdown)
        self.register_cb(Initialize, self.msg_init)
        self.register_cb(DroneInDanger, self.msg_in_danger)

        # monitor if we're in danger, i.e. about to hit something
        self.in_danger = False
        self.in_danger_fut = None

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
        #async def do_a_stop():
        #    await self.sleep(20)
        #    self.send(self.myAddress, DroneInDanger(True))
        #    await self.vehicle.wait_until('heading', lambda h: h < 300)
        #    self.send(self.myAddress, DroneInDanger(False))

        #self.call_soon(do_a_stop)

        while True:
            await self.wait_for_danger()
            # we're about to hit something!
            print("[NAV] in danger, stopping!!!")
            self.vehicle.stop_now()
            # wait until we stop
            await self.vehicle.wait_until('airspeed',
                lambda s: s < 0.1)

            print("[NAV] Stopped, looking around")
            self.vehicle.set_mode("GUIDED")
            heading = await self.vehicle.wait_for_next('heading')

            amount_rotated = 0
            while amount_rotated <= 360:
                heading -= 10
                amount_rotated += 10
                self.vehicle.set_heading(heading % 360)
                # wait until we get to the specified heading
                await self.vehicle.wait_until('heading',
                    # will mess up around a circle
                    # but fine for testing
                    lambda h: h-(heading%360) < 2)
                # updated by receiving the DroneInDanger message

                if not self.in_danger:
                    break

            print("[NAV] Moving beside the obstacle...")
            # do 10 meters forward or so by default
            pos = self.vehicle.move_local(forward=10)
            while not self.vehicle.is_close_to_local(pos):
                if self.in_danger:
                    print("[NAV] Oh no! There it is again!")
                    self.vehicle.stop_now()
                    break
                await self.vehicle.wait_for_next('location.local_frame')

            if not self.in_danger:
                print("[NAV] Okay, it's clear...")
                self.vehicle.set_mode("AUTO")

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

    async def msg_in_danger(self, msg, sender):
        self.in_danger = msg.danger
        if self.in_danger_fut is not None:
            self.in_danger_fut.set_result(self.in_danger)
            self.in_danger_fut = None

    async def wait_for_danger(self):
        while not self.in_danger:
            await self.wait_for_next_danger()

    async def wait_for_next_danger(self):
        if self.in_danger_fut is None:
            self.in_danger_fut = Future(self)
        await self.in_danger_fut
