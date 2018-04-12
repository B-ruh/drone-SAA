#!/bin/bash

echo "watson" | sudo -S killall python3 dronekit-sitl

xterm -title "Navigation" -hold -e "source /home/thomas/drone_software/py_env/bin/activate; sleep 5; python3 /home/thomas/drone_software/drone-SAA/main.py" &
xterm -title "Sensor Module" -hold -e "source /home/thomas/drone_software/py_env/bin/activate; sleep 10; python3 /home/thomas/drone_software/drone-SAA/sense_template_wrapper.py"
