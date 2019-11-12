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


# This implements an abstract class for a VXI "adapter".

# see discussion of locking at https://github.com/python-ivi/python-vxi11/issues/16


# The locking of the server/link is a little underspecified in the spec.
# 
# This default implementation has two locks, excl_lock and io_lock. The
# adapter has one of each lock, though implementations probably want to do
# things differently.
#
# IO operations first check that no other connection has an exclusive lock,
# optionally waiting for that lock.The IO timeout value is used during
# waiting for the IO lock
#
# Then, an IO lock is acquired for the particular operation. Here, the
# IO lock is global to the adapter.

import asyncio
from vxi11_srv import vxi11_deviceFlags, vxi11_errorCodes

class vxi11_link:
    
    def __init__(self, link_id: int, adapter: 'vxi11_adapter', conn):
        self.adapter = adapter
        self.link_id = link_id
        self.conn = conn
        self.srq_handle = None # set to a bytes[40] when SRQ are enabled
        
    async def read(self, requestSize: int, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, termChar: int):
        """Return (errorCode, vxi11_readReason, data: bytes)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, DEVICE_LOCKED_BY_ANOTHER_LINK,
        IO_TIMEOUT, IO_ERROR, or abort
        """
        return (vxi11_errorCodes.IO_ERROR, 0, b'')
    
    async def write(self, io_timeout: int, lock_timeout: int, flags: vxi11_deviceFlags, data: bytes):
        """Return (errorCode, size)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, PARAMETER_ERROR,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        return (vxi11_errorCodes.IO_ERROR, 0)
    
    async def read_stb(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode, stb)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or abort
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED,0)
    
    async def trigger(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED)
    
    async def clear(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED)
    
    
    async def local(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED)
    
    async def remote(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED)  
    async def docmd(self, flags: vxi11_deviceFlags, io_timeout: int, lock_timeout: int,
                    cmd: int, network_order: bool, datasize, data_in: bytes):
        """Return (errorCode,data_out)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, OPERATION_NOT_SUPPORTED,
        DEVICE_LOCKED_BY_ANOTHER_LINK, IO_TIMEOUT, IO_ERROR, or ABORT
        """
        return (vxi11_errorCodes.OPERATION_NOT_SUPPORTED,b'')  
    
    async def destroy(self):
        """If it got here, link must exist. NO_ERROR is only valid response"""
        # Unlock if necessary
        if(self.adapter.adapter_excl_lock_owner is self):
            self.adapter.adapter_excl_lock_owner = None
            self.adapter.adapter_excl_lock.release()
        return vxi11_errorCodes.NO_ERROR
    
    async def device_lock(self, flags: vxi11_deviceFlags, lock_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER,
        DEVICE_LOCKED_BY_ANOTHER_LINK, or ABORT
        """
        if(self.adapter.adapter_excl_lock_owner is self):
            return (vxi11_errorCodes.DEVICE_LOCKED_OUT_BY_ANOTHER_LINK)
        
        if(flags.WAITLOCK): # requesting waiting
            try:
                await asyncio.wait_for(self.adapter.adapter_excl_lock.acquire(), timeout=(lock_timeout+1)/1000.0)
            except asyncio.TimeoutError:
                return (vxi11_errorCodes.DEVICE_LOCKED_OUT_BY_ANOTHER_LINK) 
        else:
            if(self.adapter.adapter_excl_lock_owner is not None and self.adapter.adapter_excl_lock_owner is not self):
                return (vxi11_errorCodes.DEVICE_LOCKED_OUT_BY_ANOTHER_LINK)
            await self.adapter.adapter_excl_lock.acquire()
        self.adapter.adapter_excl_lock_owner = self
        return (vxi11_errorCodes.NO_ERROR) 
    
    async def device_unlock(self):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, NO_LOCK_HELD_BY_THIS_LINK
        """
        if(self.adapter.adapter_excl_lock_owner is self):
            self.adapter.adapter_excl_lock.release()
            self.adapter.adapter_excl_lock_owner = None
            return (vxi11_errorCodes.NO_ERROR)
        return (vxi11_errorCodes.NO_LOCK_HELD_BY_THIS_LINK)
    
    async def acquire_io_lock(self, flags: vxi11_deviceFlags, lock_timeout: int, io_timeout: int) -> bool:
        """Returns true if lock is acquired.
        
        There is a semblance of a race condition, as specified in the spec, where a IO
        operation does not prevent another link from acquiring the exclusive lock"""
        
        # Forst, check on the exclusive lock
        if(flags.WAITLOCK): # requesting waiting
            # Does another link already hold the exclusive lock?
            if((self.adapter.adapter_excl_lock_owner is not None) and (self.adapter.adapter_excl_lock_owner is not self)):
                try:
                    # Take lock temporarily as a way to implement the timeout
                    await asyncio.wait_for(self.adapter.adapter_excl_lock.acquire(), timeout=(1+lock_timeout)/1000.0)
                    self.adapter.adapter_excl_lock.release()
                except asyncio.TimeoutError:
                    return False
            
        else: # requesting no waiting
            # Does another link already hold the excl lock?
            if(self.adapter.adapter_excl_lock_owner is not None and self.adapter.adapter_excl_lock_owner is not self):
                return False
            
        # Wait for up to io_timeout to get the io_lock
        try:
            await asyncio.wait_for(self.adapter.adapter_io_lock.acquire(), timeout=(1+io_timeout)/1000.0)
        except asyncio.TimeoutError:
            return False
        return True
        
    def release_io_lock(self):
        """Returns true if lock is acquired"""
        self.adapter.adapter_io_lock.release()

class vxi11_adapter:   
    adapter_io_lock: asyncio.Lock
    adapter_excl_lock: asyncio.Lock
    adapter_excl_lock_owner: vxi11_link
    
    def __init__(self):
        self.adapter_io_lock = asyncio.Lock()
        self.adapter_excl_lock = asyncio.Lock()
        self.adapter_excl_lock_owner = None
    
    async def create_link(self, clientId: int, lockDevice: bool, lock_timeout: int, device: bytes, link_id: int, conn):
        """ Returns (errorcode,link)"""
        # Errorcode may be NO_ERROR, SYNTAX_ERROR, DEVICE_NOT_ACCESSIBLE,
        #    OUT_OF_RESOURCES, DEVICE_LOCKED_BY_ANOTHER_LINK, INVALID_ADDRESS
        return (vxi11_errorCodes.INVALID_ADDRESS,None)