# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy
from coactor import CoActor, Future
from dronekit import VehicleMode
from pymavlink import mavutil
from functools import partial as curry

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
    """Actor that manages the Pixhawk flight controller."""

    @staticmethod
    def actorSystemCapabilityCheck(capabilities, requirements=None):
        # make sure we're started on an actor system that 
        # is actually connected to the pixhawk
        return capabilities.get("nav_system", False)

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
        elif cmd == "heading":
            # send YAW command to change the heading
            # we always use it in non-relative
            mcmd = (0, 0,    # target system, target component
                    mavutil.mavlink.MAV_CMD_CONDITION_YAW, #command
                    0, #confirmation
                    msg.args[0],    # param 1, yaw in degrees
                    0,          # param 2, yaw speed deg/s
                    1,          # param 3, direction -1 ccw, 1 cw
                    0, # param 4, relative offset 1, absolute angle 0
                    0, 0, 0)
            self.send(self.dk_addr,
                DronekitSendCommand("command_long", *mcmd))
        elif cmd == "move_ned_body_offset":
            # send position command in NED space
            # relative to current position
            mcmd = (0,       # time_boot_ms (not used)
                0, 0,    # target system, target component
                mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED, # frame
                0b0000111111111000, # type_mask (only positions enabled)
                msg.args[0], msg.args[1], msg.args[2],
                0, 0, 0, # x, y, z velocity in m/s  (not used)
                0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
                0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
            self.send(self.dk_addr,
                DronekitSendCommand("set_position_target_local_ned", *mcmd))

# proxy for the vehicle
# receives PixhawkUpdates to update its parameters
# has methods to send commands to the Pixhawk manager as well
# and can call callbacks when specific paramters are updated
class VehicleProxy:
    """Proxy for the dronekit Vehicle.

    You may wish to consult http://python.dronekit.io/automodule.html
    to get an idea of what attributes are available. Note that not
    all are. Also note that dots in attribute names become underscores
    when you get them from the proxy, but not when passed as strings
    to function names!

    To use:
    * Instantiate the proxy: p = VehicleProxy(self, self.pixhawk_addr)
      where pixhawk_addr is the address of the Pixhawk actor and self
      is the actor that will own the proxy
    * Enable update messages from the Pixhawk actor by sending
      it the message PixhawkUpdateRequest(True)
    * Call p.process_update(msg, sender) with the msg and sender of all
      PixhawkUpdate messages received
    """

    def __init__(self, actor, pixhawk_addr):
        """Initialize the proxy.

        actor: actor object of the proxy owner, usually self
        pixhawk_addr: actor address of the Pixhawk addr
        """
        self.actor = actor
        self.pixhawk_addr = pixhawk_addr
        self._callbacks = []
        self._attr_updated = {}

    async def process_update(self, msg, sender):
        """Process an update message.

        Call this function with the msg and sender for every
        PixhawkUpdate message the proxy owner receives.
        """

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
                self.actor.call_soon(curry(fn, attr, value))
                if once: continue
            cb.append((attr_name, fn, once))
        self._callbacks = cb

    def register_cb(self, attr_name, fn, once=False):
        """Register a callback for attribute changes.

        attr_name: the name of the attribute
        fn: the function called. Called like fn(attr_name, value) where
          attr_name is the name of the attribute and value is its new value.
        once: if True, the callback is only called once
        """

        self._callbacks.append((attr_name, fn, once))

    async def wait_ready(self):
        """Wait for the drone to be ready."""

        # same commands as in DroneKit
        await self.wait_for(('parameters', 'gps_0', 'armed',
            'mode', 'attitude'))

    async def wait_for(self, attrs=None):
        """Wait for the specified attributes to be valid, i.e. they have
          a value and so can be retrieved.

        attrs: either a str containing one attribute name, or an iterable
          of strs of attribute names
        """

        if isinstance(attrs, str):
            attrs = (attrs,)

        # helper to make a callback for the future
        # needed because closing over a loop variable only uses the 
        # last iteration's value
        def make_wait_cb(fut):
            def wait_cb(a, v):
                fut.set_result((a, v))
            return wait_cb

        futs = []
        for attr in attrs:
            # is this one already ready? if so, continue
            if self._attr_updated.get(attr, False): continue
            # create a Future for this attribute
            fut = Future(self.actor)
            # that will get its result when the attribute comes in
            self.register_cb(attr, make_wait_cb(fut), True)
            futs.append(fut)

        # now wait for all the futures to have a result
        # -> all the results have come in
        for fut in futs:
            if fut.has_result: continue
            await fut

    # wait for the next update for the specified attributes
    async def wait_for_next(self, attrs=None):
        """Wait for the next update for the specified attributes.

        Note that an update does not necessarily mean the attribute value
        is different.

        attrs: either a str containing one attribute name, or an iterable
          of such        
        """

        if isinstance(attrs, str):
            attrs = (attrs,)

        for attr in attrs:
            self._attr_updated[attr] = False

        await self.wait_for(attrs)

    async def wait_until(self, attr, fn):
        """Wait until the specified attribute meets some criterion.

        attr: name of the attribute
        fn: the criterion function. Called like fn(value), where value
          is the next value of the attribute. If it returns True, the
          wait is over.

        Note that the criterion function may be called multiple times
        with the same value.
        """
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
        # we stop by BRAKEing
        self.set_mode("BRAKE")

    def set_heading(self, heading):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("heading", heading))

    def move_rel_body(self, forward, right, down):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("move_ned_body_offset", forward, right, down))
