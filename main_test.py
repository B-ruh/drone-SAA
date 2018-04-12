# main SAA program

from thespian.actors import *
from messages import Initialize
import time

from dk import Dronekit
from pixhawk import PixhawkStartDronekit

if __name__ == "__main__":
    # start up actor system
    asys = ActorSystem(systemBase="multiprocTCPBase",
        capabilities={"nav_system": True, "Convention Address.IPv4": "localhost:1900"}) #capabilities={"nav_system": True)

    while not ('nav' in locals()): #This while loop solution did not work and should be removed at a later date; howver it does not harm anything to keep it
        try:
            # instantiate navigation processor
            nav = asys.createActor("nav.Navigation", globalName="Navigation")
            # tell it to start up
            asys.tell(nav, Initialize())

            # wait for certain messages
            while True:
                msg = asys.listen()
                if isinstance(msg, PixhawkStartDronekit):
                    dk = Dronekit()
                    dk.start('tcp:127.0.0.1:5763', msg.addr, asys)
        finally:
            # clean up everything
            # if this isn't called, Python processes will start to build up
            #asys.shutdown()
            print("No Connection, trying again.")
            time.sleep(5)
    asys.shutdown()
