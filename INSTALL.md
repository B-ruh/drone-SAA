This file guides you through installing all the software needed to get DroneKit and librealsense up and running with Python 3.

## Important Notes
* This guide was written for Ubuntu 16.04 LTS, running on an x86_64 architecture.
* Only use `sudo` when shown

## Installing Python

```# ensure system and packages are up to date
sudo apt update && sudo apt upgrade

# install Python 3, the Python package manager, and the Python
# virtual environment library
sudo apt install python3 python3-pip python3-venv

# create a directory for the installation
# keep this directory around
cd ~
mkdir ~/drone_software
cd ~/drone_software

# create the Python virtual environment
python3 -m venv py_env

# activate the virtual environment
# once activated, all packages are installed to the environment only
# and other packages are not available
# using an environment specifically for this software avoids contaminating
# the system's packages
source py_env/bin/activate
```

You can now work on installing the other software. Remember to always `source ~/drone_software/py_env/bin/activate` before installing any Python libraries or running any Python code. If you are done, simply type `deactivate` to return to using the system Python.

## Installing pyrealsense (for R200)

Begin by installing the legacy RealSense SDK (which supports the R200 camera and pyrealsense)

``` # change to work directory
cd ~/drone_software/

# download the RealSense SDK from Github
git clone https://github.com/IntelRealSense/librealsense/
cp -R librealsense librealsense2/
mv librealsense librealsense1/
cd librealsense1/
# select the latest legacy version
git checkout v1.12.1

# install dependencies
sudo apt install libusb-1.0-0-dev pkg-config libglfw3-dev libssl-dev cmake

# build and install librealsense
mkdir build
cd build
cmake .. -DBUILD_EXAMPLES:BOOL=true
make && sudo make install
cd ..

# unplug all cameras from the system, then
# install device driver rules for the RealSense
sudo cp config/99-realsense-libusb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && udevadm trigger

# CHECK YOUR KERNEL VERSION
uname -r
# if < 4.13, do the following steps:
# patch the kernel to support the RealSense
# if it starts asking scary questions, just
# hold ENTER until it stops
./scripts/patch-uvcvideo-16.04.simple.sh

# otherwise, you're fine

# reboot to make everything happy
reboot
```

Now that the RealSense SDK is installed, you may install the Python bindings to it.

```# prepare environment
cd ~/drone_software/
source py_env/bin/activate

# download the library from github
git clone https://github.com/toinsson/pyrealsense
cd pyrealsense

# install dependencies
pip3 install pycparser numpy cython

# build and install pyrealsense
python3 setup.py install

```

The pyrealsense install is now complete.

## Installing DroneKit

```# prepare environment
cd ~/drone_software/
source py_env/bin/activate

# install dependencies
sudo apt install libxml2-dev libxslt-dev python3-dev
pip3 install future lxml # may error, just ignore it

# download pymavlink from Github
git clone https://github.com/ArduPilot/pymavlink

# get message definitions from official package
wget https://pypi.python.org/packages/98/4f/db433a88eff6cffbc60e768680d41bfcd88eca2b7aa6b66ec1a154cf75b0/pymavlink-2.2.8.tar.gz#md5=cb17acaacaac15ba8de16bf214f347a0
tar xvf pymavlink-2.2.8.tar.gz
cp -R pymavlink-2.2.8/message_definitions/ pymavlink
rm -r pymavlink-2.2.8*

# build and install pymavlink
cd pymavlink
python3 setup.py install

cd ~/drone_software/
# download DroneKit from Github
git clone https://github.com/tpwrules/dronekit-python

# build and install DroneKit
cd dronekit-python
python3 setup.py install

# install the DroneKit simulator
pip3 install dronekit-sitl # may error, ignore it

```

## Installing drone-SAA

```# prepare environment
cd ~/drone_software/
source py_env/bin/activate

# install dependencies
pip3 install thespian

# clone it
git clone https://github.com/tpwatson-uni/drone-SAA/

```