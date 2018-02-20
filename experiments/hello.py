from thespian.actors import *
import os
print(os.getpid())

class Hello(Actor):
    def receiveMessage(self, message, sender):
        self.send(sender, "Hello, world!")

if __name__ == "__main__":
    sys = ActorSystem("multiprocQueueBase", transientUnique=True)
    hello = sys.createActor('hello.Hello')
    print(sys.ask(hello, 'hi', 1))
    sys.tell(hello, ActorExitRequest())
    sys.shutdown()