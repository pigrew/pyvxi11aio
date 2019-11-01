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
import enum
import struct

import rpc_srv

import vxi11_const, vxi11_type
from vxi11_pack import VXI11Packer, VXI11Unpacker

class vxi11_errorCodes(enum.IntEnum):
    NO_ERROR = 0
    SYNTAX_ERROR = 1
    DEVICE_NOT_ACCESSIBLE = 3
    INVALID_LINK_IDENTIFIER = 4
    PARAMETER_ERROR = 5
    CHANNEL_NOT_ESTABLED = 6
    OPERATION_NOT_SUPPORTED = 8
    OUT_OF_RESOURCES = 9
    DEVICE_LOCKED_OUT_BY_ANOTHER_LINK = 11
    NO_LOCK_HELD_BY_THIS_LINK = 12
    IO_TIMEOUT = 15
    IO_ERROR = 17
    INVALID_ADDRESS = 21
    ABORT = 23
    CHANNEL_ALREADY_ESTABLISHED = 29

class vxi11_deviceFlags(enum.IntFlag):
    WAITLOCK   = 0x01
    END        = 0x08
    TERMCHRSET = 0x80

class vxi11_readReason(enum.IntFlag):
    REQCNT   = 0x01
    CHR      = 0x02
    END      = 0x84

class vxi11_core_conn(rpc_srv.rpc_conn):
    def __init__(self,srv):
        self.links = dict()
        self.srv = srv
        super().__init__()
        
    async def handle_create_link(self,rpc_msg, buf, buf_ix):
        """ Create_LinkResp    create_link        (Create_LinkParms)      = 10; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Create_LinkParms()
        print(f"create_link >>> {arg}")
        lid = self.srv.next_link_id
        self.srv.next_link_id = self.srv.next_link_id + 1
        (err,link) = await self.srv.adapters[0].create_link(clientId = arg.clientId, lockDevice = arg.lockDevice,
                             lock_timeout = arg.lock_timeout, device = arg.device, link_id = lid)
        
        self.links[lid] = link
        rsp = vxi11_type.Create_LinkResp(
                error=err, lid=lid,
                abortPort=struct.pack(">H",1026),maxRecvSize=1024) # min maxRecvSize is 1024 per spec
        print(f"            <<< {rsp}")
        p = VXI11Packer()
        p.pack_Create_LinkResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_device_write(self,rpc_msg, buf, buf_ix):
        """Device_WriteResp   device_write       (Device_WriteParms)     = 11; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_WriteParms()
        print(f"device_write >>> {arg} (flags={vxi11_errorCodes(arg.flags)})")
        link = self.links[arg.lid]
        (err,size) = await link.write(io_timeout = arg.io_timeout,
            lock_timeout = arg.lock_timeout, flags = arg.flags, data = arg.data)
        
        rsp = vxi11_type.Device_WriteResp(error=err, size=size)
        
        print(f"device_write <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_WriteResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
        
    async def handle_device_read(self,rpc_msg, buf, buf_ix):
        """Device_ReadResp    device_read        (Device_ReadParms)      = 12; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_ReadParms()
        print(f"device_read >>> {arg} (flags={vxi11_errorCodes(arg.flags)})")
        link = self.links.get(arg.lid)
        if (link is not None):
            (err,reason,data) = await link.read(requestSize = arg.requestSize,
                io_timeout = arg.io_timeout, lock_timeout = arg.lock_timeout,
                flags = arg.flags, termChar = arg.termChar)
        else:
            (err,reason,data) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,0,b'')
        rsp = vxi11_type.Device_ReadResp(error=err, reason=reason, data=data)
        print(f"device_read <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_ReadResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
        
    async def handle_device_readstb(self,rpc_msg, buf, buf_ix):
        """Device_ReadStbResp device_readstb     (Device_GenericParms)   = 13;"""
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_readstb >>> {arg}")
        link = self.links.get(arg.lid)
        if (link is not None):
            (err,stb) = await link.read_stb(flags = arg.flags,lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            (err,stb) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,0)
        rsp = vxi11_type.Device_ReadStbResp(error=err, stb=stb)#stb=struct.pack('>B',0x42))
        print(f"device_readstb <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_ReadStbResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_device_trigger(self,rpc_msg, buf, buf_ix):
        """Device_Error       device_trigger     (Device_GenericParms)   = 14; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_trigger >>> {arg}")
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.trigger(flags = arg.flags,lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error(error=err)
        print(f"device_trigger <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_device_clear(self,rpc_msg, buf, buf_ix):
        """Device_Error       device_clear       (Device_GenericParms)   = 15; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_clear >>> {arg}")
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.clear(flags = arg.flags,lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"device_clear <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_device_remote(self,rpc_msg, buf, buf_ix):
        """Device_Error       device_remote      (Device_GenericParms)   = 16; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_remote >>> {arg}")
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.clear(flags = arg.flags,lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"device_remote <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_device_local(self,rpc_msg, buf, buf_ix):
        """Device_Error       device_local       (Device_GenericParms)   = 17;"""
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_local >>> {arg}")
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.local(flags = arg.flags,lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"device_local <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_destroy_link(self,rpc_msg, buf, buf_ix):
        """Device_Error       destroy_link       (Device_Link)           = 23; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_Link()
        print(f"destroy_link >>> {arg}")
        link = self.links.get(arg)
        if (link is not None):
            err = await link.destroy()
            del self.links[arg]
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error( error=err)
        print(f"destroy_link <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_create_intr_chan(self,rpc_msg, buf, buf_ix):
        """Device_Error       create_intr_chan   (Device_RemoteFunc)     = 25;"""
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_RemoteFunc()
        print(f"create_intr_chan >>> {arg}")
        err = vxi11_errorCodes.OPERATION_NOT_SUPPORTED # This isn't implemented.... (used for SRQ)
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"create_intr_chan <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    async def handle_destroy_intr_chan(self,rpc_msg, buf, buf_ix):
        """Device_Error       destroy_intr_chan  (void)                  = 26;"""
        print(f"destroy_intr_chan >>> {arg}")
        err = vxi11_errorCodes.CHANNEL_NOT_ESTABLED
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"destroy_intr_chan <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    # (prog, vers, proc) => func(self,rpc_msg, buf, buf_ix)
    """
    Device_Error       device_lock        (Device_LockParms)      = 18; 
    Device_Error       device_unlock      (Device_Link)           = 19; 
    Device_Error       device_enable_srq  (Device_EnableSrqParms) = 20; 
    Device_DocmdResp   device_docmd       (Device_DocmdParms)     = 22; 
    """
    
    call_dispatch_table = {
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.create_link): handle_create_link, # 10
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_write): handle_device_write, # 11
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_read): handle_device_read, # 12
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_readstb): handle_device_readstb, # 13
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_trigger): handle_device_trigger, # 14
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_clear): handle_device_clear, # 15
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_remote): handle_device_remote, # 16
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_local): handle_device_local, # 17
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.destroy_link): handle_destroy_link, # 23
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.create_intr_chan): handle_create_intr_chan, # 25
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.destroy_intr_chan): handle_destroy_intr_chan, # 26
    }
class vxi11_abort_conn(rpc_srv.rpc_conn):
    def __init__(self,srv):
        self.links = dict()
        self.srv = srv
        super().__init__()
        
    async def handle_device_abort(self,rpc_msg, buf, buf_ix):
        """Device_Error device_abort (Device_Link) = 1;"""
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_Link()
        print(f"device_local >>> {arg}")
        link = self.links.get(arg)
        if (link is not None):
            err = vxi11_errorCodes.NO_ERROR # We don't really do it, but this is kinda following the spec
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        print(f"device_local <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    call_dispatch_table = {
            (vxi11_const.DEVICE_ASYNC,vxi11_const.DEVICE_ASYNC_VERSION, vxi11_const.device_abort): handle_device_abort
            }

class vxi11_core_srv(rpc_srv.rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port,adapters):
        self.adapters = adapters
        self.next_link_id = 0
        super().__init__(port)
    
    def create_conn(self):
        return vxi11_core_conn(self)

class vxi11_async_srv(rpc_srv.rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port,adapters):
        self.adapters = adapters
        self.next_link_id = 0
        super().__init__(port)
    
    def create_conn(self):
        return vxi11_async_conn(self)
