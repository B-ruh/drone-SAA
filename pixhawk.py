# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy
from coactor import CoActor, Future
from dronekit import VehicleMode
from pymavlink import mavutil

from dk import *

# a command from the vehicle proxy to do something
class PixhawkProxyCommand:
    def __init__(self, cmd, *args):
        self.cmd = cmd
        self.args = args

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

        self.attrs = {}

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
        msg, sender = await self.wait_msg(DronekitReady)
        self.dk_addr = sender
        
        print("[PIX] Done!")
        # unregister init callback
        self.unregister_cb(Initialize, self.msg_init)
        # register proxy message callback
        self.register_cb(PixhawkProxyCommand, self.msg_proxy_cmd)
        

    async def msg_shutdown(self, msg, sender):
        print("[PIX] Shutdown")

    async def msg_dk_update(self, msg, sender):
        # save the value in ourselves
        self.attrs[msg.attr_name] = msg.value

        # and broadcast the value to the actors who want it
        for updatee in self.updatees:
            self.send(updatee, msg)

    async def msg_update_req(self, msg, sender):
        if msg.enable:
            self.updatees.append(sender)
            # send the current parameters to ensure the new updatee
            # has all of them
            self.send(sender, PixhawkUpdate(None, self.attrs))
        else:
            if sender in self.updatees:
                self.updatees.remove(sender)

    async def msg_proxy_cmd(self, msg, sender):
        cmd = msg.cmd
        if cmd == "arm":
            # flip armed to the specified value
            self.send(self.dk_addr,
                DronekitSetAttr('armed', msg.args[0]))
        elif cmd == "mode":
            # set mode to the specified value,
            # after converting it into that weird VehicleMode
            self.send(self.dk_addr,
                DronekitSetAttr('mode', VehicleMode(msg.args[0])))
        elif cmd == "takeoff":
            # send TAKEOFF command and get drone to specified altitude
            altitude = float(msg.args[0])
            mcmd = (0, 0, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                    0, 0, 0, 0, 0, 0, 0, altitude)
            self.send(self.dk_addr,
                DronekitSendCommand("command_long", *mcmd))

# proxy for the vehicle
# receives PixhawkUpdates to update its parameters
# has methods to send commands to the Pixhawk manager as well
# and can call callbacks when specific paramters are updated
class VehicleProxy:
    def __init__(self, actor, pixhawk_addr):
        self.actor = actor
        self.pixhawk_addr = pixhawk_addr
        self._callbacks = []
        self._attr_updated = {}

    async def process_update(self, msg, sender):
        if msg.attr_name == None and isinstance(msg.value, dict):
            # it's a bulk attribute update
            for attr, value in msg.value.items():
                self._update_attr(attr, value)
        else:
            # just one
            self._update_attr(msg.attr_name, msg.value)

    def _update_attr(self, attr, value):
        # update the parameter in question
        setattr(self, attr.replace(".", "_"), value)
        self._attr_updated[attr] = True
        # and call any callbacks
        cb = []
        for attr_name, fn, once in self._callbacks:
            if attr_name == attr:
                self.actor.call_soon(lambda: fn(attr, value))
                if once: continue
            cb.append((attr_name, fn, once))
        self._callbacks = cb

    def register_cb(self, attr_name, fn, once=False):
        self._callbacks.append((attr_name, fn, once))

    async def wait_ready(self):
        await self.wait_for(('parameters', 'gps_0', 'armed',
            'mode', 'attitude'))

    # wait for the specified attributes to be valid
    async def wait_for(self, attrs=None):
        if isinstance(attrs, str):
            attrs = (attrs,)

        futs = []
        for attr in attrs:
            # is this one already ready? if so, continue
            if self._attr_updated.get(attr, False): continue
            # create a Future for this attribute
            fut = Future(self.actor)
            # that will get its result when the attribute comes in
            self.register_cb(attr, lambda a, v: fut.set_result((a, v)), True)
            futs.append(fut)

        # now wait for all the futures to have a result
        # -> all the results have come in
        for fut in futs:
            if fut.has_result: continue
            await fut

    # wait for the next update for the specified attributes
    async def wait_for_next(self, attrs=None):
        if isinstance(attrs, str):
            attrs = (attrs,)

        for attr in attrs:
            self._attr_updated[attr] = False

        await self.wait_for(attrs)

    async def wait_until(self, attr, fn):
        if attr not in self._attr_updated:
            await self.wait_for_next(attr)
        ga = attr.replace(".", "_")
        while not fn(getattr(self, ga)):
            await self.wait_for_next(attr)

    async def arm_motors(self, arm):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("arm", arm))

        while self.armed != arm:
            await self.wait_for_next('armed')

    def set_mode(self, mode):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("mode", mode))

    async def takeoff(self, altitude):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("takeoff", altitude))

        curr_alt = self.location_global_relative_frame.alt
        if curr_alt < 0.01: curr_alt = 0.01
        while abs((curr_alt-altitude)/altitude) > 0.05:
            await self.wait_for_next("location.global_relative_frame")
            curr_alt = self.location_global_relative_frame.alt

    def stop_now(self):
        # set mode to BRAKE
        self.set_mode("BRAKE")
