#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019 Nathan J. Conrad

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.

# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


# Connect to TCPIP0::127.0.0.1::inst0::INSTR

# The following prorities are used when searching for the local portmapper:

# 1. Attempt to use UNIX socket /var/run/rpcbind.sock
# 2. Attempt to connect to 127.0.0.1:111
# 3. Attempt to create our own static portmapper

import sys
import asyncio
import os
from typing import Type

from vxi11aio import vxi11_srv, adapter_time, portmap_srv, rpc_client, portmap_client

from vxi11aio.xdr import vxi11_const, portmap_const

async def main() -> None:
    
    vxi11_core_srv = vxi11_srv.vxi11_core_srv(port=0,adapters=[adapter_time.adapter()])
    vxi11_async_srv = vxi11_srv.vxi11_async_srv(port=0)
    
    # Open sockets so that we can get the actual port numbers
    await asyncio.gather(vxi11_core_srv.open(),vxi11_async_srv.open())
    
    cl = None
    if (os.path.exists(b"/var/run/rpcbind.sock")):
        cl = rpc_client.rpc_client()
        await cl.connect_unix(path="/var/run/rpcbind.sock")
    else:
        try:
            cl = rpc_client.rpc_client()
            await cl.connect(host="127.0.0.1",port=111)
        except ConnectionRefusedError:
            print("Could not connect to portmapper.... attempting to start our own")
            cl = None
    tasks = [asyncio.create_task(vxi11_core_srv.main()),
             asyncio.create_task(vxi11_async_srv.main()),
             ]   
    if (cl is not None):
        print("Requesting RPC mapping")
        await portmap_client.map(cl,vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, port = vxi11_core_srv.actual_port)
        await portmap_client.map(cl,vxi11_const.DEVICE_ASYNC,vxi11_const.DEVICE_ASYNC_VERSION, port = vxi11_async_srv.actual_port)
        await cl.close()
    else:
        print("Starting static portmapper")
        mapper = portmap_srv.portmapper()
        # although spec only specifies that core channel needs to be mapped, KeySight IO libraries want both mapped
        mapper.mapping[(vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION,
                        portmap_const.IPPROTO_TCP)] = vxi11_core_srv.actual_port
        mapper.mapping[(vxi11_const.DEVICE_ASYNC,vxi11_const.DEVICE_ASYNC_VERSION,
                        portmap_const.IPPROTO_TCP)] = vxi11_async_srv.actual_port
        
        pm_srv = portmap_srv.portmap_srv(mapper=mapper,port=111)
        pm_task = asyncio.create_task(pm_srv.main())
        tasks = tasks + [pm_task]
    vxi11_core_srv.abort_port = vxi11_async_srv.actual_port
    await asyncio.gather(*tasks, return_exceptions=True)
    
if  __name__ == "__main__":
    if(sys.hexversion >= 0x03070000):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        # Blocking call which returns when the hello_world() coroutine is done
        loop.run_until_complete(main())
        loop.close()
    
    
