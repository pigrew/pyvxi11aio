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
from typing import Any, Dict, List, Optional
from .rpc_srv import rpc_conn, rpc_srv

from .xdr import vxi11_const, vxi11_type, rpc_type
from .xdr.vxi11_pack import VXI11Packer, VXI11Unpacker

from .rpc_client import rpc_client

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

class vxi11_intr_client(rpc_client):
    async def device_intr_srq(self, handle: bytes) -> None:
        """void device_intr_srq (Device_SrqParms) = 30;"""
        args = vxi11_type.Device_SrqParms(handle=handle)
        p = VXI11Packer()
        p.pack_Device_SrqParms(args)
        rsp, msg = await self.call(vxi11_const.DEVICE_INTR, vers=vxi11_const.DEVICE_INTR_VERSION,
                  proc=vxi11_const.device_intr_srq, data = p.get_buffer(), read_reply = False)
        print("SRQ sent!")

# Handles the connection, and queueing interupt requests
class vxi11_intr_executor():
    def __init__(self) -> None:
        self._intr_client: Optional[vxi11_intr_client] = None
        self._intr_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._task: Optional[asyncio.Task[Any]] = None
        pass
    
    def send_irq(self,handle: bytes) -> None:
        if(self._intr_client is not None):
            self._intr_queue.put_nowait(handle)
    
    async def connect(self, host: str, port: int) -> None:
        self._intr_client = vxi11_intr_client()
        await self._intr_client.connect(host, port)
        
    async def disconnect(self) -> None:
        assert (self._intr_client is not None)
        await self._intr_client.close()
        self._intr_client = None
        
    async def _main(self) -> None:
        try:
            while True:
                el = await self._intr_queue.get()
                print("Get SRQ to send to {}")
                if(self._intr_client is not None):
                    await self._intr_client.device_intr_srq(el)
                self._intr_queue.task_done()
        except asyncio.CancelledError:
            raise
            
    def start(self) -> None:
        self._task = asyncio.create_task(self._main())
    
    async def stop(self) -> None:
        assert( self._task is not None)
        if(self._intr_client != None):
            await self.disconnect()
        
        try:
            self._task.cancel()
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        
    
class vxi11_core_conn(rpc_conn):
    def __init__(self,srv: 'vxi11_core_srv') -> None:
        self.links: Dict[int,'vxi11_adapter.vxi11_link'] = dict()
        self.srv = srv
        self._intr_exec: Optional[vxi11_intr_executor] = None
        super().__init__()
        
    @rpc_conn.callHandler(
            VXI11Unpacker,VXI11Unpacker.unpack_Create_LinkParms,
            VXI11Packer,VXI11Packer.pack_Create_LinkResp)
    async def handle_create_link(self,rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Create_LinkParms) -> vxi11_type.Create_LinkResp:
        """ Create_LinkResp    create_link        (Create_LinkParms)      = 10; """
        lid = self.srv.next_link_id
        self.srv.next_link_id = self.srv.next_link_id + 1
        (err,link) = await self.srv.adapters[0].create_link(clientId = arg.clientId, lockDevice = arg.lockDevice,
                             lock_timeout = arg.lock_timeout, device = arg.device, link_id = lid, conn = self)
        self.links[lid] = link
        rsp = vxi11_type.Create_LinkResp(
                error=err, lid=lid,
                abortPort=self.srv.abort_port,maxRecvSize=1024) # min maxRecvSize is 1024 per spec
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_WriteParms,
        VXI11Packer,VXI11Packer.pack_Device_WriteResp)
    async def handle_device_write(self, rpc_msg: rpc_type.rpc_msg,
                                  arg: vxi11_type.Device_WriteParms) -> vxi11_type.Device_WriteResp:
        """Device_WriteResp   device_write       (Device_WriteParms)     = 11; """
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links[arg.lid]
        if (link is not None):
            (err,size) = await link.write(io_timeout = arg.io_timeout,
                lock_timeout = arg.lock_timeout, flags = vxi11_deviceFlags(arg.flags), data = arg.data)
        else:
            (err, size) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,0)
        rsp = vxi11_type.Device_WriteResp(error=err, size=size)
        return rsp
        
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_ReadParms,
        VXI11Packer,VXI11Packer.pack_Device_ReadResp)
    async def handle_device_read(self, rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_ReadParms) -> vxi11_type.Device_ReadResp:
        """Device_ReadResp    device_read        (Device_ReadParms)      = 12; """
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            (err,reason,data) = await link.read(requestSize = arg.requestSize,
                io_timeout = arg.io_timeout, lock_timeout = arg.lock_timeout,
                flags = vxi11_deviceFlags(arg.flags), termChar = arg.termChar)
        else:
            (err,reason,data) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,0,b'')
        rsp = vxi11_type.Device_ReadResp(error=err, reason=reason, data=data)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_GenericParms,
        VXI11Packer,VXI11Packer.pack_Device_ReadStbResp)
    async def handle_device_readstb(self,rpc_msg: rpc_type.rpc_msg,
                                    arg: vxi11_type.Device_GenericParms) -> vxi11_type.Device_ReadStbResp:
        """Device_ReadStbResp device_readstb     (Device_GenericParms)   = 13;"""
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            (err,stb) = await link.read_stb(flags = vxi11_deviceFlags(arg.flags),lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            (err,stb) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,0)
        rsp = vxi11_type.Device_ReadStbResp(error=err, stb=stb)#stb=struct.pack('>B',0x42))
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_GenericParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_trigger(self,rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_GenericParms) -> vxi11_type.Device_Error:
        """Device_Error       device_trigger     (Device_GenericParms)   = 14; """
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.trigger(flags = vxi11_deviceFlags(arg.flags),lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_GenericParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_clear(self,rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_GenericParms) -> vxi11_type.Device_Error:
        """Device_Error       device_clear       (Device_GenericParms)   = 15; """
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.clear(flags = vxi11_deviceFlags(arg.flags),lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_GenericParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_remote(self, rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_GenericParms) -> vxi11_type.Device_Error:
        """Device_Error       device_remote      (Device_GenericParms)   = 16; """
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.clear(flags = vxi11_deviceFlags(arg.flags),lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_GenericParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_local(self, rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_GenericParms) -> vxi11_type.Device_Error:
        """Device_Error       device_local       (Device_GenericParms)   = 17;"""
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.local(flags = vxi11_deviceFlags(arg.flags),lock_timeout = arg.lock_timeout,
                io_timeout = arg.io_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_LockParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_lock(self, rpc_msg: rpc_type.rpc_msg, arg: vxi11_type.Device_LockParms) -> vxi11_type.Device_Error:
        """Device_Error       device_lock        (Device_LockParms)      = 18;"""
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            err = await link.device_lock(flags=vxi11_deviceFlags(arg.flags), lock_timeout=arg.lock_timeout)
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_Link,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_unlock(self,rpc_msg: rpc_type.rpc_msg, arg: int) -> vxi11_type.Device_Error:
        """Device_Error       device_unlock      (Device_Link)           = 19;"""
        link = self.links.get(arg)
        if (link is not None):
            err = await link.device_unlock()
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error( error=err)
        return rsp
    
    def send_srq(self, handle: bytes) -> None:
        if(self._intr_exec is not None):
             self._intr_exec.send_irq(handle)
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_EnableSrqParms,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_enable_srq(self,rpc_msg: rpc_type.rpc_msg,
                                       arg: vxi11_type.Device_EnableSrqParms) -> vxi11_type.Device_Error:
        """Device_Error       device_enable_srq  (Device_EnableSrqParms) = 20;"""
        assert(arg.lid is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            if(arg.enable):
                link.srq_handle = arg.handle
            else:
                link.srq_handle = None
            err = vxi11_errorCodes.NO_ERROR
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_DocmdParms,
        VXI11Packer,VXI11Packer.pack_Device_DocmdResp)
    async def handle_device_docmd(self,rpc_msg: rpc_type.rpc_msg,
                                  arg: vxi11_type.Device_DocmdParms)  -> vxi11_type.Device_DocmdResp:
        """Device_DocmdResp   device_docmd       (Device_DocmdParms)     = 22;"""
        assert(arg.lid is not None)
        assert(arg.flags is not None)
        link = self.links.get(arg.lid)
        if (link is not None):
            (err,data_out) = await link.docmd(flags = vxi11_deviceFlags(arg.flags),
                io_timeout = arg.io_timeout, lock_timeout = arg.lock_timeout,
                cmd = arg.cmd, network_order = arg.network_order, datasize=arg.datasize,
                data_in = arg.data_in)
        else:
            (err,data_out) = (vxi11_errorCodes.INVALID_LINK_IDENTIFIER,b'')
        rsp = vxi11_type.Device_DocmdResp(error=err, data_out=data_out)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_Link,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_destroy_link(self,rpc_msg: rpc_type.rpc_msg, arg: int) -> vxi11_type.Device_Error:
        """Device_Error       destroy_link       (Device_Link)           = 23; """
        link = self.links.get(arg)
        if (link is not None):
            # Remove link prior to destroying it, to ensure another connection
            # doesn't use the link in the meanwhile
            del self.links[arg]
            err = await link.destroy()
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        rsp = vxi11_type.Device_Error( error=err)
        return rsp
    
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_RemoteFunc,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_create_intr_chan(self, rpc_msg: rpc_type.rpc_msg,
                                      arg: vxi11_type.Device_RemoteFunc) -> vxi11_type.Device_Error:
        """Device_Error       create_intr_chan   (Device_RemoteFunc)     = 25;"""
        assert(arg.hostAddr is not None)
        assert(arg.hostPort is not None)
        if((arg.progNum != vxi11_const.DEVICE_INTR) or (arg.progVers != vxi11_const.DEVICE_INTR_VERSION)):
            err = vxi11_errorCodes.OPERATION_NOT_SUPPORTED
        elif ((arg.progFamily != vxi11_const.DEVICE_TCP)):
            err = vxi11_errorCodes.OPERATION_NOT_SUPPORTED # UDP support is optional
        elif (self._intr_exec is not None):
            err = vxi11_errorCodes.CHANNEL_ALREADY_ESTABLISHED
        else:
            self._intr_exec = vxi11_intr_executor()
            addr = f"{(arg.hostAddr>>24)&0xff}.{(arg.hostAddr>>16)&0xff}.{(arg.hostAddr>>8)&0xff}.{(arg.hostAddr)&0xff}"
            await self._intr_exec.connect(addr,arg.hostPort)
            self._intr_exec.start()
            err = vxi11_errorCodes.NO_ERROR
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    @rpc_conn.callHandler(
        None,None,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_destroy_intr_chan(self,rpc_msg: rpc_type.rpc_msg, arg: None) -> vxi11_type.Device_Error:
        """Device_Error       destroy_intr_chan  (void)                  = 26;"""
        print(f"destroy_intr_chan >>> (void)")
        if(self._intr_exec is None):
            err = vxi11_errorCodes.CHANNEL_NOT_ESTABLED
        else:
            await self._intr_exec.stop()
            self._intr_exec = None
            err = vxi11_errorCodes.NO_ERROR
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    # (prog, vers, proc) => func(self,rpc_msg, buf, buf_ix)
    
    call_dispatch_table = {
        (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION): {
            vxi11_const.create_link: handle_create_link, # 10
            vxi11_const.device_write: handle_device_write, # 11
            vxi11_const.device_read: handle_device_read, # 12
            vxi11_const.device_readstb: handle_device_readstb, # 13
            vxi11_const.device_trigger: handle_device_trigger, # 14
            vxi11_const.device_clear: handle_device_clear, # 15
            vxi11_const.device_remote: handle_device_remote, # 16
            vxi11_const.device_local: handle_device_local, # 17
            vxi11_const.device_lock: handle_device_lock, # 18
            vxi11_const.device_unlock: handle_device_unlock, # 19
            vxi11_const.device_enable_srq: handle_device_enable_srq, # 20
            vxi11_const.device_docmd: handle_device_docmd, # 22
            vxi11_const.destroy_link: handle_destroy_link, # 23
            vxi11_const.create_intr_chan: handle_create_intr_chan, # 25
            vxi11_const.destroy_intr_chan: handle_destroy_intr_chan, # 26
        }
    }

class vxi11_abort_conn(rpc_conn):
    def __init__(self,srv: 'vxi11_async_srv') -> None:
        print("Opening abort connection")
        self.links: Dict[int,Any] = dict()
        self.srv = srv
        super().__init__()
        
    @rpc_conn.callHandler(
        VXI11Unpacker,VXI11Unpacker.unpack_Device_Link,
        VXI11Packer,VXI11Packer.pack_Device_Error)
    async def handle_device_abort(self,rpc_msg: rpc_type.rpc_msg, arg: int) -> vxi11_type.Device_Error:
        """Device_Error device_abort (Device_Link) = 1;"""
        link = self.links.get(arg)
        if (link is not None):
            err = vxi11_errorCodes.NO_ERROR # We don't really do it, but this is kinda following the spec
        else:
            err = vxi11_errorCodes.INVALID_LINK_IDENTIFIER
        
        rsp = vxi11_type.Device_Error(error=err)
        return rsp
    
    call_dispatch_table = {
            (vxi11_const.DEVICE_ASYNC,vxi11_const.DEVICE_ASYNC_VERSION): {
                    vxi11_const.device_abort: handle_device_abort
            }
        }

class vxi11_core_srv(rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port: int,adapters: List['vxi11_adapter']) -> None:
        self.adapters = adapters
        self.next_link_id = 0
        self.abort_port = None
        #self.intrQueue = asyncio.queue
        super().__init__(port)
    
    def create_conn(self) -> vxi11_core_conn:
        return vxi11_core_conn(self)

class vxi11_async_srv(rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port: int) -> None:
        super().__init__(port)
    
    def create_conn(self) -> vxi11_abort_conn:
        return vxi11_abort_conn(self)
