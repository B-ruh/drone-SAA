# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy
from coactor import CoActor, Future
from dronekit import VehicleMode
from pymavlink import mavutil
from functools import partial as curry
import math

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
        elif cmd == "move_local":
            # send position command in NED space
            # relative to current position
            mcmd = (0,       # time_boot_ms (not used)
                0, 0,    # target system, target component
                msg.args[3], # frame
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

        for attr in ('parameters', 'gps_0', 'armed',
                'mode', 'attitude'):
            await self.wait_for(attr)

    async def wait_ready_ekf(self):
        await self.wait_for('ekf_ok')
        await self.wait_for('location_local_frame')

    async def wait_for(self, attr):
        """Wait for the specified attribute to be valid, i.e. it has
          a value and so can be retrieved.

        attr: the name of the attribute

        returns: the attribute's new value
        """

        # check if it's already valid
        if self._attr_updated.get(attr, False):
            # return its value
            return getattr(self, attr.replace(".", "_"))

        # it's not, wait on it
        return await self.wait_for_next(attr)

    async def wait_for_next(self, attr):
        """Wait for an update to the specified attribute.

        Note that an update does not necessarily mean that the attribute's
        value will be any different.

        attr: the name of the attribute

        returns: the attribute's new value
        """

        fut = Future(self.actor)

        # register callback so that hwen the future is updated
        # its result is set
        self.register_cb(attr, lambda a, v: fut.set_result(v), once=True)

        # then wait on the future (and return the value which is its result)
        return await fut

    async def wait_for_new(self, attr):
        """Wait for the specified attribute to have a new value.

        attr: the name of the attribute

        returns: the attribute's new value
        """

        # check if it exists
        if self._attr_updated.get(attr, False):
            # it doesn't, so just wait until it does
            return await self.wait_for_next(attr)

        # it does, so get its value
        old_value = getattr(self, attr.replace(".", "_"))
        # and wait for it to change
        value = old_value
        while value == old_value:
            value = await self.wait_for_next(attr)

        return value

    async def wait_until(self, attr, fn, new=True):
        """Wait until the specified attribute meets some criterion.

        attr: name of the attribute
        fn: the criterion function. Called like fn(value), where value
          is the new value of the attribute. If it returns True, the
          wait is over.
        new: if True, fn is only evaluated when the attribute changes
          if False, it's evaluated every time the attribute gets an update

        returns: the new value of the attribute
        """

        wf = self.wait_for_next
        if new:
            wf = self.wait_for_new

        if attr not in self._attr_updated:
            value = await wf(attr)
        ga = attr.replace(".", "_")
        value = getattr(self, ga)
        while not fn(getattr(self, ga)):
            value = await wf(attr)

        return value

    async def arm_motors(self, arm):
        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("arm", arm))

        await self.wait_until('armed', lambda v: v == arm)

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

    def goto_local(self, north, east, down):
        """Go to the specified north, east, down position,
          relative to home.

        north, east, down: position, in meters

        returns: the final position, relative to home, as
          (north, east, down)
        """

        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("move_local", north, east, down,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED))

        return (north, east, down)

    def goto_local_rel(self, north=0, east=0, down=0):
        """Go to the specified north, east, down position,
          relative to the drone.

        north, east, down: position, in meters

        returns: the final position, relative to home, as
          (north, east, down)
        """

        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("move_local", north, east, down,
                mavutil.mavlink.MAV_FRAME_LOCAL_OFFSET_NED))

        pos = self.location_local_frame
        return (pos.north+north,
            pos.east+east,
            pos.down+down)

    def move_local(self, forward=0, right=0, down=0):
        """Move the specified amount forward, right, and down,
           relative to the drone's current position and heading.

        forward, right, down: amount, in meters

        returns: the final position, relative to home, as
            (north, east, down)
        """

        self.actor.send(self.pixhawk_addr,
            PixhawkProxyCommand("move_local", forward, right, down,
                mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED))

        pos = self.location_local_frame
        yaw = self.attitude.yaw

        return (pos.north+forward*math.cos(yaw)-right*math.sin(yaw),
            pos.east+forward*math.sin(yaw)+right*math.cos(yaw),
            pos.down+down)

    def is_close_to_local(self, pos, how_close=0.5):
        """Returns True if the vehicle is close to the specified positon.

        pos: the position, as (north, east, down) relative to home
        how_close: how close is close, in meters
        """

        our_pos = self.location_local_frame
        dist = math.sqrt((pos[0]-our_pos.north)**2 + 
            (pos[1]-our_pos.east)**2+
            (pos[2]-our_pos.down)**2)

        return dist <= how_close

    async def wait_until_close_to_local(self, pos, how_close=0.5):
        """Waits until the vehicle is close to the specified position.

        pos: the position, as (north, east, down) relative to home
        how_close: how close is close, in meters
        """

        while not self.is_close_to_local(pos, how_close):
            await self.wait_for_next('location.local_frame')

