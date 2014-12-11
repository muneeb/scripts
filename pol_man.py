#!/usr/bin/python

import os
import struct
import locale
import fcntl
import time

from optparse import OptionParser

def enum(**enums):
    return type('Enum', (), enums)

ENUMS = enum(PRT_COMM_SEND=1, PRT_COMM_RECV=2, \
               HWPF_ON=0, LLC_HWPF_OFF=1, HWPF_OFF=2, \
               SWPF_8MBLLC=1, SWPF_6MBLLC=2, SWPF_4MBLLC=3, \
               SWPF_2MBLLC=4, SWPF_1MBLLC=5, SWPF_0MBLLC=6, SWPF_JIT_ACTIVE=7,\
               NO_REVERT_TO_PREV=0, REVERT_TO_PREV=1, REVERT_TO_ORIG=2)

BUF_SIZE=52
NUM_APPS=4
SLEEP_TIME=0.1  #100 milli-sec
NUM_MON_WIN=5
REEXP_TIME=1000
STRUCT_FMTSTR="iiiiifffffiii"
ENABLED_SWPF = False

PERF_BOOK = {"hwpf":1}
AVG_PERF_BOOK = {}
MON_WIN_BOOK = {}
curr_policy="hwpf"
max_perf_policy="hwpf"
max_thruput=1

EXP_PLAN = {4:["hwpf", "swpf", "l1hwpfswpf", "hwpfswpf", "nopref"], \
            3:["hwpf", "l1hwpfswpf", "swpf", "hwpfswpf", "nopref"], \
            2:["hwpf", "hwpfswpf", "swpf", "l1hwpfswpf"],\
            1:["hwpf", "hwpfswpf", "l1hwpfswpf"]}

class Conf:
    def __init__(self):
        
        parser = OptionParser("usage: %prog [OPTIONS...] INFILE")
        
        parser.add_option("-b", "--buf-size",
                          type="int", default="52",
                          dest="BUF_SIZE",
                          help="Size of structure communicated between runtime and policy manager")
        parser.add_option("-n", "--num-apps",
                        type="int", default="4",
                        dest="NUM_APPS",
                        help="Number of active cores. Total applications running")
        parser.add_option("-s", "--sleep",
                          type="float", default="0.1",
                          dest="SLEEP_TIME",
                          help="Sleep time in milli-seconds")
        parser.add_option("-r", "--reexplore-in",
                        type="int", default="1000",
                        dest="REEXP_TIME",
                        help="Start re-exploration of best prefetch policy in XXX seconds")
        parser.add_option("-w", "--num-mon-win",
                          type="int", default="5",
                          dest="NUM_MON_WIN",
                          help="Number of performance windows to monitor for each policy")

        (opts, args) = parser.parse_args()

        global BUF_SIZE
        global NUM_APPS
        global SLEEP_TIME
        global REEXP_TIME
        global NUM_MON_WIN

        BUF_SIZE = opts.BUF_SIZE
        NUM_APPS = opts.NUM_APPS
        SLEEP_TIME = opts.SLEEP_TIME
        REEXP_TIME = opts.REEXP_TIME
        NUM_MON_WIN = opts.NUM_MON_WIN

        self.rp = os.open("/tmp/PRT_POL_MAN_RECV", os.O_RDONLY )
        fl = fcntl.fcntl(self.rp, fcntl.F_GETFL)
        fcntl.fcntl(self.rp, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        self.rp_app = []
        self.wp = []
    
        for core_idx in range(NUM_APPS):
        
            self.rp_app.append(os.open("/tmp/PRT_SND_INFO_%d"%(core_idx), os.O_RDONLY ))
            self.wp.append(os.open("/tmp/PRT_RECV_INFO_%d"%(core_idx), os.O_WRONLY ))
            
            fl = fcntl.fcntl(self.rp_app[core_idx], fcntl.F_GETFL)
            fcntl.fcntl(self.rp_app[core_idx], fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            fl = fcntl.fcntl(self.wp[core_idx], fcntl.F_GETFL)
            fcntl.fcntl(self.wp[core_idx], fcntl.F_SETFL, fl | os.O_NONBLOCK)


def nonblocking_readlines(fd):

    os.lseek(fd, 0, os.SEEK_SET)

    buf = bytearray()
    remaining_bytes = BUF_SIZE
    
    while remaining_bytes > 0:
        try:
            block = os.read(fd, BUF_SIZE) #read BUF_SIZE-byte chunks at a time
        except BlockingIOError:
            print "No communication!"
        
        remaining_bytes -= len(block)
        
        print "data is %d Bytes"%(len(block))
        
        if not block:
            if buf:
                buf.clear()
            return buf
    
        buf.extend(block)

        if remaining_bytes > 0:
            time.sleep(0.05)
        
    return buf

def send_data(fd, snd_data):
    deleteContent(fd)
    os.write(fd, snd_data)

def deleteContent(fd):
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)

def compute_weighted_speedup(bpc_list):

    hwpf_bpc_list = AVG_PERF_BOOK["hwpf"]
    ws = 0

    for idx in range(NUM_APPS):
        ws += float(bpc_list[idx]/hwpf_bpc_list[idx])

    return float(ws)/float(NUM_APPS)

def monitor_perf(policy, conf):

    print "POLMAN -- monitoring performance for policy %s"%(policy)

    i=0

    core_id = [0,1,2,3]
    bpc = [0,0,0,0]

    while i < NUM_MON_WIN:

        data = nonblocking_readlines(conf.rp)
        
        if not data:
            continue
        
        (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(STRUCT_FMTSTR, data)

        bpc[0] += bpc0
        bpc[1] += bpc1
        bpc[2] += bpc2
        bpc[3] += bpc3

        i += 1
        time.sleep(SLEEP_TIME)

    #average recorded bpc
    for idx in range(NUM_APPS):
        bpc[idx] = float(bpc[idx])/float(NUM_MON_WIN)

    AVG_PERF_BOOK[policy] = bpc

    if policy != "hwpf":
        ws = compute_weighted_speedup(bpc)
        PERF_BOOK[policy] = ws

        if ws > max_thruput:
            max_thruput = ws
            max_perf_policy = policy

def wait_for_JIT(conf):

    for fd in conf.rp_app:
        while True:
            data = nonblocking_readlines(fd)
            if not data:
                time.sleep(1)
                continue
            (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(STRUCT_FMTSTR, data)

            if swpf_status == ENUMS.SWPF_JIT_ACTIVE:
                break
            time.sleep(1)

def ready_this_policy(policy, conf):

    print "POLMAN -- readying policy %s"%(policy)

    global ENABLED_SWPF

    if policy == "hwpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                                            0.0, 0.0, 0.0, 0.0, 0.0, \
                                            ENUMS.HWPF_ON, 0, ENUMS.REVERT_TO_ORIG)
        ENABLED_SWPF = False
    elif policy == "swpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                             0.0, 0.0, 0.0, 0.0, 0.0, \
                             ENUMS.HWPF_OFF, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)
        if not ENABLED_SWPF:
            ENABLED_SWPF = True
    elif policy == "l1hwpfswpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.LLC_HWPF_OFF, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)
        if not ENABLED_SWPF:
            ENABLED_SWPF = True
    elif policy == "hwpfswpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.HWPF_ON, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)
        if not ENABLED_SWPF:
            ENABLED_SWPF = True
    elif policy == "nopref":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.HWPF_OFF, 0, ENUMS.REVERT_TO_ORIG)
        ENABLED_SWPF = False
    
    for fd in conf.wp:
        send_data(fd, snd_data)

    if ENABLED_SWPF:
        wait_for_JIT(conf)

    print "POLMAN -- policy %s is ready on all cores"%(policy)

def main():

    #ignore the first 5 seconds
    time.sleep(0.5)

    conf = Conf()

    exp_plan_idx = 0

    total_states = len(EXP_PLAN[NUM_APPS][exp_plan_idx])

    while True:
    
        print "POLMAN -- entering exploration phase"
    
        time.sleep(SLEEP_TIME) # sleep for 100 milli-seconds -- 2X the protean runtime
        
        for exp_plan_idx in range(total_states):
        
            policy = EXP_PLAN[NUM_APPS][exp_plan_idx]
        
            ready_this_policy(policy, conf)

            monitor_perf(EXP_PLAN[NUM_APPS][exp_plan_idx], conf)

        #apply policy with max performance
        print "POLMAN -- Applying best prefetching policy: %s"%(max_perf_policy)
        ready_this_policy(max_perf_policy, conf)

        #sleep until next exploration phase
        time.sleep(REEXP_TIME)


if __name__ == '__main__':
    main()