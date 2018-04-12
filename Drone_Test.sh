#!/bin/bash

killall python3 dronekit-sitl
#source /home/thomas/drone_software/py_env/bin/activate

#dronekit-sitl copter &   # launch dronekit 
#sleep 15

#cd /home/thomas/drone_software/drone-SAA

xterm -title "Simulation Drone" -hold -e "source /home/thomas/drone_software/py_env/bin/activate; dronekit-sitl copter; " &
xterm -title "Navigation" -hold -e "source /home/thomas/drone_software/py_env/bin/activate; sleep 25; python3 /home/thomas/drone_software/drone-SAA/main_test.py" &
xterm -title "Sensor Module" -hold -e "source /home/thomas/drone_software/py_env/bin/activate; sleep 30; python3 /home/thomas/drone_software/drone-SAA/sense_template_wrapper_test.py"
