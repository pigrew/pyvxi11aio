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


# Connect to TCPIP0::127.0.0.1::INSTR

import asyncio
from enum import Enum
import struct
from pprint import pprint

import portmap_const, portmap_type
from portmap_pack import PORTMAPPacker, PORTMAPUnpacker

import rpc_const, rpc_type
from rpc_pack import RPCPacker, RPCUnpacker

import vxi11_const

import rpc_srv
import vxi11_srv
import adapter_time

class portmapper():
    def __init__(self):
        self.mapping = {}

class portmap_conn(rpc_srv.rpc_conn):
    def __init__(self, mapper):
        self.mapper = mapper
        super().__init__()
    async def handle_getPort(self,rpc_msg, buf, buf_ix):
        arg_up = PORTMAPUnpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_mapping()
        print(f"mapping = {arg}")
        port = self.mapper.mapping[(arg.prog,arg.vers,arg.prot)]
        print(f"port is {port}, xid={rpc_msg.xid}")

        data = struct.pack(">I",port)
        data = rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,data)
        return data
    # (prog, vers, proc) => func(self,rpc_msg, buf, buf_ix)

    call_dispatch_table = {
            (portmap_const.PMAP_PROG,portmap_const.PMAP_VERS, portmap_const.PMAPPROC_GETPORT): handle_getPort
    }
    
class portmap_srv(rpc_srv.rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port,mapper):
        self.mapper = mapper
        super().__init__(port)
        
    def create_conn(self):
        return portmap_conn(self.mapper)

#async def gather_helper(g):
#    res = await g
#    return res
async def main():
    
    vxi11_core_srv = vxi11_srv.vxi11_core_srv(port=1025,adapters=[adapter_time.adapter()])
    vxi11_async_srv = vxi11_srv.vxi11_async_srv(port=1026,adapters=[])
    
    mapper = portmapper()
    # Only core channel needs to be mapped
    mapper.mapping[(vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1025
    
    pm_srv = portmap_srv(mapper=mapper,port=111)
    pm_task = asyncio.create_task(pm_srv.main())
    
    tasks = [pm_task,
             asyncio.create_task(vxi11_core_srv.main()),
             asyncio.create_task(vxi11_async_srv.main()),
             ]
    await asyncio.gather(*tasks, return_exceptions=True)
    
if  __name__ == "__main__":
    #pm_srv.start()
    asyncio.run(main())