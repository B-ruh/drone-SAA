# PixHawk manager actor and vehicle stuff

from thespian.actors import *
from messages import Initialize
import copy
from coactor import CoActor

class Pixhawk(CoActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # schedule init callback
        self.register_cb(Initialize, self.msg_init)

    async def msg_init(self, msg, sender):
        print("[PIX] Initializing!")
        self.init_data = copy.deepcopy(msg.data)
        # sleep a little while
        await self.sleep(3)
        print("[PIX] Done!")
        # unregister init callback
        self.unregister_cb(Initialize, self.msg_init)

            