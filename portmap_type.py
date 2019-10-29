# Generated by rpcgen.py from portmap.x on Wed Oct 23 11:10:04 2019
import sys,os
sys.path.append(os.path.dirname(__file__))
import portmap_const as const
class mapping:
    # XDR definition:
    # struct mapping {
    #     uint prog;
    #     uint vers;
    #     uint prot;
    #     uint port;
    # };
    def __init__(self, prog=None, vers=None, prot=None, port=None):
        self.prog = prog
        self.vers = vers
        self.prot = prot
        self.port = port

    def __repr__(self):
        out = []
        if self.prog is not None:
            out += ['prog=%s' % repr(self.prog)]
        if self.vers is not None:
            out += ['vers=%s' % repr(self.vers)]
        if self.prot is not None:
            out += ['prot=%s' % repr(self.prot)]
        if self.port is not None:
            out += ['port=%s' % repr(self.port)]
        return 'mapping(%s)' % ', '.join(out)
    __str__ = __repr__

class pmaplist:
    # XDR definition:
    # struct pmaplist {
    #     mapping map;
    #     pmaplist next;
    # };
    def __init__(self, map=None, next=None):
        self.map = map
        self.next = next

    def __repr__(self):
        out = []
        if self.map is not None:
            out += ['map=%s' % repr(self.map)]
        if self.next is not None:
            out += ['next=%s' % repr(self.next)]
        return 'pmaplist(%s)' % ', '.join(out)
    __str__ = __repr__

class call_args:
    # XDR definition:
    # struct call_args {
    #     uint prog;
    #     uint vers;
    #     uint proc;
    #     opaque args<>;
    # };
    def __init__(self, prog=None, vers=None, proc=None, args=None):
        self.prog = prog
        self.vers = vers
        self.proc = proc
        self.args = args

    def __repr__(self):
        out = []
        if self.prog is not None:
            out += ['prog=%s' % repr(self.prog)]
        if self.vers is not None:
            out += ['vers=%s' % repr(self.vers)]
        if self.proc is not None:
            out += ['proc=%s' % repr(self.proc)]
        if self.args is not None:
            out += ['args=%s' % repr(self.args)]
        return 'call_args(%s)' % ', '.join(out)
    __str__ = __repr__

class call_result:
    # XDR definition:
    # struct call_result {
    #     uint port;
    #     opaque res<>;
    # };
    def __init__(self, port=None, res=None):
        self.port = port
        self.res = res

    def __repr__(self):
        out = []
        if self.port is not None:
            out += ['port=%s' % repr(self.port)]
        if self.res is not None:
            out += ['res=%s' % repr(self.res)]
        return 'call_result(%s)' % ', '.join(out)
    __str__ = __repr__

