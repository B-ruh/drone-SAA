# manager for dronekit
# directly controlled by Pixhawk

import threading
from dronekit import *

# set a specific vehicle attribute
class DronekitSetAttr:
    def __init__(self, attr, value):
        self.attr = attr
        self.value = value

# send a MAVLink command
# cmd = "command_long"
# *args = [0, 0, 1, 3] etc
# -> vehicle.send_mavlink(vehicle.message_factory.command_long_encode(*args))
class DronekitSendCommand:
    def __init__(self, cmd, *args):
        self.cmd = cmd
        self.args = args

class DronekitReady:
    pass

class PixhawkUpdate:
    def __init__(self, attr_name, value):
        self.attr_name = attr_name
        self.value = value
    def __repr__(self):
        return "{} = {}".format(self.attr_name, self.value)

# Dronekit gets its own thread
class Dronekit:
    # pass the connection string, the actor id of Pixhawk, and the actor system
    def start(self, connection_string, actor, sys):
        self._thread_obj = \
            threading.Thread(target=self._thread, args=(connection_string, actor, sys),
                daemon=True)
        self._thread_obj.start()

    def _thread(self, connection_string, actor, sys):
        self.asys = sys
        self.actor = actor
        self.hsys = None

        # get our own private connection to the actor system
        self.psys = sys.private().__enter__()

        # send message saying we're ready
        self.psys.tell(self.actor, DronekitReady())

        # start dronekit
        self.vehicle = connect(connection_string, _initialize=False)
        # observe EVERYTHING!!!
        self.vehicle.add_attribute_listener('*', self.attr_handler)
        self.vehicle.initialize(4, 30)

        # and enter receive loop
        while True:
            msg = self.psys.listen(0.1)
            if isinstance(msg, DronekitSetAttr):
                setattr(self.vehicle,
                    msg.attr, msg.value)
            elif isinstance(msg, DronekitSendCommand):
                enc = getattr(self.vehicle.message_factory,
                    msg.cmd+"_encode")
                encmsg = enc(*msg.args)
                self.vehicle.send_mavlink(encmsg)

    def attr_handler(self, vehicle, attr_name, value):
        # the handler gets another system context because it's on another thread
        # (i think)
        if self.hsys is None:
            self.hsys = self.asys.private().__enter__()
        if attr_name in ("parameters", "location", "channels"):
            # todo: figure out how to send these without dying
            # of pickle errors
            value = "hi this doesn;t work yet"

        self.hsys.tell(self.actor, PixhawkUpdate(attr_name, value))
