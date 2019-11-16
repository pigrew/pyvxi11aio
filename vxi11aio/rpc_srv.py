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

from abc import ABC, abstractmethod
from typing import Any, Type, Dict, Tuple, Callable, Optional, Awaitable, Coroutine
import asyncio
import functools
import struct
import sys
import xdrlib

from .xdr import rpc_const, rpc_type
from .xdr.rpc_pack import RPCPacker, RPCUnpacker

class rpc_conn(ABC):
    def __init__(self) -> None:
        super().__init__()
    
    callHandlerType = Callable[[Any,rpc_type.rpc_msg,bytes,int],Coroutine[Any,Any,Optional[bytes]]]
    
    # (prog, vers, proc) => bytes handler_func(self,rpc_msg, buf, buf_ix)
    call_dispatch_table: Dict[Tuple[int,int],Dict[int,callHandlerType]] = {}
    
    @staticmethod
    def callHandler(unpacker: Optional[Type[xdrlib.Unpacker]], unpack_func: Optional[Callable],
                    packer: Type[xdrlib.Packer], pack_func: Callable):
        """Decorator for RPC call handlers. This automates the packing and
        unpacking of handelers."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(self, rpc_msg: rpc_type.rpc_msg, buf: bytes, buf_ix: int) -> Optional[bytes]:
                if(unpacker is not None and unpack_func is not None):
                    arg_up = unpacker(buf)
                    arg_up.set_position(buf_ix)
                    arg = unpack_func(arg_up)
                    print(f"{func.__name__} >>> {arg}")
                else:
                    arg = None
                    print(f"{func.__name__} >>> (void)")
                rsp = await func(self, rpc_msg, arg)
                print(f"{func.__name__} <<< {arg}")
                p = packer()
                pack_func(p,rsp)
                return rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
            return wrapper
        return decorator
    
    async def handleMsg(self, rpc_msg: rpc_type.rpc_msg, buf, buf_ix: int) -> Optional[bytes]:
        if(rpc_msg.body.mtype != rpc_const.CALL):
            return None
        cbody = rpc_msg.body.cbody
        progHandlers = self.call_dispatch_table.get((cbody.prog,cbody.vers))
        if(progHandlers is None):
            print(f"RPC(prog={cbody.prog,cbody.vers}) not implemented")
            return rpc_srv.pack_reply_msg_unsupported(rpc_msg.xid,stat=rpc_const.PROG_UNAVAIL)
        
        handler = progHandlers.get(cbody.proc)
        #print(f"dispatcher = {handler}")
        if(handler is None):
            print(f"RPC(proc={cbody.proc}) not implemented")
            return rpc_srv.pack_reply_msg_unsupported(rpc_msg.xid,stat=rpc_const.PROC_UNAVAIL)
        return await handler(self,rpc_msg, buf, buf_ix)

class rpc_srv(ABC):
    def __init__(self, port) -> None:
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None
    
    @abstractmethod
    def create_conn(self) -> rpc_conn:
        pass
    
    async def HandleRPC(self,reader, writer) -> None:
        conn = self.create_conn()
        
        while True:
            frag_hdr_data = await reader.read(4)
            if(len(frag_hdr_data) != 4):
                break
            frag_len = struct.unpack(">I",frag_hdr_data)[0]
            if((frag_len & 0x80000000) == 0):
                raise Exception("Partial fragments not implemented")
            frag_len = frag_len & 0x7FFFFFFF
            data = await reader.read(frag_len)
            if(len(data) != frag_len):
                break
            msg_up = RPCUnpacker(data)
            msg = msg_up.unpack_rpc_msg()
            #pprint(msg)
            reply_data = await conn.handleMsg(msg,buf=data,buf_ix=msg_up.get_position())
            #print(f"rdata={reply_data}")
            if(reply_data is None):
                raise Exception("cannot handle message")
            writer.write(struct.pack(">I",0x80000000 | len(reply_data)))
            writer.write(reply_data)
        print(f"Closing socket")
        writer.close()
        if(sys.hexversion > 0x03070000):
            await writer.wait_closed()
        
    def pack_success_data_msg(xid,data) -> bytes:
        reply = rpc_type.rpc_msg(
            xid=xid,
            body=rpc_type.rpc_msg_body(
                    mtype=rpc_const.REPLY,
                    rbody=rpc_type.reply_body(
                        stat=rpc_const.MSG_ACCEPTED,
                        areply=rpc_type.accepted_reply(
                                verf=rpc_type.opaque_auth(flavor=rpc_const.AUTH_NONE,body=b''),
                                reply_data=rpc_type.rpc_reply_data(stat=rpc_const.SUCCESS,results=b'')
                                )
                        )
                    )
            )
        rpc_p = RPCPacker()
        rpc_p.pack_rpc_msg(reply)
        # The generated packing functions don't actually append the data to be packed.
        rpc_p.pack_fopaque(len(data),data)
        #print(f"rep_data={reply}")
        return rpc_p.get_buffer()             
        
    def pack_reply_msg_unsupported(xid, stat) -> bytes:
        """stat may be [rpc_const.PROG_UNAVAIL,rpc_const.PROC_UNAVAIL]"""
        reply = rpc_type.rpc_msg(
            xid=xid,
            body=rpc_type.rpc_msg_body(
                    mtype=rpc_const.REPLY,
                   rbody=rpc_type.reply_body(
                        stat=rpc_const.MSG_ACCEPTED,
                        areply=rpc_type.accepted_reply(
                                verf=rpc_type.opaque_auth(flavor=rpc_const.AUTH_NONE,body=b''),
                                reply_data=rpc_type.rpc_reply_data(stat=stat)
                                )
                        )
                    )
            )
        rpc_p = RPCPacker()
        rpc_p.pack_rpc_msg(reply)
        return rpc_p.get_buffer()
    
    async def open(self) -> None:
        self._server = await asyncio.start_server(
                self.HandleRPC, '127.0.0.1', self.port)
        if(self._server.sockets is None):
            raise Exception("Server did not open socket")
        addr = self._server.sockets[0].getsockname()
        print(f'Serving {self.__class__.__name__} on TCP {addr}')
        self.actual_port = self._server.sockets[0].getsockname()[1]
        
    async def main(self) -> None:
        if(self._server is None):
            await self.open()
        assert (self._server is not None)
        async with self._server:
            await self._server.serve_forever()
            
    async def close(self) -> None:
        assert (self._server is not None)
        print("Closing server")
        self._server.close()
        await self._server.wait_closed()
        self._server = None
    #def start(self):
    #    asyncio.run(self.main(), debug=True)
        