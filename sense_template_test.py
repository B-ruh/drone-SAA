'''
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
'''

#########################
## Sensor Controller   ##
#########################

import pyrealsense2 as rs
import sys
import numpy as np

from nav import DroneInDanger
import time
import datetime

#distance sensitivity
#sen = 2300  #about 9'
#sen = 1300  #about 5'
sen = 300  #about 3"

#print("START REALSENSE")
print("START REALSENSE for %s mm(ish) "  % (sen))
print(datetime.datetime.now())
class SensorController:
    def __init__(self, mat):
        self.data = mat

    def __setitem__(self, mat):
        self.data = mat

    def __getitem__(self):
        return self.data

    def getDimX(self):
        return self.data.shape[0]

    def getDimY(self):
        return self.data.shape[1]

    def printShape(self):
        print("PRINT SHAPE")
        print(self.data.shape)

    def printData(self):
        print("PRINT data")
        print(self.data)

    def cropSubset(self, width):      
        c=width
        x=self.data.shape[0]
        y=self.data.shape[1]
        cx=int(c*(x/5)/2)
        dx=x-cx
        cy=int(c*(y/5)/2)
        dy=y-cy
        self.data=self.data[cx:dx,cy:dy]

    def filterSuperPix(self, layer):  #Filters using minimal meaned super pixels
        #print("inside filter")
        vectorizedSize = self.data.shape[0] * self.data.shape[1]
        npDepth1 = self.data.reshape(2,int(vectorizedSize/2)).mean(0)
        npDepth2 = npDepth1.reshape(int(vectorizedSize/2/2),2).mean(1)
        self.data = npDepth2.reshape(int(self.data.shape[0]/2),int(self.data.shape[1]/2))
        #print("done inside filter")

def main(asys, nav):
    asys.tell(nav, DroneInDanger(False))

    #######################
    d = np.array([[4, 2, 5, 6, 7, 5, 4, 3, 5, 7]])
    dataP = d
    #print("dataP.shape 1")
    #print(dataP.shape)
    # for i in range(0, 63):
    #         dataP = np.concatenate((dataP, d), axis=1)
    # dd = dataP
    # #print("dataP.shape 2")
    # #print(dataP.shape)
    # for j in range(0, 479):
    #         dataP = np.concatenate((dataP, dd), axis=0)
    # print("dataP.shape 3")
    # print(dataP.shape)

    #######################

    sc = SensorController(dataP)

    try:
        # Create a context object. This object owns the handles to all connected realsense devices
        pipeline = rs.pipeline()
        pipeline.start()
        print("in Try")
        while True:
            #print("in while")
            # This call waits until a new coherent set of frames is available on a device
            # Calls to get_frame_data(...) and get_frame_timestamp(...) on a device will return stable values until wait_for_frames(...) is called
            print(datetime.time.now())
            frames = pipeline.wait_for_frames()
            depth = frames.get_depth_frame()

            npDepth = np.empty([480, 640])
            if not depth: continue
            #if (depth): print("DEPTH INDEED")

            npDepth = np.asanyarray(depth.get_data())

            #print("npDepth initialized with double for")

            sc.__setitem__(npDepth)
            #print("npDepth initialized")
            # print("***********************************************************")
            # print("***********************************************************")
            # sc.printShape()
            # print("***********************************************************")
            # print("***********************************************************")

            sc.cropSubset(2)
            #print("cropped")
            #sc.printShape()

            sc.filterSuperPix(1)
            sc.filterSuperPix(1)
            sc.filterSuperPix(1)
            sc.filterSuperPix(1)
            #print("filrered")
            #sc.printShape()
            print(datetime.time.now())
            for yy in range(0,sc.getDimY(),1):
                for xx in range(0,sc.getDimX(),1):
                    #print("%1.1f " % npDepth3[xx, yy], end=" ")
                    #print("%1.1f " % sc.__getitem__()[xx, yy], end=" ")
                    #if (3.0 > npDepth3[xx, yy] and npDepth3[xx, yy] > 0.3):
                    z=sc.__getitem__()[xx, yy]
                    if (z < sen):
                        #print(datetime.datetime.now())
                        print("Obstacle!! %s at %s %s"  % (z, xx, yy))
                        asys.tell(nav, DroneInDanger(True))
                        #print(datetime.datetime.now())
                    else :
                        asys.tell(nav, DroneInDanger(False))
                        continue
                        #print()
                #print('\n\n')
        exit(0)
    #except rs.error as e:
    #    # Method calls agaisnt librealsense objects may throw exceptions of type pylibrs.error
    #    print("pylibrs.error was thrown when calling %s(%s):\n", % (e.get_failed_function(), e.get_failed_args()))
    #    print("    %s\n", e.what())
    #    exit(1)
    except Exception as e:
        print(e)
    pass
