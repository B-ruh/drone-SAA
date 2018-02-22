from nav import DroneInDanger
import time

def main(asys, nav):
    asys.tell(nav, DroneInDanger(False))

    print("press ENTER to see an obstacle")
    input()
    print("Seeing it for 5 seconds")
    asys.tell(nav, DroneInDanger(True))
    time.sleep(5)
    print("ok it's gone")
    asys.tell(nav, DroneInDanger(False))

