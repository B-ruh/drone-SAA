# manager for dronekit
# directly controlled by Pixhawk

import threading
from dronekit import *
from thespian.actors import ActorSystem

class DronekitSetVariable:
    pass

class DronekitUpdate:
    def __init__(self, attr_name, value):
        self.attr_name = attr_name
        self.value = value
    def __repr__(self):
        return "{} = {}".format(self.attr_name, self.value)

class DronekitReady:
    pass

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
        self.psys = sys.private()
        # it's a context manager, so enter it to get the interactable object
        self.psys = self.psys.__enter__()

        # start dronekit
        self.vehicle = connect(connection_string)
        # observe EVERYTHING!!!
        self.vehicle.add_attribute_listener('*', self.attr_handler)

        self.vehicle.wait_ready()
        # send message saying we're ready
        self.psys.tell(self.actor, DronekitReady())

        # and enter receive loop
        while True:
            msg = self.psys.listen(0.1)

    def attr_handler(self, vehicle, attr_name, value):
        # the handler gets another system context because it's on another thread
        # (i think)
        if self.hsys is None:
            self.hsys = self.asys.private().__enter__()
        if attr_name in ("parameters", "location", "channels"):
            # todo: figure out how to send these without dying
            # of pickle errors
            return
        self.hsys.tell(self.actor, DronekitUpdate(attr_name, value))