This document covers the theory of operation for the drone-SAA program.

## Framework
The program makes heavy use of two concurrent programming concepts: Actors and Coroutines. These enable the main program logic to be simplified and the program to perform well, even across multiple machines.

On receipt of a message (an arbitrary Python object), an Actor can:
* send a message to another actor: `self.send(actor_addr, obj)`
* create another actor: `self.createActor('actor.Class')`
* modify internal state: `self.something = "whatever"`

A coroutine in Python is a function prefixed with `async def` instead of simply `def`. As the name suggests, the coroutine runs asynchronously. You must use `await` to run the coroutine and get the result. The `CoActor` class models a coroutine event loop in the actor system. The benefit of the coroutine system is that no locks or other synchronization objects are required.

You can use the event loop to:
* sleep for some seconds: `await self.sleep(seconds)`
* wait for a specific message: `await self.wait_msg(MsgType)`
* call a function or coroutine in parallel: `self.call_soon(fn)`

## Navigation
The Navigation actor (in nav.py) is where all the exciting stuff happens. The main loop is in the `nav()` function. It interacts with the drone via a VehicleProxy object `self.vehicle`. It acts on drone attributes via the various `self.vehicle.wait_` coroutines and changes the drone state with other functions of `self.vehicle`. When it receives a DroneInDanger message from the sensor engine, `self.msg_in_danger` is called which alerts the main loop waiting for there to be danger with `self.wait_for_danger`.

## Pixhawk
The Pixhawk actor manages the VehicleProxy and multiplexing access to the Pixhawk hardware. The VehicleProxy class can be instantiated by any actor and behind the scenes it sends and receives messages from Pixhawk to communicate attribute updates and vehicle actions. The VehicleProxy is intended to be a close mirror of Dronekit's vehicle.

Note that while many actors can read from the VehicleProxy, you must be aware of race conditions if multiple actors write to it!

## Dronekit
The Dronekit library is used as the underlying Pixhawk communicator. It sits in a separate thread and sends Pixhawk all drone attribute updates and receives directions on how to encode messages to send to the hardware.