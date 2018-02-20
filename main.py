# main SAA program

from thespian.actors import *
from messages import Initialize
import time

if __name__ == "__main__":
    # start up actor system
    asys = ActorSystem("multiprocTCPBase", transientUnique=True)

    try:
        # instantiate navigation processor
        nav = asys.createActor("nav.Navigation")
        # tell it to start up
        asys.tell(nav, Initialize())

        # do nothing, program is now working
        while True:
            time.sleep(1)
    finally:
        # clean up everything
        # if this isn't called, Python processes will start to build up
        asys.shutdown()
