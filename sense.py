# manager for sensors

import threading
from nav import DroneInDanger

# Sensor manager gets its own thread
class SensorManager:
    # pass the actor id of the nav manager, and the actor system
    def start(self, actor, sys):
        self._thread_obj = \
            threading.Thread(target=self._thread, args=(actor, sys),
                daemon=True)
        self._thread_obj.start()

    def _thread(self, actor, sys):
        self.asys = sys
        self.actor = actor
        self.hsys = None

        # get our own private connection to the actor system
        self.psys = sys.private()
        # it's a context manager, so enter it to get the interactable object
        self.psys = self.psys.__enter__()

        # we can now sense!

    def set_danger_status(self, status):
        self.psys.tell(self.actor, DroneInDanger(status))
        