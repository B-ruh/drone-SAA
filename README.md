# drone-SAA
Stop and Avoid program for drone companion computer

## Running the Program

1. Follow the installation steps
2. Open three terminals and `source ~/dronekit_software/py_env/bin/activate`
3. In the first terminal, start the simulation by running `dronekit-sitl copter`.
4. Connect Mission Planner to the simulation by connecting to TCP localhost port 5760
5. Start the navigation program in the second terminal with `python3 main.py`
6. Start the fake sensor framework in the third terminal with `python3 sense_template_wrapper.py`