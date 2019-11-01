This implements a VXI-11 server, using Python 3.7 in a cross-platform way.

Some design goals/notes:

* Use asyncio to handle multiple connections (one connection per target instrument)
* Be usable as a gateway to a USBTMC device (via pyvisa) or Prologix GPIB adapter
* Have its own portmapper implementation, for platforms like Windows which don't
  have one by default.
* Listen only to 127.0.0.1, reducing the need for authentication (Does NI VISA even
  support RPC authentication?).
* Serve as an arbiter, juggling the bus between links
* Require minimal non-standard Python libraries
* Perform compile-time code generation from XDR files (xdrgen.py from PY NFS project)
* Single-threaded network stack
  - Adapter may operate in separate thread(s), but must operate as a asyncio task (with minimal busy states)
* Code is BSD 3-clause licensed, except:
  - xdrgen.py which is GPLv2
  - portmapper.x/rpc.x which are from the cooresponding RFCs.
  - VXI-11 specification is public domain. Thanks!
* Prior art and references:
  - coburnw/python-vxi11-server
  - VXI-11 specification


Current status:
* NI VISA can create connections to the server
* Portmapper returns static mappings
* 5 of 15 RPC calls have stub implementations
