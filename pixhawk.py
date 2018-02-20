# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy

class Pixhawk(Actor):
    def receiveMessage(self, msg, sender):
        if isinstance(msg, Initialize):
            print("[PIX] Initializing!")
            self.init_data = copy.deepcopy(msg.data)