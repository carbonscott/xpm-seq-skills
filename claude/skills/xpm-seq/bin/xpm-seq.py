#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "numpy",
# ]
# ///
"""xpm-seq: LCLS-II XPM timing sequence CLI (ratecalc / generate / validate).

Usage:
    xpm-seq ratecalc <rate1> <rate2> ... [--json] [--list]
    xpm-seq generate periodic --rates ... --descriptions ... -o FILE [flags]
    xpm-seq generate train --train-spacing ... [flags]
    xpm-seq validate <script.py> --engine N [--json]
"""

import argparse
import json
import math
import logging
import os
import sys
from itertools import chain
from functools import reduce
import operator

import numpy


# ============================================================
# globals — constants (was xpm_seq/globals.py)
# ============================================================

MAXSEQ = 64
NALWSEQ = 14
MAXDST = 16
MAXCTL = 72
TPGSEC = 910000
CTLBITS = 16


# ============================================================
# tsdef — timing system definitions (was xpm_seq/tsdef.py)
# ============================================================

if os.environ.get('XPM_SEQ_MODE', '').lower() == 'ued':
    fixedRates  = ['500kHz', '100kHz','50kHz','10kHz','5kHz','1kHz','500Hz','1Hz']
    fixedRateHzToMarker = {'500kHz':0, '100kHz':1, '50kHz':2, '10kHz':3, '5kHz':4, '1kHz':5, '500Hz':6, '1Hz':7}
    FixedIntvs = [1, 5, 10, 50, 100, 500, 1000, 500000]
    FixedIntvsDict = {"500kH":{"intv":1     ,"marker":0},
                      "100kH":{"intv":5     ,"marker":1},
                      "50kH" :{"intv":10    ,"marker":2},
                      "10kH" :{"intv":50    ,"marker":3},
                      "5kH"  :{"intv":100   ,"marker":4},
                      "1kH"  :{"intv":500   ,"marker":5},
                      "500H" :{"intv":1000  ,"marker":6},
                      "1H"   :{"intv":500000,"marker":7}}

    acRates     = ['60Hz','30Hz','10Hz','5Hz','1Hz','0.5Hz']
    acTS        = ['TS%u'%(i+1) for i in range(6)]
    acRateHzToMarker    = {'60Hz':0, '30Hz':1, '10Hz':2, '5Hz':3, '1Hz':4, '0_5Hz':5 }
    ACIntvs    = [1, 2, 6, 12, 60, 120]

    ACIntvsDict = {"0.5H":{"intv":120,"marker":5},
                   "1H"  :{"intv":60 ,"marker":4},
                   "5H"  :{"intv":12 ,"marker":3},
                   "10H" :{"intv":6  ,"marker":2},
                   "30H" :{"intv":2  ,"marker":1},
                   "60H" :{"intv":1  ,"marker":0}}

    FixedFidRate  = 500e3
    FixedToACFids = int(500e3/360)

else:
    fixedRates  = ['1.02Hz','10.2Hz','102Hz','1.02kHz','10.2kHz','71.4kHz','929kHz', 'Undef7', 'Undef8', 'Undef9' ]
    fixedRateHzToMarker = {'929kHz':6, '71kHz':5, '10kHz':4, '1kHz':3, '100Hz':2, '10Hz':1, '1Hz':0}
    FixedIntvs = [910000, 91000, 9100, 910, 91, 13, 1]
    FixedIntvsDict = {"1H"   :{"intv":910000,"marker":0},
                      "10H"  :{"intv":91000 ,"marker":1},
                      "100H" :{"intv":9100  ,"marker":2},
                      "1kH"  :{"intv":910   ,"marker":3},
                      "10kH" :{"intv":91    ,"marker":4},
                      "70kH" :{"intv":13    ,"marker":5},
                      "910kH":{"intv":1     ,"marker":6}}

    acRates     = ['0.5Hz','1Hz','5Hz','10Hz','30Hz','60Hz']
    acTS        = ['TS%u'%(i+1) for i in range(6)]
    acRateHzToMarker    = {'60Hz':5, '30Hz':4, '10Hz':3, '5Hz':2, '1Hz':1, '0_5Hz':0 }
    ACIntvs    = [120, 60, 12, 6, 2, 1]

    ACIntvsDict = {"0.5H":{"intv":120,"marker":0},
                   "1H"  :{"intv":60 ,"marker":1},
                   "5H"  :{"intv":12 ,"marker":2},
                   "10H" :{"intv":6  ,"marker":3},
                   "30H" :{"intv":2  ,"marker":4},
                   "60H" :{"intv":1  ,"marker":5}}

    FixedFidRate  = 910e3
    FixedToACFids = int(910e3/0.98/360)


# ============================================================
# rates — sub-harmonic math (was xpm_seq/rates.py)
# ============================================================

FRAME_PERIOD_SEC = 0.98
BASE_RATE_HZ = TPGSEC / FRAME_PERIOD_SEC


def all_subharmonics():
    divisors = sorted(d for d in range(1, TPGSEC + 1) if TPGSEC % d == 0)
    return divisors


def hz_to_period(rate_hz):
    return round(BASE_RATE_HZ / rate_hz)


def period_to_hz(period):
    return BASE_RATE_HZ / period


def nearest_exact(rate_hz, count=5):
    subharmonics = all_subharmonics()
    candidates = []
    for period in subharmonics:
        actual_hz = period_to_hz(period)
        error_pct = (actual_hz - rate_hz) / rate_hz * 100
        candidates.append({
            "period": period,
            "rate_hz": actual_hz,
            "error_pct": error_pct,
        })
    candidates.sort(key=lambda c: abs(c["error_pct"]))
    return candidates[:count]


# ============================================================
# seq — instruction set (was xpm_seq/seq.py)
# ============================================================

verbose = False

def factor(n):
    if n <= Instruction.maxocc:
        return (n)

    if n > Instruction.maxocc * Instruction.maxocc:
        raise ValueError('factor failed: argument too large')

    primes = []
    rem = n
    for i in range(2,int(math.sqrt(n)+1)):
        while rem%i == 0:
            primes.append(i)
            rem = rem//i
        if rem == 1:
            break

    print(f'primes of {n} are {primes}')


class Instruction(object):

    maxocc = 0xfff
    maxcc  = 4

    def __init__(self, args):
        self.args = args

    def encoding(self):
        args = [0]*7
        args[0] = len(self.args)-1
        args[1:len(self.args)+1] = self.args
        return args

    def __str__(self):
        return self.print_()


class FixedRateSync(Instruction):

    opcode = 0

    def __init__(self, marker, occ):
        if occ > Instruction.maxocc:
            raise ValueError('FixedRateSync called with occ={}'.format(occ))
        if marker in FixedIntvsDict:
            mk     = marker
            marker = FixedIntvsDict[mk]['marker']
            self.intv = FixedIntvsDict[mk]['intv']
        else:
            self.intv = FixedIntvs[marker]
        super(FixedRateSync, self).__init__( (self.opcode, marker, occ) )

    def _word(self):
        return int((2<<29) | ((self.args[1]&0xf)<<16) | (self.args[2]&Instruction.maxocc))

    def print_(self):
        return 'FixedRateSync({}) # occ({})'.format(fixedRates[self.args[1]],self.args[2])

    def execute(self,engine):
        intv = self.intv
        engine.instr += 1
        step = intv*self.args[2]-(engine.frame%intv)
        if step>0:
            engine.frame  += step
            engine.request = 0
        engine.modes |= 1


class ACRateSync(Instruction):

    opcode = 1

    def __init__(self, timeslotm, marker, occ):
        if occ > Instruction.maxocc:
            raise ValueError('ACRateSync called with occ={}'.format(occ))
        if timeslotm > 0x3f:
            raise ValueError('ACRateSync called with timeslotm={}'.format(timeslotm))
        if marker in ACIntvsDict:
            mk     = marker
            marker = ACIntvsDict[mk]['marker']
            self.intv = ACIntvsDict[mk]['intv']
        else:
            self.intv = ACIntvs[marker]
        super(ACRateSync, self).__init__( (self.opcode, timeslotm, marker, occ) )

    def _word(self):
        return int((3<<29) | ((self.args[1]&0x3f)<<23) | ((self.args[2]&0xf)<<16) | (self.args[3]&Instruction.maxocc))

    def print_(self):
        return 'ACRateSync({}/0x{:x}) # occ({})'.format(acRates[self.args[2]],self.args[1],self.args[3])

    def execute(self,engine):
        intv = self.intv
        engine.instr += 1
        mask = self.args[1]&0x3f
        for i in range(self.args[3]):
            while True:
                acphase = engine.frame % FixedToACFids
                engine.frame += FixedToACFids - acphase
                acframe = int(engine.frame/FixedToACFids)
                ts = acframe % 6
                if ((1<<ts)&mask)!=0 and (int(acframe/6)%intv)==0:
                    break

        engine.request = 0
        engine.modes  |= 2


class Branch(Instruction):

    opcode = 2

    def __init__(self, args):
        if len(args)>2:
            if args[2] > 0x3:
                raise ValueError('Branch called with ctr={}'.format(args[2]))
            if args[3] > Instruction.maxocc:
                raise ValueError('Branch called with occ={}'.format(args[3]))
        super(Branch, self).__init__(args)

    def _word(self, a = None):
        if a is None:
            w = self.args[1] & 0x7ff
        else:
            w = a & 0x7ff
        if len(self.args)>2:
            w = ((self.args[2]&0x3)<<27) | (1<<24) | ((self.args[3]&Instruction.maxocc)<<12) | w
        return int(w)

    @classmethod
    def unconditional(cls, line):
        return cls((cls.opcode, line))

    @classmethod
    def conditional(cls, line, counter, value):
        return cls((cls.opcode, line, counter, value))

    def address(self):
        return self.args[1]

    def print_(self):
        if len(self.args)==2:
            return 'Branch unconditional to line {}'.format(self.args[1])
        else:
            return 'Branch to line {} until ctr{}={}'.format(self.args[1],self.args[2],self.args[3])

    def execute(self,engine):
        if len(self.args)==2:
            if engine.instr==self.args[1]:
                engine.done = True
            engine.instr = self.args[1]
        else:
            if engine.ccnt[self.args[2]]==self.args[3]:
                engine.instr += 1
                engine.ccnt[self.args[2]] = 0
            else:
                engine.instr = self.args[1]
                engine.ccnt[self.args[2]] += 1


class CheckPoint(Instruction):

    opcode = 3

    def __init__(self):
        super(CheckPoint, self).__init__((self.opcode,))

    def _word(self):
        return int((1<<29))

    def print_(self):
        return 'CheckPoint'

    def execute(self,engine):
        engine.instr += 1


class BeamRequest(Instruction):

    opcode = 4

    def __init__(self, charge):
        super(BeamRequest, self).__init__((self.opcode, charge))

    def _word(self):
        return int((4<<29) | self.args[1])

    def print_(self):
        return 'BeamRequest charge {}'.format(self.args[1])

    def execute(self,engine):
        engine.request = (self.args[1]<<16) | 1
        engine.instr += 1


class ControlRequest(Instruction):

    opcode = 5

    def __init__(self, word):
        if isinstance(word,list):
            v = 0
            for w in word:
                v |= (1<<w)
        else:
            v = word
        super(ControlRequest, self).__init__((self.opcode, v))

    def _word(self):
        return int((4<<29) | self.args[1])

    def print_(self):
        codes = []
        w = self.args[1]
        code = 0
        while w:
            if w&1:
                codes.append(code)
            w >>= 1
            code += 1

        return f'ControlRequest word 0x{self.args[1]:x} {codes}'

    def execute(self,engine):
        engine.request = self.args[1]
        engine.instr += 1


class Call(Instruction):

    opcode = 6

    def __init__(self, line):
        super(Call, self).__init__((self.opcode,line))

    def _word(self,a):
        return int((5<<29) | (a&0x7ff))

    def address(self):
        return self.args[1]

    def print_(self):
        return f'Call 0x{self.args[1]:x}'

    def execute(self,engine):
        engine.returnaddr = engine.instr+1
        engine.instr = self.args[1]


class Return(Instruction):

    opcode = 7

    def __init__(self):
        super(Return, self).__init__((self.opcode,))

    def _word(self):
        return int((5<<29) | (1<<12))

    def print_(self):
        return f'Return'

    def execute(self,engine):
        if engine.returnaddr is None:
            raise ValueError(f'engine.returnaddr is None')
        engine.instr = engine.returnaddr
        engine.returnaddr = None


class Macro(Instruction):

    def __init__(self, args):
        super(Macro, self).__init__(args)

    def _word(self):
        raise RuntimeError(f'Attempted encoding of macro Wait({self.args})')

    def execute(self,engine):
        raise RuntimeError(f'Attempting to simulate macro Wait({self.args})')


class Wait(Instruction):

    opcode = -1

    def __init__(self, marker, occ):
        if marker is None:
            self.intv = 1
            for k,v in FixedIntvsDict.items():
                if v["intv"]==self.intv:
                    marker = v["marker"]
                    break
        elif marker in FixedIntvsDict:
            mk     = marker
            marker = FixedIntvsDict[mk]['marker']
            self.intv = FixedIntvsDict[mk]['intv']
        else:
            self.intv = FixedIntvs[marker]
        super(Wait, self).__init__( (self.opcode, marker, occ) )

    def print_(self):
        return f'Wait({fixedRates[self.args[1]]}) # occ({self.args[2]})'

    def replace(self, cc, line):
        marker = self.args[1]
        occ    = self.args[2]
        n = int(occ/Instruction.maxocc)
        rem = occ - n*Instruction.maxocc
        if cc is None or n < 3:
            l = [FixedRateSync(marker,occ=Instruction.maxocc)]*n
        else:
            l = [FixedRateSync(marker,occ=Instruction.maxocc),
                 Branch.conditional( line, cc, n-1 )]
        if rem > 0:
            l.append(FixedRateSync(marker,occ=rem))
        return l


class WaitA(Instruction):

    opcode = -2

    def __init__(self, timeslotm, marker, occ):
        if timeslotm > 0x3f:
            raise ValueError('WaitA called with timeslotm={}'.format(timeslotm))
        if marker is None:
            self.intv = 1
            for k,v in ACIntvsDict.items():
                if v["intv"]==self.intv:
                    marker = v["marker"]
                    break
        elif marker in ACIntvsDict:
            mk        = marker
            marker    = ACIntvsDict[mk]['marker']
            self.intv = ACIntvsDict[mk]['intv']
        else:
            self.intv = ACIntvs[marker]
        super(WaitA, self).__init__( (self.opcode, timeslotm, marker, occ) )

    def print_(self):
        return f'WaitA(0x{self.args[1]:x},{acRates[self.args[2]]}) # occ({self.args[3]})'

    def replace(self, cc, line):
        timeslotm = self.args[1]
        marker    = self.args[2]
        occ       = self.args[3]
        n = int(occ/Instruction.maxocc)
        rem = occ - n*Instruction.maxocc
        if cc is None or n < 3:
            l = [ACRateSync(timeslotm,marker,occ=Instruction.maxocc)]*n
        else:
            l = [ACRateSync(timeslotm,marker,occ=Instruction.maxocc),
                 Branch.conditional( line, cc, n-1 )]
        if rem > 0:
            l.append(ACRateSync(timeslotm,marker,occ=rem))
        return l


def decodeInstr(w):
    idw = w>>29
    instr = Instruction([])
    if idw == 0:  # Branch
        if w&(1<<24):
            instr = Branch.conditional(line=w&0x7ff,counter=(w>>27)&3,value=(w>>12)&Instruction.maxocc)
        else:
            instr = Branch.unconditional(line=w&0x7ff)
    elif idw == 1: # Checkpoint
        instr = CheckPoint()
    elif idw == 2: # FixedRateSync
        instr = FixedRateSync(marker=(w>>16)&0xf,occ=w&Instruction.maxocc)
    elif idw == 3: # ACRateSync
        instr = ACRateSync(timeslotm=(w>>23)&0x3f,marker=(w>>16)&0xf,occ=w&Instruction.maxocc)
    elif idw == 4: # Request (assume ControlRequest)
        instr = ControlRequest(word = w&0xffff)
    elif idw == 5: # Call/Return
        if (w&(1<<12)):
            instr = Subroutine.return_()
        else:
            instr = Subroutine.call(w&0xfff)
    return instr


def validate(filename):
    config = {'title':'TITLE', 'descset':None, 'instrset':None, 'seqcodes':None, 'repeat':False}
    seq = 'from psdaq.seq.seq import *\n'
    seq += open(filename).read()
    exec(compile(seq, filename, 'exec'), {}, config)
    l = preproc(config['instrset'])

    if len(l) > 2048:
        logging.warning(f'{filename} may be too large.  {len(l)} > 2048.')
    else:
        logging.info(f'{filename} has {len(l)} instructions.')

    d = {cc:[] for cc in range(Instruction.maxcc)}
    for line,instr in enumerate(l):
        if instr.args[0]==Branch.opcode and len(instr.args)>2:
            cc   = instr.args[2]
            addr = instr.args[1]
            d[cc].append([addr,line])

    for cc in range(Instruction.maxcc):
        for r in d[cc]:
            addr = r[0]
            for s in d[cc]:
                if addr>s[0] and addr<s[1]:
                    raise ValueError(f'{filename}: CC {cc} found in overlapping loops {r} {s}')


def relocate(instrset,target,source=0):
    words = []
    for i in instrset:
        if hasattr(i,'address'):
            jumpto = i.address()
            if jumpto > len(instrset)+source:
                return None
            elif jumpto >= source:
                words.append(i._word(jumpto+target))
            else:
                return None
        else:
            words.append(i._word())

    for i,ins in enumerate(instrset):
        print(f'{i}: {ins}')

    for i,w in enumerate(words):
        print(f'{i}: {w:x}')

    return words


def preproc(instrset):

    d = {cc:[] for cc in range(Instruction.maxcc)}
    for line,instr in enumerate(instrset):
        if instr.args[0]==Branch.opcode and len(instr.args)>2:
            cc   = instr.args[2]
            addr = instr.args[1]
            if line < addr:
                print(f'Preprocessor detected forward conditional branch')
            else:
                d[cc].append([addr,line])

    def _findcc(line):
        for cc in range(Instruction.maxcc):
            lAvail = True
            for br in d[cc]:
                if line >= br[0] and line < br[1]:
                    lAvail = False
                    break
            if lAvail:
                return cc
        return None

    reps  = {}
    for line,instr in enumerate(instrset):
        if instr.args[0]==Wait.opcode:
            reps[line] = Wait.replace(instr, _findcc(line), line)
        elif instr.args[0]==WaitA.opcode:
            reps[line] = WaitA.replace(instr, _findcc(line), line)

    def _target( old ):
        target = old
        for r in reps.keys():
            if r < old:
                target += len(reps[r])-1
        return target

    def _relocate(instr):
        if instr.opcode == Branch.opcode:
            if len(instr.args) > 2:
                return Branch.conditional(_target(instr.args[1]),
                                          instr.args[2],
                                          instr.args[3])
            else:
                return Branch.unconditional(_target(instr.args[1]))
        return instr

    newinstr = []
    for line,instr in enumerate(instrset):
        start = len(newinstr)
        if line in reps:
            for rline,rinstr in enumerate(reps[line]):
                newinstr.append(_relocate(rinstr))
        else:
            newinstr.append(_relocate(instr))

    return newinstr


# ============================================================
# simulator — headless engine (was xpm_seq/simulator.py)
# ============================================================

class Engine:

    def __init__(self):
        self.request = 0
        self.instr = 0
        self.frame = 0
        self.ccnt = [0] * 4
        self.done = False
        self.returnaddr = None
        self.modes = 0


class HeadlessSimulator:

    @staticmethod
    def simulate(instrset, start_frame=0, stop_frame=910000):
        engine = Engine()
        engine.frame = start_frame

        events = {}
        max_iterations = stop_frame * 10
        iterations = 0

        while not engine.done and engine.frame < stop_frame:
            if engine.instr >= len(instrset):
                break

            old_frame = engine.frame
            instrset[engine.instr].execute(engine)

            if engine.request != 0:
                frame = old_frame
                req = engine.request
                for bit in range(16):
                    if req & (1 << bit):
                        events.setdefault(bit, []).append(frame)

            iterations += 1
            if iterations > max_iterations:
                break

        return events


def _seq_namespace():
    """Return a dict of all instruction classes/functions needed by sequence scripts."""
    return {
        name: obj for name, obj in globals().items()
        if isinstance(obj, type) and issubclass(obj, Instruction)
        or name in ('preproc', 'validate', 'relocate', 'decodeInstr')
    }


def load_script(path):
    source = open(path).read()

    for imp in (
        'from psdaq.seq.seq import *',
        'from xpm_seq.seq import *',
        'from xpm_seq import *',
    ):
        source = source.replace(imp, '')

    ns = _seq_namespace()
    config = {
        'title': 'TITLE',
        'descset': None,
        'instrset': None,
        'seqcodes': None,
        'repeat': False,
    }
    config.update(ns)
    exec(compile(source, path, 'exec'), config)

    instrset = config['instrset']
    seqcodes = config.get('seqcodes') or {}

    return instrset, seqcodes


# ============================================================
# periodicgenerator (was xpm_seq/periodicgenerator.py)
# ============================================================

def myunion(s0,s1):
    return set(s0) | set(s1)


class PeriodicGenerator(object):
    '''period : value or list of values representing the interval to be repeated.
       start  : value or list of values of the bucket on which to start the period(s).
       charge : electron bunch charge for beam requests.  Only used by TPG.
       repeat -1 : repeat forever
               0 : don't repeat
               n : repeat n times
       notify : insert a notify instruction when the entire sequence is completed
       merge  : output ControlRequest([0]) on any of the periods, else ControlRequest([n..]) for each period n.
       marker : marker id for period counts
       resync : insert a slow fixed rate marker at the end of the sequence to keep it aligned in cases of XPM
                transmission/receive drops.  This can only happen if the repeating part of the sequence does not cross
                the slow marker boundaries.
    '''
    def __init__(self, period, start, charge=None, repeat=-1, notify=False, merge=False, marker=None, resync=True):
        self.charge = charge
        self.merge  = merge
        if marker is None:
            for k,v in FixedIntvsDict.items():
                if v["intv"]==1:
                    marker = k
                    break
        self.resync = resync
        self.init(period, start, marker, repeat, notify)

    def init(self, period, start, marker='910kH', repeat=-1, notify=False):
        self.async_start       = 0
        if isinstance(period,list):
            if len(period) != len(start):
                raise ValueError('period and start lists must be equal length')
            self.period    = period
            self.start     = start
        else:
            self.period    = [period]
            self.start     = [start]
        if marker in FixedIntvsDict.keys():
            self.syncins = f'Wait( marker=\"{marker}\"'
        elif marker[0]=='a':
            rate, tslots = marker[1:].split('t')
            tsm = 0
            for t in tslots:
                tsm |= 1<<(int(t)-1)
            self.syncins = f'WaitA( {tsm}, \"{rate}\"'
        else:
            options = list(FixedIntvsDict.keys())
            options.append( f'a{acRates}t[1..6]')
            raise ValueError(f'marker {marker} not recognized. Options are {options}')

        self.repeat = repeat
        self.notify = notify

        self.desc = 'Periodic: period[{}] start[{}]'.format(period,start)
        self.instr = ['instrset = []']
        self.ninstr = 0
        self._fill_instr()
        if self.ninstr > 1024:
            raise RuntimeError('Instruction cache overflow [{}]'.format(self.ninstr))

    def _wait(self, intv):
        if intv <= 0:
            raise ValueError
        self.instr.append(f'instrset.append( {self.syncins}, occ={intv} ) )' )
        self.ninstr += 1

    def _fill_instr(self):
        period = numpy.lcm.reduce(self.period)

        print('# period {}  args.period {}'.format(period,self.period))
        reps   = [period // p for p in self.period]
        last_start = numpy.max(self.start)

        if last_start > 0:
            bkts = [range(self.start[i],last_start,self.period[i]) for i in range(len(self.period))]
            self.fill_bkts(bkts,last_start)

        start_repeat = self.ninstr
        bkts = []
        for i in range(len(self.start)):
            if self.start[i]<last_start:
                np = 1+(last_start-self.start[i]-1)//self.period[i]
                bkts.append(range(np*self.period[i]+self.start[i]-last_start,period,self.period[i]))
            else:
                bkts.append(range(0,period,self.period[i]))
        if self.fill_bkts(bkts,period,resync=self.resync,start=last_start):
            start_repeat = 0

        if self.repeat < 0:
            self.instr.append(f'instrset.append( Branch.unconditional({start_repeat}) )')
            self.ninstr += 1
        else:
            if self.repeat > 0:
                self.instr.append(f'instrset.append( Branch.conditional({start_repeat}, 2, {self.repeat}) )')
                self.ninstr += 1

            if self.notify:
                self.instr.append('instrset.append( CheckPoint() )')
                self.ninstr += 1

            self.instr.append('last = len(instrset)')
            self.instr.append('instrset.append( Wait(marker="1H",occ=1) )')
            self.instr.append('instrset.append( Branch.unconditional(last) )')
            self.ninstr += 2


    def fill_bkts(self,bkts,period,resync=False,start=None):
        bunion = sorted(reduce(myunion,bkts))
        reqs   = []
        for b in bunion:
            req = []
            for i,bs in enumerate(bkts):
                if b in bs:
                    req.append(i)
            reqs.append(req)

        blist  = [0] + list(bunion)
        bsteps = list(map(operator.sub,blist[1:],blist[:-1]))
        rem    = period - blist[-1]

        if verbose:
            print('#common period {}'.format(period))
            print('#bkts {}'.format(bkts))
            print('#bunion {}'.format(bunion))
            print('#blist {}  bsteps {}  reqs {}  rem {}'.format(blist,bsteps,reqs,rem))

        if len(bsteps)==0:
            self._wait(rem)
            return

        breps = []
        nreps = 0
        for i in range(1,len(bsteps)):
            if bsteps[i]==bsteps[i-1] and reqs[i]==reqs[i-1]:
                nreps += 1
            else:
                breps.append(nreps)
                nreps = 0
        breps.append(nreps)

        i = 0
        j = 0
        for r in breps:
            if r > 0:
                del bsteps[j:j+r]
                del reqs  [j:j+r]
                if verbose:
                    print('#del [{}:{}]'.format(j,j+r))
                    print('#bsteps {}'.format(bsteps))
                    print('#reqs   {}'.format(reqs))
            j += 1

        if verbose:
            print('#breps  {}'.format(breps))
            print('#bsteps {}'.format(bsteps))
            print('#reqs   {}'.format(reqs))

        for i,n in enumerate(breps):
            if n > 0:
                self.instr.append('# loop: req {} of step {} and repeat {}'.format(reqs[i],bsteps[i],n))
                self.instr.append('start = len(instrset)')
                if bsteps[i]>0:
                    self._wait(bsteps[i])
                if self.charge is not None:
                    self.instr.append('instrset.append( BeamRequest({}) )'.format(self.charge))
                else:
                    self.instr.append('instrset.append( ControlRequest({}) )'.format([0] if self.merge else reqs[i]))
                self.ninstr += 1
                self.instr.append('instrset.append( Branch.conditional(start, 0, {}) )'.format(n))
                self.ninstr += 1
            else:
                if bsteps[i]>0:
                    self._wait(bsteps[i])
                if self.charge is not None:
                    self.instr.append('instrset.append( BeamRequest({}) )'.format(self.charge))
                else:
                    self.instr.append('instrset.append( ControlRequest({}) )'.format([0] if self.merge else reqs[i]))
                self.ninstr += 1

        if rem > 0:
            if resync:
                for k,v in FixedIntvsDict.items():
                    if period==v['intv'] and start<rem:
                        print(f'PeriodicGenerator: Filling remainder {rem} with sync to {k}, start {start}, period {period}')
                        self.instr.append(f'instrset.append( Wait(marker="{k}",occ=1) )')
                        return True
            self._wait(rem)

        return False


# ============================================================
# traingenerator (was xpm_seq/traingenerator.py)
# ============================================================

class TrainGenerator(object):
    COUNT_RANGE=1024

    def __init__(self, start_bucket=0,
                 train_spacing=TPGSEC,
                 bunch_spacing=1, bunches_per_train=1,
                 charge=0, repeat=0, notify=False,
                 rrepeat=False, rpad=None):
        self.start_bucket      = start_bucket
        self.train_spacing     = train_spacing
        self.bunch_spacing     = bunch_spacing
        self.bunches_per_train = bunches_per_train
        self.request           = 'ControlRequest([0])' if charge is None else 'BeamRequest({})'.format(charge)
        self.repeat            = repeat
        self.notify            = notify
        self.rrepeat           = rrepeat
        self.rpad              = rpad
        self.async_start       = None if repeat else 0

        self.instr = ['instrset = []']
        self._fill_instr()

    def _train(self, cc):
        intb = self.bunch_spacing
        nb   = self.bunches_per_train
        w    = 0
        self.instr.append('#   {} bunches / _train'.format(nb))
        self.instr.append('instrset.append({})'.format(self.request))

        rb = nb-1
        if rb:
            if rb > 0xfff:
                self.instr.append('iinstr=len(instrset)')
                self._wait(intb)
                self.instr.append('instrset.append({})'.format(self.request))
                self.instr.append('instrset.append(Branch.conditional(line=iinstr,counter={},value={}))'.format(cc[0],0xfff))
                self.instr.append('instrset.append(Branch.conditional(line=iinstr,counter={},value={}))'.format(cc[1],(rb//0x1000) -1))
                rb = rb & 0xfff

            if rb:
                self.instr.append('iinstr=len(instrset)')
                self._wait(intb)
                self.instr.append('instrset.append({})'.format(self.request))
                if rb > 1:
                    self.instr.append('instrset.append(Branch.conditional(line=iinstr,counter={},value={}))'.format(cc[0],rb-1))
            w = intb*(nb-1)
        return w

    def _wait(self, intv):
        if intv <= 0:
            raise ValueError(f'Calculated wait interval is {intv}')
        if intv >= 0xfff:
            self.instr.append('iinstr = len(instrset)')
            self.instr.append('instrset.append( FixedRateSync(marker="910kH", occ=4095) )')
            if intv >= 0x1ffe:
                self.instr.append('instrset.append( Branch.conditional(line=iinstr, counter=3, value={}) )'.format(int(intv/0xfff)-1))

        rint = intv%0xfff
        if rint:
            self.instr.append('instrset.append( FixedRateSync(marker="910kH", occ={} ) )'.format(rint))

    def _trains(self,intv,nint):
        rint = nint % self.COUNT_RANGE
        if rint:
            self.instr.append('# loop A: {} _trains'.format(rint))
            self.instr.append('startreq = len(instrset)')
            self._wait(intv-self._train([1,2]))
            if rint > 1:
                self.instr.append('instrset.append( Branch.conditional(startreq, 0, {}) )'.format(rint-1))
            self.instr.append('# end loop A')
            nint = nint - rint

        rint = (nint/self.COUNT_RANGE) % self.COUNT_RANGE
        if rint:
            self.instr.append('# loop B: {} _trains'.format(rint*self.COUNT_RANGE))
            self.instr.append('startreq = len(instrset)')
            self._wait(intv-self._train([1]))
            self.instr.append('instrset.append( Branch.conditional(startreq, 0, self.COUNT_RANGE-1) )')
            if rint > 1:
                self.instr.append('instrset.append( Branch.conditional(startreq, 2, {}) )'.format(rint-1))
            self.instr.append('# end loop B')
            nint = nint - rint*self.COUNT_RANGE

        rint = (nint / (self.COUNT_RANGE*self.COUNT_RANGE)) % self.COUNT_RANGE
        if rint:
            self.instr.append('# loop C: {} _trains'.format(rint*self.COUNT_RANGE*self.COUNT_RANGE))
            self.instr.append('# loop (n_trains / self.COUNT_RANGE)')
            self.instr.append('startreq = len(instrset)')
            self._wait(intv-self._train([3]))
            self.instr.append('instrset.append( Branch.conditional(line=startreq, counter=2, value=self.COUNT_RANGE-1) )')
            self.instr.append('instrset.append( Branch.conditional(line=startreq, counter=1, value=self.COUNT_RANGE-1) )')
            if rint > 1:
                self.instr.append('instrset.append( Branch.conditional(line=startreq, counter=0, value={}) )'.format(rint-1))
            self.instr.append('# end loop C')
            nint = nint - rint*self.COUNT_RANGE*self.COUNT_RANGE


    def _fill_instr(self):
        intv = self.train_spacing

        if self.start_bucket>0:
            self.instr.append('# start at bucket {}'.format(self.start_bucket))
            self._wait(self.start_bucket)

        self.instr.append('first = len(instrset)')

        if self.repeat < 0:
            len = self._train([1,2])
            self._wait(intv-len)
            self.instr.append('instrset.append( Branch.unconditional(first) )')
        else:
            if self.repeat > 0:
                self._trains(intv,self.repeat)
            if self.notify:
                self.instr.append('instrset.append( CheckPoint() )')
            if self.rrepeat:
                if self.rpad:
                    self._wait(self.rpad)
                self.instr.append('instrset.append( Branch.unconditional(first) )')
            else:
                self.instr.append('last = len(instrset)')
                self.instr.append('instrset.append( FixedRateSync(marker="1H",occ=1) )')
                self.instr.append('instrset.append( Branch.unconditional(last) )')


# ============================================================
# cli helpers — _build_script, ratecalc, generate, validate
# ============================================================

_PSDAQ_IMPORT = "from psdaq.seq.seq import *"


def _build_script(seqcodes, instr_lines):
    lines = []
    lines.append(_PSDAQ_IMPORT)
    lines.append("")
    lines.append(f"seqcodes = {seqcodes!r}")
    lines.append("")
    for line in instr_lines:
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


# --- ratecalc subcommand ---

def _add_ratecalc_parser(sub):
    p = sub.add_parser(
        "ratecalc",
        help="XPM timing rate calculator.",
        description="Convert Hz to bucket periods and enumerate exact sub-harmonic rates.",
    )
    p.add_argument(
        "rates", nargs="*", type=float, metavar="RATE_HZ",
        help="One or more target rates in Hz to look up.",
    )
    p.add_argument(
        "--period", type=int, action="append", default=None,
        help="Reverse lookup: convert a bucket period to Hz. May be repeated.",
    )
    p.add_argument(
        "--list", action="store_true",
        help="Show all 100 exact sub-harmonic rates.",
    )
    p.add_argument(
        "--json", dest="use_json", action="store_true",
        help="Output structured JSON.",
    )
    p.set_defaults(func=_ratecalc_run)


def _ratecalc_run(args):
    if not args.rates and not args.period and not args.list:
        print("Error: must specify rates, --period, or --list.", file=sys.stderr)
        return 1

    results = {}

    if args.rates:
        rate_results = []
        for rate_hz in args.rates:
            period = hz_to_period(rate_hz)
            actual_hz = period_to_hz(period)
            error_pct = (actual_hz - rate_hz) / rate_hz * 100
            is_exact = TPGSEC % period == 0
            entry = {
                "requested_hz": rate_hz,
                "period": period,
                "actual_rate_hz": round(actual_hz, 2),
                "error_pct": round(error_pct, 4),
                "exact_subharmonic": is_exact,
            }
            rate_results.append(entry)
        results["rates"] = rate_results

    if args.period:
        period_results = []
        for period in args.period:
            actual_hz = period_to_hz(period)
            is_exact = TPGSEC % period == 0
            entry = {
                "period": period,
                "actual_rate_hz": round(actual_hz, 2),
                "exact_subharmonic": is_exact,
            }
            period_results.append(entry)
        results["periods"] = period_results

    if args.list:
        subharmonics = all_subharmonics()
        sub_list = []
        for period in subharmonics:
            actual_hz = period_to_hz(period)
            sub_list.append({
                "period": period,
                "rate_hz": round(actual_hz, 2),
            })
        results["subharmonics"] = sub_list

    if args.use_json:
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _ratecalc_print_human(results)

    return 0


def _ratecalc_print_human(results):
    if "rates" in results:
        print(f"{'Requested Hz':>14s}  {'Period':>6s}  {'Actual Hz':>12s}  {'Error %':>8s}  {'Exact':>5s}")
        print("-" * 52)
        for r in results["rates"]:
            exact_str = "yes" if r["exact_subharmonic"] else "no"
            print(f"{r['requested_hz']:14.1f}  {r['period']:6d}  {r['actual_rate_hz']:12.2f}  {r['error_pct']:+8.4f}  {exact_str:>5s}")
        print()

    if "periods" in results:
        print(f"{'Period':>6s}  {'Actual Hz':>12s}  {'Exact':>5s}")
        print("-" * 28)
        for r in results["periods"]:
            exact_str = "yes" if r["exact_subharmonic"] else "no"
            print(f"{r['period']:6d}  {r['actual_rate_hz']:12.2f}  {exact_str:>5s}")
        print()

    if "subharmonics" in results:
        print(f"All {len(results['subharmonics'])} exact sub-harmonic rates of {TPGSEC} buckets / {FRAME_PERIOD_SEC}s:")
        print(f"{'Period':>8s}  {'Rate Hz':>12s}")
        print("-" * 23)
        for s in results["subharmonics"]:
            print(f"{s['period']:8d}  {s['rate_hz']:12.2f}")
        print()


# --- generate subcommand ---

def _add_generate_parser(sub):
    p = sub.add_parser(
        "generate",
        help="Generate XPM timing sequence scripts.",
    )
    gsub = p.add_subparsers(dest="gen_command", help="Generator type")
    gsub.required = True

    # periodic
    p_periodic = gsub.add_parser(
        "periodic",
        help="Generate periodic sequences via PeriodicGenerator.",
    )
    rate_group = p_periodic.add_mutually_exclusive_group()
    rate_group.add_argument(
        "--rates", nargs="+", type=float, metavar="HZ",
        help="Target rates in Hz (converted to bucket periods).",
    )
    rate_group.add_argument(
        "--periods", nargs="+", type=int, metavar="PERIOD",
        help="Bucket periods directly.",
    )
    p_periodic.add_argument(
        "--start", nargs="+", type=int, default=None,
        help="Starting bucket offsets (default: all 0).",
    )
    p_periodic.add_argument(
        "--descriptions", nargs="+", type=str, required=True,
        help="Description for each event code.",
    )
    p_periodic.add_argument(
        "--repeat", type=int, default=-1,
        help="Number of repeats (-1 = infinite, default: -1).",
    )
    p_periodic.add_argument(
        "--marker", type=str, default=None,
        help="Sync marker (default: 910kH).",
    )
    p_periodic.add_argument(
        "--merge", action="store_true",
        help="Merge all triggers onto one event code.",
    )
    p_periodic.add_argument(
        "--no-resync", action="store_true",
        help="Disable resync marker at end of period.",
    )
    p_periodic.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output file (default: stdout).",
    )
    p_periodic.add_argument(
        "--json", dest="use_json", action="store_true",
        help="Emit JSON summary to stderr.",
    )
    p_periodic.set_defaults(func=_generate_run)

    # train
    p_train = gsub.add_parser(
        "train",
        help="Generate train sequences via TrainGenerator.",
    )
    p_train.add_argument(
        "--train-spacing", type=int, required=True,
        help="Buckets between start of each train.",
    )
    p_train.add_argument(
        "--bunch-spacing", type=int, required=True,
        help="Buckets between bunches within a train.",
    )
    p_train.add_argument(
        "--bunches-per-train", type=int, required=True,
        help="Number of bunches in each train.",
    )
    p_train.add_argument(
        "--start-bucket", type=int, default=0,
        help="Starting bucket for first train (default: 0).",
    )
    p_train.add_argument(
        "--charge", type=int, default=None,
        help="Bunch charge in pC (default: None = ControlRequest).",
    )
    p_train.add_argument(
        "--repeat", type=int, default=0,
        help="Number of repeats (0 = no repeat, -1 = infinite, default: 0).",
    )
    p_train.add_argument(
        "--notify", action="store_true",
        help="Assert SeqDone PV when repeats are finished.",
    )
    p_train.add_argument(
        "--description", type=str, required=True,
        help="Description for the event code.",
    )
    p_train.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output file (default: stdout).",
    )
    p_train.add_argument(
        "--json", dest="use_json", action="store_true",
        help="Emit JSON summary to stderr.",
    )
    p_train.set_defaults(func=_generate_run)


def _generate_run(args):
    if args.gen_command == "periodic":
        return _do_periodic(args)
    elif args.gen_command == "train":
        return _do_train(args)
    return 1


def _do_periodic(args):
    if args.rates and args.periods:
        print("Error: --rates and --periods are mutually exclusive.", file=sys.stderr)
        return 1
    if not args.rates and not args.periods:
        print("Error: must specify --rates or --periods.", file=sys.stderr)
        return 1

    if args.rates:
        periods = [hz_to_period(r) for r in args.rates]
    else:
        periods = args.periods

    if args.start:
        start = args.start
    else:
        start = [0] * len(periods)

    if len(start) != len(periods):
        print("Error: --start must have same number of values as rates/periods.",
              file=sys.stderr)
        return 1

    if not args.descriptions or len(args.descriptions) != len(periods):
        print("Error: --descriptions must have same number of values as rates/periods.",
              file=sys.stderr)
        return 1

    seqcodes = {i: desc for i, desc in enumerate(args.descriptions)}

    gen = PeriodicGenerator(
        period=periods,
        start=start,
        repeat=args.repeat,
        marker=args.marker,
        merge=args.merge,
        resync=not args.no_resync,
    )

    script = _build_script(seqcodes, gen.instr)

    if args.output:
        with open(args.output, "w") as f:
            f.write(script)
    else:
        print(script)

    if args.use_json:
        lcm_period = int(numpy.lcm.reduce(periods))
        actual_rates = [round(period_to_hz(p), 2) for p in periods]
        summary = {
            "generator": "periodic",
            "instruction_count": gen.ninstr,
            "periods": periods,
            "lcm_period": lcm_period,
            "actual_rates_hz": actual_rates,
            "descriptions": args.descriptions,
        }
        if args.output:
            summary["output_file"] = args.output
        json.dump(summary, sys.stderr, indent=2)
        sys.stderr.write("\n")

    return 0


def _do_train(args):
    seqcodes = {0: args.description}

    gen = TrainGenerator(
        start_bucket=args.start_bucket,
        train_spacing=args.train_spacing,
        bunch_spacing=args.bunch_spacing,
        bunches_per_train=args.bunches_per_train,
        charge=args.charge,
        repeat=args.repeat,
        notify=args.notify,
    )

    script = _build_script(seqcodes, gen.instr)

    if args.output:
        with open(args.output, "w") as f:
            f.write(script)
    else:
        print(script)

    if args.use_json:
        summary = {
            "generator": "train",
            "instruction_count": len(gen.instr) - 1,
            "train_spacing": args.train_spacing,
            "bunch_spacing": args.bunch_spacing,
            "bunches_per_train": args.bunches_per_train,
            "start_bucket": args.start_bucket,
            "repeat": args.repeat,
            "description": args.description,
        }
        if args.output:
            summary["output_file"] = args.output
        json.dump(summary, sys.stderr, indent=2)
        sys.stderr.write("\n")

    return 0


# --- validate subcommand ---

_VALIDATE_BASE_RATE_HZ = TPGSEC / 0.98


def _add_validate_parser(sub):
    p = sub.add_parser(
        "validate",
        help="Validate an XPM timing sequence script via headless simulation.",
    )
    p.add_argument(
        "script", type=str,
        help="Path to the .py sequence script to validate.",
    )
    p.add_argument(
        "--time", nargs=2, type=float, default=[0, 0.98], metavar=("START", "STOP"),
        help="Simulation window in seconds (default: 0 0.98).",
    )
    p.add_argument(
        "--engine", type=int, default=0,
        help="Engine number for event code offset (default: 0).",
    )
    p.add_argument(
        "--json", dest="use_json", action="store_true",
        help="Output results as JSON.",
    )
    p.set_defaults(func=_validate_run)


def _validate_counters(instrset, filename):
    warnings = []

    d = {cc: [] for cc in range(Instruction.maxcc)}
    for line, instr in enumerate(instrset):
        if instr.args[0] == Branch.opcode and len(instr.args) > 2:
            cc = instr.args[2]
            addr = instr.args[1]
            d[cc].append([addr, line])

    for cc in range(Instruction.maxcc):
        for r in d[cc]:
            addr = r[0]
            for s in d[cc]:
                if addr > s[0] and addr < s[1]:
                    warnings.append(
                        f"CC {cc} found in overlapping loops {r} {s}"
                    )

    return warnings


def _validate_run(args):
    try:
        instrset, seqcodes = load_script(args.script)
    except Exception as e:
        print(f"Error loading script: {e}", file=sys.stderr)
        return 1

    expanded = preproc(instrset)

    instr_count = len(expanded)
    instr_limit = 2048
    warnings = []
    if instr_count > instr_limit:
        warnings.append(
            f"Instruction count {instr_count} exceeds limit {instr_limit}"
        )

    counter_warnings = _validate_counters(expanded, args.script)
    warnings.extend(counter_warnings)

    start_sec, stop_sec = args.time
    start_frame = int(start_sec * TPGSEC / 0.98)
    stop_frame = int(stop_sec * TPGSEC / 0.98)

    events = HeadlessSimulator.simulate(expanded, start_frame, stop_frame)

    sim_duration_sec = stop_sec - start_sec
    event_code_base = 256 + args.engine * 4

    event_results = {}
    for bit in sorted(events.keys()):
        count = len(events[bit])
        rate_hz = round(count / sim_duration_sec, 2) if sim_duration_sec > 0 else 0
        desc = seqcodes.get(bit, "")
        event_results[bit] = {
            "count": count,
            "rate_hz": rate_hz,
            "description": desc,
            "event_code": event_code_base + bit,
        }

    valid = len(warnings) == 0

    if args.use_json:
        output = {
            "script": args.script,
            "instruction_count": instr_count,
            "instruction_limit": instr_limit,
            "simulation_time_sec": sim_duration_sec,
            "event_codes": {str(bit): info for bit, info in event_results.items()},
            "warnings": warnings,
            "valid": valid,
        }
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Script: {args.script}")
        print(f"Instructions: {instr_count} / {instr_limit}")
        print(f"Simulation: {start_sec}s - {stop_sec}s ({sim_duration_sec}s)")
        print()

        if event_results:
            print(f"{'Bit':>4}  {'EvtCode':>7}  {'Count':>8}  {'Rate (Hz)':>12}  Description")
            print(f"{'---':>4}  {'-------':>7}  {'-----':>8}  {'---------':>12}  -----------")
            for bit, info in event_results.items():
                print(
                    f"{bit:>4}  {info['event_code']:>7}  "
                    f"{info['count']:>8}  {info['rate_hz']:>12.2f}  "
                    f"{info['description']}"
                )
        else:
            print("No event codes fired during simulation window.")

        print()
        if warnings:
            print("Warnings:")
            for w in warnings:
                print(f"  - {w}")
            print()

        print(f"Valid: {'YES' if valid else 'NO'}")

    return 0


# ============================================================
# main — unified CLI entry point
# ============================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="xpm-seq",
        description="LCLS-II XPM timing sequence CLI (ratecalc / generate / validate).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_ratecalc_parser(sub)
    _add_generate_parser(sub)
    _add_validate_parser(sub)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
