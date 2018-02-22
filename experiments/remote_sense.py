import sys
sys.path.append(".")

from thespian.actors import *
import time
from nav import DroneInDanger

bsys = ActorSystem(systemBase="multiprocTCPBase", 
    capabilities={"Convention Address.IPv4": ('localhost', 1900),
                    "Admin Port": 1901, 
                    "nav_system": False})

try:
    nav = bsys.createActor('nav.Navigation', globalName="Navigation")

    #time.sleep(10)

    bsys.tell(nav, DroneInDanger(False))

    # #bsys.tell("Navigation", DroneInDanger(False))

    print("press ENTER to see an obstacle")
    input()
    bsys.tell(nav, DroneInDanger(True))
    time.sleep(5)
    bsys.tell(nav, DroneInDanger(False))
finally:
    #time.sleep(100)
    bsys.shutdown()