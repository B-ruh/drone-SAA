from nav import DroneInDanger
import time

def main(asys, nav):
    asys.tell(nav, DroneInDanger(False))

    while True:
        print("press ENTER to see an obstacle")
        input()
        print("Seeing it for 5 seconds")
        asys.tell(nav, DroneInDanger(True))

        print("press ENTER to make it go away")
        input()
        asys.tell(nav, DroneInDanger(False))
        print("ok it's gone")
