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

import xdr.rpc_const as rpc_const, xdr.rpc_type as rpc_type
from xdr.rpc_pack import RPCPacker, RPCUnpacker

class rpc_client():
    # Don't connect in the constructor, since it should be asynchronous!
    def __init__(self):
        self._xid = 100
    
    async def connect(self, host, port):
        print(f"Opening RPC client connection to {host}:{port}")
        self._reader, self._writer = await asyncio.open_connection(
                host, port)
    
    async def connect_unix(self, path):
        print(f"Opening UNIX RPC connection to {path}")
        self._reader, self._writer = await asyncio.open_unix_connection(
            path=path)
        
    async def close(self):
        self._writer.close()
        if(sys.hexversion > 0x03070000):
            await self._writer.wait_closed()
        self._writer = None
        self._reader = None
        
    async def call(self, prognum, vers, proc, data: bytes):
        cbody = rpc_type.call_body(
                rpcvers=2,
                prog=prognum,
                vers=vers,
                proc=proc,
                cred=rpc_type.opaque_auth(flavor=rpc_const.AUTH_NONE,body=b''),
                verf=rpc_type.opaque_auth(flavor=rpc_const.AUTH_NONE,body=b'')
                )
        msg = rpc_type.rpc_msg(
                xid=self._xid,
                body=rpc_type.rpc_msg_body(
                        rpc_const.CALL,
                        cbody=cbody))
        self._xid = (self._xid + 1) % 0x10000
        
        p =  RPCPacker()
        p.pack_rpc_msg(msg)
        b_call = p.get_buffer()
        frag_len = len(b_call) + len(data)
        b_len = struct.pack(">I",0x80000000 | frag_len)
        self._writer.write(b_len + b_call + data)
        await self._writer.drain()
        
        frag_hdr_data = await self._reader.read(4)
        if(len(frag_hdr_data) != 4):
            raise Exception("client closed connection???")
        frag_len = struct.unpack(">I",frag_hdr_data)[0]
        if((frag_len & 0x80000000) == 0):
            raise Exception("Partial fragments not implemented")
        frag_len = frag_len & 0x7FFFFFFF
        data = await self._reader.read(frag_len)
        if(len(data) != frag_len):
            raise Exception("Data not as expected")
        msg_up = RPCUnpacker(data)
        msg = msg_up.unpack_rpc_msg()
        #reply_data = await conn.handleMsg(msg,buf=data,buf_ix=msg_up.get_position())
        
        return (data[msg_up.get_position():], msg)
    
