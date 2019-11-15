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

import sys
import asyncio
import struct
from abc import ABC, abstractmethod

from .xdr import rpc_const, portmap_type, portmap_const
from .xdr.portmap_pack import PORTMAPPacker, PORTMAPUnpacker
from . import rpc_client

async def map(client, prog, vers, port):
    mapping = portmap_type.mapping(prog=prog, vers=vers, prot=portmap_const.IPPROTO_TCP, port=port)
    p = PORTMAPPacker()
    p.pack_mapping(mapping)
    rsp, msg = await client.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_SET, data = p.get_buffer())
    rsp = struct.unpack(">I",rsp)[0]
    if((msg.body.rbody.stat != rpc_const.MSG_ACCEPTED) or (msg.body.rbody.areply.reply_data.stat != rpc_const.SUCCESS)):
        raise Exception(f"Request to RPC portmapper map port {port} for prog {prog}.{vers} not supported: {msg}.")
    if(rsp == 0):
        raise Exception(f"Request to map port {port} for prog {prog}.{vers} failed.")
    print("Mapping done?")
    
async def getport(client, prog, vers):
    mapping = portmap_type.mapping(prog=prog, vers=vers, prot=portmap_const.IPPROTO_TCP, port=0)
    p = PORTMAPPacker()
    p.pack_mapping(mapping)
    rsp, msg = await client.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_GETPORT, data = p.get_buffer())
    if((msg.body.rbody.stat != rpc_const.MSG_ACCEPTED) or (msg.body.rbody.areply.reply_data.stat != rpc_const.SUCCESS)):
        raise Exception(f"Request to RPC portmapper to get port for prog {prog}.{vers} not supported: {msg}.")
    rsp = struct.unpack(">I",rsp)[0]
    print(f"rsp = {rsp}")
    return rsp

async def main():
    cl = rpc_client.rpc_client()
    
    #await cl.connect("127.0.0.1",portmap_const.PMAP_PORT)
    await cl.connect_unix(path="/var/run/rpcbind.sock")
    prog=9876
    ver=1
    mapping = portmap_type.mapping(prog=prog, vers=ver, prot=portmap_const.IPPROTO_TCP, port=5000)
    p = PORTMAPPacker()
    p.pack_mapping(mapping)
    rsp, _ = await cl.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_GETPORT, data = p.get_buffer())
    rsp, msg = await cl.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_SET, data = p.get_buffer())
    await cl.close()
    
if  __name__ == "__main__":
    asyncio.run(main())

