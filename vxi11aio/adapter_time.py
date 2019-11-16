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


# This implements a "time-server" adapter

import asyncio
import time
from typing import Any, Type, Dict, Tuple, Callable, Optional, Awaitable, Coroutine

from .vxi11_srv import vxi11_errorCodes, vxi11_deviceFlags, vxi11_readReason
from .vxi11_adapter import vxi11_link, vxi11_adapter


class link(vxi11_link):
    def __init__(self, link_id: int, device: bytes, adapter: 'adapter', conn):
        self.outBuf: Optional[bytes] = None
        self.device_name = device
        super().__init__(link_id=link_id, adapter=adapter, conn=conn)
        
    async def write(self, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, data: bytes) -> Tuple[vxi11_errorCodes,int]:
        """Return (errorCode, size)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, PARAMETER_ERROR,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        await self.acquire_io_lock(flags,lock_timeout=lock_timeout, io_timeout=io_timeout)
        if(data.lower().startswith(b'*idn?')):
            self.outBuf = b"TIME_SERVER,0," + self.device_name + b'\n'
        elif(data.lower().startswith(b"time?")):
            self.outBuf = str.encode(time.strftime("%H:%M:%S +0000", time.gmtime()))
        else:
            self.outBuf = b"INVALID_QUERY\n"
        self.release_io_lock()
            
        return (vxi11_errorCodes.NO_ERROR,len(data))
        
    async def read(self, requestSize: int, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, termChar: int) -> Tuple[vxi11_errorCodes,int,bytes]:
        """Return (errorCode, vxi11_readReason, data: bytes)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, DEVICE_LOCKED_BY_ANOTHER_LINK,
        IO_TIMEOUT, IO_ERROR, or abort
        """
        if(self.outBuf is not None):
            await asyncio.sleep(2)
            ret = (vxi11_errorCodes.NO_ERROR,vxi11_readReason.END, self.outBuf)
            self.outBuf = None
            return ret
        
        return (vxi11_errorCodes.IO_TIMEOUT,0,b'')
        
    async def read_stb(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode, stb)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        return (vxi11_errorCodes.NO_ERROR,0x23)
    
    def timeout_cb(self):
        print("link TIMEOUT! (and potentially SRQ)")
        self.th = asyncio.get_running_loop().call_later(delay=6, callback=self.timeout_cb)
        if(self.srq_handle is not None):
            self.conn.send_srq(self.srq_handle)
        
class adapter(vxi11_adapter):
    def __init__(self):
        super().__init__()
        
    async def create_link(self, clientId: int, lockDevice: bool, lock_timeout: int, device: bytes, link_id: int, conn):
        """ Returns (errorcode,link)"""
        # Errorcode may be NO_ERROR, SYNTAX_ERROR, DEVICE_NOT_ACCESSIBLE,
        #    OUT_OF_RESOURCES, DEVICE_LOCKED_BY_ANOTHER_LINK, INVALID_ADDRESS
        l = link(link_id=link_id,device=device,adapter=self, conn=conn)
        l.th = asyncio.get_running_loop().call_later(delay=6, callback=l.timeout_cb)
        
        
        return (vxi11_errorCodes.NO_ERROR,l)
    
