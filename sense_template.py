from nav import DroneInDanger
import time

def main(asys, nav):
    asys.tell(nav, DroneInDanger(False))

    print("press ENTER to see an obstacle")
    input()
    asys.tell(nav, DroneInDanger(True))
    time.sleep(5)
    asys.tell(nav, DroneInDanger(False))

