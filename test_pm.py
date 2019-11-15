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

import unittest
import asyncio

from vxi11aio import portmap_srv, rpc_client, portmap_client

from vxi11aio.xdr import portmap_const, rpc_const

class TestPM_srv(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.loop = asyncio.get_event_loop()
        self.mapper = portmap_srv.portmapper()
        # although spec only specifies that core channel needs to be mapped, KeySight IO libraries want both mapped
        self.mapper.mapping[(5,  6, portmap_const.IPPROTO_TCP)] = 987
        self.mapper.mapping[(10,11, portmap_const.IPPROTO_TCP)] = 4932
        
        self.pm_srv = portmap_srv.portmap_srv(mapper=self.mapper,port=0)
        self.pm_srv_task = self.loop.create_task(self.pm_srv.main())
        self.loop.run_until_complete(self.pm_srv.open())
    @classmethod
    def tearDownClass(self):
        self.loop.run_until_complete(self.pm_srv.close())
        self.pm_srv_task.cancel()
        try:
            self.loop.run_until_complete(self.pm_srv_task)
        except asyncio.CancelledError:
            pass
        self.pm_srv = None
        self.loop.close()
        
    def test_lookups(self):
        cl = rpc_client.rpc_client()
        self.loop.run_until_complete(cl.connect(host="127.0.0.1",port=self.pm_srv.actual_port))
        for m,port in self.mapper.mapping.items():
            
            self.assertEqual(self.loop.run_until_complete(portmap_client.getport(
                    client=cl,prog=m[0],vers=m[1])),port)
            
        self.assertEqual(self.loop.run_until_complete(portmap_client.getport(
                    client=cl,prog=m[0],vers=m[1])),port)
        self.assertEqual(self.loop.run_until_complete(portmap_client.getport(
                    client=cl,prog=987,vers=765)),0)
        self.loop.run_until_complete(cl.close())
        
    def test_bad_prog(self):
        cl = rpc_client.rpc_client()
        self.loop.run_until_complete(cl.connect(host="127.0.0.1",port=self.pm_srv.actual_port))
        rsp, msg = self.loop.run_until_complete(cl.call(9,8,7,b''))
        print(f"{rsp},{msg}")
        self.assertEqual(msg.body.rbody.areply.reply_data.stat,rpc_const.PROG_UNAVAIL)
        self.loop.run_until_complete(cl.close())
        
    def test_bad_proc(self):
        cl = rpc_client.rpc_client()
        self.loop.run_until_complete(cl.connect(host="127.0.0.1",port=self.pm_srv.actual_port))
        rsp, msg = self.loop.run_until_complete(cl.call(portmap_const.PMAP_PROG,portmap_const.PMAP_VERS,12345,b''))
        print(f"{rsp},{msg}")
        self.assertEqual(msg.body.rbody.areply.reply_data.stat,rpc_const.PROC_UNAVAIL)
        self.loop.run_until_complete(cl.close())
        
    def test_3(self):
        pass
if __name__ == '__main__':
    unittest.main()