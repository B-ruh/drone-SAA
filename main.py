# main SAA program

from thespian.actors import *
from messages import Initialize
import time

from dk import Dronekit
from pixhawk import PixhawkStartDronekit
import sense

if __name__ == "__main__":
    # start up actor system
    asys = ActorSystem("multiprocTCPBase")

    try:
        # instantiate navigation processor
        nav = asys.createActor("nav.Navigation")
        # tell it to start up
        asys.tell(nav, Initialize())

        # start up sensor manager
        sensor = sense.SensorManager()
        sensor.start(nav, asys)

        # wait for certain messages
        while True:
            msg = asys.listen()
            if isinstance(msg, PixhawkStartDronekit):
                dk = Dronekit()
                dk.start('tcp:127.0.0.1:5763', msg.addr, asys)
    finally:
        # clean up everything
        # if this isn't called, Python processes will start to build up
        asys.shutdown()
