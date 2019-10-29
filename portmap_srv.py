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

class portmapper:
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self):
        self.mapping = {}
    def handle(self,rpc_msg, buf, buf_ix):
        if(rpc_msg.body.mtype != rpc_const.CALL):
            return None
        cbody = rpc_msg.body.cbody
        if((cbody.prog != portmap_const.PMAP_PROG) or 
           (cbody.vers != portmap_const.PMAP_VERS)):
            return None
        if(cbody.proc == portmap_const.PMAPPROC_GETPORT):
            arg_up = PORTMAPUnpacker(buf)
            arg_up.set_position(buf_ix)
            arg = arg_up.unpack_mapping()
            print(f"mapping = {arg}")
            port = self.mapping[(arg.prog,arg.vers,arg.prot)]
            print(f"port is {port}, xid={rpc_msg.xid}")
            reply = rpc_type.rpc_msg(
                    xid=rpc_msg.xid,
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
            data = struct.pack(">I",port)
            rpc_p.pack_fopaque(len(data),data)
            #rpc_p.pack_rpc_reply_data(rpc_type.rpc_reply_data(stat=rpc_const.SUCCESS,results=struct.pack(">I",port)))
            print(f"rep_data={reply}")
            return rpc_p.get_buffer()
        else:
            raise Exception(f"portmap(proc={cbody.proc}) not implemented")
        return None


class portmap_srv:
    def __init__(self, program):
        self.program = program
    
    async def HandlePortmap(self,reader, writer):
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
            pprint(msg)
            reply_data = self.program.handle(msg,buf=data,buf_ix=msg_up.get_position())
            print(f"rdata={reply_data}")
            if(reply_data is None):
                raise Exception("cannot handle message")
            writer.write(struct.pack(">I",0x80000000 | len(reply_data)))
            writer.write(reply_data)
    async def main(self,port):
        server = await asyncio.start_server(
                self.HandlePortmap, '127.0.0.1', port)

        addr = server.sockets[0].getsockname()
        print(f'Serving portmap on {addr}')
    
        async with server:
            await server.serve_forever()
            
    def start(self):
        asyncio.run(self.main(), debug=True)

#async def gather_helper(g):
#    res = await g
#    return res

if  __name__ == "__main__":
    mapper = portmapper(port=111)
    mapper.mapping[(vx11_const.DEVICE_ASYNC,vx11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1025
    mapper.mapping[(vx11_const.DEVICE_CORE,vx11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1026
    mapper.mapping[(vx11_const.DEVICE_INTR,vx11_const.DEVICE_ASYNC_VERSION,portmap_const.IPPROTO_TCP)] = 1027
    pm_srv = portmap_srv(mapper)
    pm_task = asyncio.create_task(pm_srv.main())
    tasks = [pm_task]
    g = asyncio.gather(*tasks, return_exceptions=True)
    #pm_srv.start()
    asyncio.run(g)