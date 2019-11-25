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


# This implements a proxy to a VISA USBTMC device

# The VISA session runs in a separate thread, using an event queue in order to
# serialize requests.

import asyncio
import concurrent
import time
from typing import Any, Type, Dict, Tuple, Callable, Optional, Awaitable, Coroutine

from .vxi11_srv import vxi11_errorCodes, vxi11_deviceFlags, vxi11_readReason, vxi11_core_conn
from .vxi11_adapter import vxi11_link, vxi11_adapter

import pyvisa


class link(vxi11_link):
    def __init__(self, link_id: int, device: bytes, adapter: 'adapter', conn: vxi11_core_conn):
        self.outBuf: Optional[bytes] = None
        self.device_name = device
        super().__init__(link_id=link_id, adapter=adapter, conn=conn)
        
    async def write(self, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, data: bytes) -> Tuple[vxi11_errorCodes,int]:
        """Return (errorCode, size)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, PARAMETER_ERROR,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        if (not await self.acquire_io_lock(flags,lock_timeout=lock_timeout, io_timeout=io_timeout)):
            return (vxi11_errorCodes.IO_TIMEOUT,0)
        def f(inst: pyvisa.resources.MessageBasedResource, data: bytes) -> Tuple[int,pyvisa.constants.StatusCode]:
            l = inst.write_raw(data)
            return l
        (l,_) = await asyncio.get_event_loop().run_in_executor(self.adapter._exec, f, self.adapter.inst, data)
        self.release_io_lock()
        print(l)
        return (vxi11_errorCodes.NO_ERROR,l)
        
    async def read(self, requestSize: int, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, termChar: int) -> Tuple[vxi11_errorCodes,int,bytes]:
        """Return (errorCode, vxi11_readReason, data: bytes)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, DEVICE_LOCKED_BY_ANOTHER_LINK,
        IO_TIMEOUT, IO_ERROR, or abort
        """
        
        if (not await self.acquire_io_lock(flags,lock_timeout=lock_timeout, io_timeout=io_timeout)):
            return (vxi11_errorCodes.IO_TIMEOUT,0,b'')
        def f(inst: pyvisa.resources.MessageBasedResource, requestSize: int) -> bytes:
            return inst.read_raw(requestSize)
            #return inst.read()
        data = await asyncio.get_event_loop().run_in_executor(self.adapter._exec, f, self.adapter.inst, requestSize)
        self.release_io_lock()
        print(f"{data!r}")
        return (vxi11_errorCodes.NO_ERROR,vxi11_readReason.END,data)
        
    async def read_stb(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int) -> Tuple[vxi11_errorCodes,int]:
        """Return (errorCode, stb)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        def f(inst: pyvisa.resources.MessageBasedResource) -> int:
            return inst.read_stb()
        if(not await self.acquire_io_lock(flags,lock_timeout=lock_timeout, io_timeout=io_timeout)):
            return (vxi11_errorCodes.IO_TIMEOUT,0)
        stb = await asyncio.get_event_loop().run_in_executor(self.adapter._exec, f,self.adapter.inst)
        self.release_io_lock()
        return (vxi11_errorCodes.NO_ERROR,stb)
    
    async def clear(self, flags: vxi11_deviceFlags, lock_timeout: int,
                    io_timeout: int) -> vxi11_errorCodes:
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        if (not await self.acquire_io_lock(flags,lock_timeout=lock_timeout, io_timeout=io_timeout)):
            return (vxi11_errorCodes.IO_TIMEOUT)
        def f(inst: pyvisa.resources.MessageBasedResource) -> pyvisa.constants.StatusCode:
            # Pyvisa discards the return value of the call to viClear, so lets call it directly
            return inst.visalib.clear(inst.session)
        sc = await asyncio.get_event_loop().run_in_executor(self.adapter._exec, f, self.adapter.inst)
        self.release_io_lock()
        scMap = {
                pyvisa.constants.StatusCode.success: vxi11_errorCodes.NO_ERROR,
                pyvisa.constants.StatusCode.error_timeout: vxi11_errorCodes.IO_TIMEOUT,
                }
        return (scMap.get(sc, vxi11_errorCodes.IO_ERROR))
    
class adapter(vxi11_adapter):
    def __init__(self, visaAddress: str, visa_library:str='') -> None:
        self.visaAddress: str = visaAddress
        rm = pyvisa.ResourceManager(visa_library=visa_library)
        self.inst: pyvisa.resources.MessageBasedResource = rm.open_resource(visaAddress)
        self._exec = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="visa_")
        super().__init__()
        
    async def create_link(self, clientId: int, lockDevice: bool,
                          lock_timeout: int, device: bytes, link_id: int, conn:vxi11_core_conn) -> Tuple[vxi11_errorCodes,link]:
        """ Returns (errorcode,link)"""
        # Errorcode may be NO_ERROR, SYNTAX_ERROR, DEVICE_NOT_ACCESSIBLE,
        #    OUT_OF_RESOURCES, DEVICE_LOCKED_BY_ANOTHER_LINK, INVALID_ADDRESS
        l = link(link_id=link_id,device=device,adapter=self, conn=conn)
        
        
        return (vxi11_errorCodes.NO_ERROR, l)