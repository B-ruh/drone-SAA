from thespian.actors import *
import time
from nav import DroneInDanger

import sys

class NavDummy(Actor):
    def receiveMessage(self, msg, sender):
        if isinstance(msg, DroneInDanger):
            print("Danger status: {}".format(msg.danger))

asys = None
nav = None

if __name__ == "__main__":
    try:
        try:
            dummy = sys.argv[1] != "testing"
        except:
            dummy = False

        if dummy:
            asys = ActorSystem(systemBase="multiprocTCPBase",
                capabilities={"Admin Port": 1999})
        else:
            asys = ActorSystem(systemBase="multiprocTCPBase", 
                capabilities={"Convention Address.IPv4": ('localhost', 1900),
                                "Admin Port": 1901, 
                                "nav_system": False})

        nav = None

        if dummy:
            nav = asys.createActor(NavDummy)
        else:
            nav = asys.createActor('nav.Navigation', globalName="Navigation")

        import sense_template
        sense_template.main(asys, nav)
    finally:
        asys.shutdown()