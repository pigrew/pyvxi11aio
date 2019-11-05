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

from vxi11_srv import vxi11_deviceFlags, vxi11_errorCodes

class vxi11_link:
    
    def __init__(self, link_id: int, adapter: 'vxi11_adapter'):
        self.adapter = adapter
        self.link_id = link_id
        
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
    
    async def device_lock(self, flags: vxi11_deviceFlags, lock_timeout: int):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER,
        DEVICE_LOCKED_BY_ANOTHER_LINK, or ABORT
        """
        if(self.adapter.adapter_lock is None):
            self.adapter.adapter_lock = self
            return (vxi11_errorCodes.NO_ERROR) 
        return (vxi11_errorCodes.DEVICE_LOCKED_OUT_BY_ANOTHER_LINK) 
    
    async def device_unlock(self):
        """Return (errorCode)
        
        Errorcode may be NO_ERROR, INVALID_LINK_IDENTIFIER, NO_LOCK_HELD_BY_THIS_LINK
        """
        if(self.adapter.adapter_lock is self):
            self.adapter.adapter_lock = None
            return (vxi11_errorCodes.NO_ERROR)
        return (vxi11_errorCodes.NO_LOCK_HELD_BY_THIS_LINK)
    
    async def destroy(self):
        """If it got here, link must exist. NO_ERROR is only valid response"""
        return vxi11_errorCodes.NO_ERROR
    
class vxi11_adapter:
    # By default, "adapter" lock is used by default link implementation.
    adapter_lock = None
    
    async def create_link(self, clientId: int, lockDevice: bool, lock_timeout: int, device: bytes, link_id: int):
        """ Returns (errorcode,link)"""
        # Errorcode may be NO_ERROR, SYNTAX_ERROR, DEVICE_NOT_ACCESSIBLE,
        #    OUT_OF_RESOURCES, DEVICE_LOCKED_BY_ANOTHER_LINK, INVALID_ADDRESS
        return (vxi11_errorCodes.INVALID_ADDRESS,None)