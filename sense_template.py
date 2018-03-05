#########################
## Sensor Controller   ##
#########################

import pyrealsense2 as rs
import sys
import numpy as np

from nav import DroneInDanger
import time

class SensorController:
    def cropSubset(self, data, width):
        c=width
        x=data.shape[0]
        y=data.shape[1]
        cx=c*(x/5)/2
        dx=x-cx
        cy=c*(y/5)/2
        dy=y-cy
        data=data[cx:dx,cy:dy]

    def filterSuperPix(self, dataD, depthDataraw, layer):  #Needs more work!!
        for y in range(0,dataD.shape[1],1):
            for x in range(0,dataD.shape[0],1):
                dataD[x, y] = depthDataraw.get_distance(x, y)
        npDepth1 = dataD.reshape(2,(dataD.shape[1]*dataD.shape[0]/2)).mean(0)
        npDepth2 = npDepth1.reshape((dataD.shape[1]*dataD.shape[0]/2/2),2).mean(1)
        npDepth3 = npDepth2.reshape(5,5)       

def main(asys, nav):
    asys.tell(nav, DroneInDanger(False))
    try:
        # Create a context object. This object owns the handles to all connected realsense devices
        pipeline = rs.pipeline()
        pipeline.start()

        while True:
            # This call waits until a new coherent set of frames is available on a device
            # Calls to get_frame_data(...) and get_frame_timestamp(...) on a device will return stable values until wait_for_frames(...) is called
            frames = pipeline.wait_for_frames()
            depth = frames.get_depth_frame()
            #npDepth = np.asarray(depth)  #can format here
            npDepth = np.empty([10, 10])
            #data = np.empty([depth.shape[0], depth.shape[1]])
            dataDepth = np.empty([480, 640])
            if not depth: continue

            for y in range(235,245,1):
                for x in range(315,325,1):
                    dist = depth.get_distance(x, y)
                    npDepth[x-315, y-235] = dist
                    print("%1.1f " % dist, end=" ")
                    print("%1.1f " % npDepth[x-315, y-235], end=" ")
                #print('\n\n')
            npDepth1 = npDepth.reshape(2,50).mean(0)
            npDepth2 = npDepth1.reshape(25,2).mean(1)
            npDepth3 = npDepth2.reshape(5,5)
            for yy in range(0,5,1):
                for xx in range(0,5,1):
                    #print("%1.1f " % npDepth3[xx, yy], end=" ")
                    #if (3.0 > npDepth3[xx, yy] and npDepth3[xx, yy] > 0.3):
                    if (1.0 > npDepth3[xx, yy]):
                        print("DRONE IN DANGER DRONE IN DANGER DRONE IN DANGER")
                        print("DRONE IN DANGER DRONE IN DANGER DRONE IN DANGER")
                        print("DRONE IN DANGER DRONE IN DANGER DRONE IN DANGER")
                        asys.tell(nav, DroneInDanger(True))
                    else :
                        asys.tell(nav, DroneInDanger(False))
                        continue
                        #print()
                print('\n\n')
        exit(0)
    #except rs.error as e:
    #    # Method calls agaisnt librealsense objects may throw exceptions of type pylibrs.error
    #    print("pylibrs.error was thrown when calling %s(%s):\n", % (e.get_failed_function(), e.get_failed_args()))
    #    print("    %s\n", e.what())
    #    exit(1)
    except Exception as e:
        print(e)
    pass
