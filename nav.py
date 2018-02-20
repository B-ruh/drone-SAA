# navigation processor and related stuff

from thespian.actors import *
from messages import Initialize
import copy

class Navigation(Actor):
    def receiveMessage(self, msg, sender):
        if isinstance(msg, Initialize):
            print("[NAV] Initializing!")
            self.init_data = copy.deepcopy(msg.data) # clone init data
            self.init_data["actor_system"] = sender # save actor system address

            # create the pixhawk manager
            self.pixhawk = self.createActor('pixhawk.Pixhawk')
            # and initialize it
            self.send(self.pixhawk, Initialize(**self.init_data))