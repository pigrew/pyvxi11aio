#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Connect to TCPIP0::127.0.0.1::INSTR

import asyncio
from enum import Enum
import struct
from pprint import pprint

import portmap_const, portmap_type
from portmap_pack import PORTMAPPacker, PORTMAPUnpacker

import rpc_const, rpc_type
from rpc_pack import RPCPacker, RPCUnpacker

import vx11_const

import rpc_srv
import vx11_srv

class portmapper():
    def __init__(self):
        self.mapping = {}

class portmap_conn(rpc_srv.rpc_conn):
    def __init__(self, mapper):
        self.mapper = mapper
        super().__init__()
    def handle_getPort(self,rpc_msg, buf, buf_ix):
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
    
    vxi11_core_srv = vx11_srv.vx11_srv(port=1025)
    vxi11_async_srv = vx11_srv.vx11_srv(port=1026)
    #dev_srv3 = vx11_srv.vx11_srv(port=1027)
    
    mapper = portmapper()
    mapper.mapping[(vx11_const.DEVICE_ASYNC,vx11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1025
    mapper.mapping[(vx11_const.DEVICE_CORE,vx11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1026
    
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