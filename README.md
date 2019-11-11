This implements a VXI-11 server, using Python 3.7 in a cross-platform way.

main.py starts the servers, by default using the "time_adapter". To use it
with other hardware, new adapters will need to be written.

Some design goals/notes:


* Uses asyncio to handle multiple connections (one connection per target instrument)
  - This seems to be the first Python asyncio Sun/ONC RPC server on GitHub, and may be useful for other projects as a RPC server
* Compatible with Python 3.7 and 3.8.
* Be usable as a gateway to a USBTMC device (via pyvisa) or Prologix GPIB adapter
* Listens only to 127.0.0.1, reducing the need for authentication (Does NI VISA even
  support RPC authentication?).
* Serves as an arbiter, juggling the bus between links
* Requires minimum of non-standard Python libraries
* Performs compile-time code generation from XDR files (xdrgen.py from PY NFS project)
* Single-threaded network stack
  - Adapter may operate in separate thread(s), but must operate as a asyncio task (with minimal busy states)
* Flexable RPC portmapping:
  - Can register services on local portmapper or start static portmapper
  - Has its own portmapper implementation, for platforms like Windows which don't
  have one by default.
* Code is BSD 3-clause licensed, except:
  - xdrgen.py which is GPLv2
  - portmapper.x/rpc.x which are from the cooresponding RFCs.
  - VXI-11 specification is public domain. Thanks!
* Prior art and references:
  - coburnw/python-vxi11-server
  - VXI-11 specification

Current status:
* Keysight and NI VISA can create connections to the server
* Portmapper working well enough
* All VXI-11 calls have stub implementations
* Interrupt channels not implemented
* Abort channel has a do-nothing implementation
* Time server "adapter" is written
