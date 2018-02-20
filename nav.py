# navigation processor and related stuff

from thespian.actors import *

class Navigation(Actor):
    def receiveMessage(self, message, sender):
        print("Got: {} from {}".format(message, sender))