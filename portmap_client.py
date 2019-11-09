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

import xdr.rpc_const as rpc_const
import xdr.portmap_type as portmap_type
import xdr.portmap_const as portmap_const
from xdr.portmap_pack import PORTMAPPacker, PORTMAPUnpacker
import rpc_client


async def main():
    cl = rpc_client.rpc_client()
    
    await cl.connect("127.0.0.1",portmap_const.PMAP_PORT)
    mapping = portmap_type.mapping(prog=0x0607AF, vers=1, prot=portmap_const.IPPROTO_TCP, port=0)
    p = PORTMAPPacker()
    p.pack_mapping(mapping)
    rsp, _ = await cl.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_GETPORT, data = p.get_buffer())
    rsp, _ = await cl.call( portmap_const.PMAP_PROG, vers=portmap_const.PMAP_VERS,
                  proc=portmap_const.PMAPPROC_GETPORT, data = p.get_buffer())
    print(rsp)
    await cl.close()

asyncio.run(main())