#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Connect to TCPIP0::127.0.0.1::INSTR

import asyncio
from enum import Enum
import struct
from pprint import pprint
from abc import ABC, abstractmethod, abstractproperty

import rpc_const, rpc_type
from rpc_pack import RPCPacker, RPCUnpacker

class rpc_conn(ABC):
    def __init__(self):
        super().__init__()
        
    # (prog, vers, proc) => bytes handler_func(self,rpc_msg, buf, buf_ix)
    call_dispatch_table = None
    
    def handleMsg(self,rpc_msg, buf, buf_ix):
        if(rpc_msg.body.mtype != rpc_const.CALL):
            return None
        cbody = rpc_msg.body.cbody
        handler = self.call_dispatch_table.get((cbody.prog,cbody.vers,cbody.proc))
        #print(f"dispatcher = {handler}")
        if(handler is None):
            raise Exception(f"RPC(proc={cbody.proc}) not implemented")
        return handler(self,rpc_msg, buf, buf_ix)

class rpc_srv(ABC):
    def __init__(self, port):
        self.port = port
    
    @abstractmethod
    def create_conn(self):
        pass
    
    async def HandleRPC(self,reader, writer):
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
            reply_data = conn.handleMsg(msg,buf=data,buf_ix=msg_up.get_position())
            #print(f"rdata={reply_data}")
            if(reply_data is None):
                raise Exception("cannot handle message")
            writer.write(struct.pack(">I",0x80000000 | len(reply_data)))
            writer.write(reply_data)
    
    def pack_success_data_msg(xid,data):
        reply = rpc_type.rpc_msg(
            xid=xid,
            body=rpc_type.rpc_msg_body(
                    mtype=rpc_const.REPLY,
                    rbody=rpc_type.reply_body(
                        stat=rpc_const.SUCCESS,
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
        
    async def main(self):
        server = await asyncio.start_server(
                self.HandleRPC, '127.0.0.1', self.port)
        print(server.sockets[0])
        addr = server.sockets[0].getsockname()
        print(f'Serving portmap on {addr}')
        self.actual_port = server.sockets[0].getsockname()[1]
        async with server:
            await server.serve_forever()
        
    def start(self):
        asyncio.run(self.main(), debug=True)
