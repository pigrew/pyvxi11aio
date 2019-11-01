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
from pprint import pprint

import rpc_const, rpc_type
from rpc_pack import RPCPacker, RPCUnpacker

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

class vxi11_conn(rpc_srv.rpc_conn):
    def __init__(self,srv):
        self.links = []
        self.srv = srv
        super().__init__()
        
    def handle_create_link(self,rpc_msg, buf, buf_ix):
        """ Create_LinkResp    create_link        (Create_LinkParms)      = 10; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Create_LinkParms()
        print(f"create_link >>> {arg}")
        rsp = vxi11_type.Create_LinkResp(
                error=vxi11_errorCodes.NO_ERROR.value, lid=1,
                abortPort=struct.pack(">H",self.srv.actual_port),maxRecvSize=1024) # min maxRecvSize is 1024 per spec
        print(f"            <<< {rsp}")
        p = VXI11Packer()
        p.pack_Create_LinkResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    def handle_device_write(self,rpc_msg, buf, buf_ix):
        """Device_WriteResp   device_write       (Device_WriteParms)     = 11; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_WriteParms()
        print(f"device_write >>> {arg} (flags={vxi11_errorCodes(arg.flags)})")
        rsp = vxi11_type.Device_WriteResp(
                error=vxi11_errorCodes.NO_ERROR.value, size=len(arg.data))
        print(f"device_write <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_WriteResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
        
    def handle_device_read(self,rpc_msg, buf, buf_ix):
        """Device_ReadResp    device_read        (Device_ReadParms)      = 12; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_ReadParms()
        print(f"device_read >>> {arg} (flags={vxi11_errorCodes(arg.flags)})")
        reason = vxi11_readReason.END
        rsp = vxi11_type.Device_ReadResp(
                error=vxi11_errorCodes.NO_ERROR.value, reason=reason, data=b"Hello World\n")
        print(f"device_read <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_ReadResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
        
    def handle_device_readstb(self,rpc_msg, buf, buf_ix):
        """Device_ReadStbResp device_readstb     (Device_GenericParms)   = 13;"""
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_GenericParms()
        print(f"device_readstb >>> {arg}")
        rsp = vxi11_type.Device_ReadStbResp(
                error=vxi11_errorCodes.NO_ERROR.value, stb=0x23)#stb=struct.pack('>B',0x42))
        print(f"device_readstb <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_ReadStbResp(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    
    def handle_destroy_link(self,rpc_msg, buf, buf_ix):
        """Device_Error       destroy_link       (Device_Link)           = 23; """
        arg_up = VXI11Unpacker(buf)
        arg_up.set_position(buf_ix)
        arg = arg_up.unpack_Device_Link()
        print(f"destroy_link >>> {arg}")
        rsp = vxi11_type.Device_Error( error=vxi11_errorCodes.NO_ERROR.value)
        print(f"destroy_link <<< {rsp}")
        p = VXI11Packer()
        p.pack_Device_Error(rsp)
        return rpc_srv.rpc_srv.pack_success_data_msg(rpc_msg.xid,p.get_buffer())
    
    # (prog, vers, proc) => func(self,rpc_msg, buf, buf_ix)
    """
    
    
    
    Device_Error       device_trigger     (Device_GenericParms)   = 14; 
    Device_Error       device_clear       (Device_GenericParms)   = 15; 
    Device_Error       device_remote      (Device_GenericParms)   = 16; 
    Device_Error       device_local       (Device_GenericParms)   = 17; 
    Device_Error       device_lock        (Device_LockParms)      = 18; 
    Device_Error       device_unlock      (Device_Link)           = 19; 
    Device_Error       device_enable_srq  (Device_EnableSrqParms) = 20; 
    Device_DocmdResp   device_docmd       (Device_DocmdParms)     = 22; 
    Device_Error       create_intr_chan   (Device_RemoteFunc)     = 25; 
    Device_Error       destroy_intr_chan  (void)                  = 26;
    """
    call_dispatch_table = {
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.create_link): handle_create_link,
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_write): handle_device_write,
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_read): handle_device_read,
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.device_readstb): handle_device_readstb,
            (vxi11_const.DEVICE_CORE,vxi11_const.DEVICE_CORE_VERSION, vxi11_const.destroy_link): handle_destroy_link,
            
    }
    
class vxi11_srv(rpc_srv.rpc_srv):
    """ 
    mapping member is a map from (prog,vers,prot) to uint
    """
    def __init__(self,port):
        super().__init__(port)
    
    def create_conn(self):
        return vxi11_conn(self)