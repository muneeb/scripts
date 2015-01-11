#!/usr/bin/python

import os
import struct
import locale
import fcntl
import time

import subprocess
import sys

from optparse import OptionParser
from io import BlockingIOError

def enum(**enums):
    return type('Enum', (), enums)

ENUMS = enum(PRT_COMM_SEND=1, PRT_COMM_RECV=2, \
               HWPF_ON=0, LLC_HWPF_OFF=1, HWPF_OFF=2, \
               SWPF_8MBLLC=1, SWPF_6MBLLC=2, SWPF_4MBLLC=3, \
               SWPF_2MBLLC=4, SWPF_1MBLLC=5, SWPF_0MBLLC=6, SWPF_JIT_ACTIVE=7,\
               NO_REVERT_TO_PREV=0, REVERT_TO_PREV=1, REVERT_TO_ORIG=2)

#4:["hwpf", "swpf", "l1hwpfswpf", "hwpfswpf", "nopref"],
EXP_PLAN = {4:["hwpf", "swpf", "l1hwpfswpf", "hwpfswpf"], \
            3:["hwpf", "l1hwpfswpf", "swpf", "hwpfswpf"], \
            2:["hwpf", "hwpfswpf", "swpf", "l1hwpfswpf"],\
            1:["hwpf", "hwpfswpf", "l1hwpfswpf"]}

PERF_BOOK = {"hwpf":1}

AVG_PERF_BOOK = {}
MON_WIN_BOOK = {}

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
                          type="float", default="0.05",
                          dest="SLEEP_TIME",
                          help="Sleep time in milli-seconds")
        parser.add_option("-r", "--reexplore-in",
                        type="int", default="5",
                        dest="REEXP_TIME",
                        help="Start re-exploration of best prefetch policy in XXX seconds")
        parser.add_option("-p", "--rep-reexplore",
                          type="int", default="10",
                          dest="REP_REEXP",
                          help="Repead re-exploration this many times")
        parser.add_option("-w", "--num-mon-win",
                          type="int", default="10",
                          dest="NUM_MON_WIN",
                          help="Number of performance windows to monitor for each policy")
        parser.add_option("-e", "--mon-epoch",
                        type="float", default="0.5",
                        dest="MON_EPOCH",
                        help="Duration of monitor epoch for each policy")
        parser.add_option("-x", "--exit-after",
                        type="int", default="65",
                        dest="EXIT_AFTER",
                        help="Exit after XXX seconds of applying the optimal policy")
        parser.add_option("-t", "--retries",
                          type="int", default="5",
                          dest="RETRIES",
                          help="Number of retries to important prefetch policies")

        (opts, args) = parser.parse_args()
        
        
        self.STRUCT_FMTSTR="iiiiifffffiii"
        self.ENABLED_SWPF = False
        self.curr_policy="hwpf"
        self.baseline = "hwpf"
        self.max_perf_policy="hwpf"
        self.max_thruput=1.0
        self.start_time = time.time()

        self.BUF_SIZE = opts.BUF_SIZE
        self.NUM_APPS = opts.NUM_APPS
        self.SLEEP_TIME = opts.SLEEP_TIME
        self.REEXP_TIME = opts.REEXP_TIME
        self.NUM_MON_WIN = opts.NUM_MON_WIN
        self.EXIT_AFTER= opts.EXIT_AFTER
        self.RETRIES = opts.RETRIES
        self.REP_REEXP = opts.REP_REEXP
        self.MON_EPOCH = opts.MON_EPOCH
        self.curr_ws = 1
        self.falsepos_count = 0
        self.falsepos_thr= 4
        self.win_policies = []
        self.backoff_reexp_time = self.REEXP_TIME

        self.rp = os.open("/tmp/PRT_POL_MAN_RECV", os.O_RDONLY)
        fl = fcntl.fcntl(self.rp, fcntl.F_GETFL)
        fcntl.fcntl(self.rp, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        self.rp_app = []
        self.wp = []
    
        for core_idx in range(self.NUM_APPS):
        
            self.rp_app.append(os.open("/tmp/PRT_SND_INFO_%d"%(core_idx), os.O_RDONLY))
            self.wp.append(os.open("/tmp/PRT_RECV_INFO_%d"%(core_idx), os.O_WRONLY ))
            
            fl = fcntl.fcntl(self.rp_app[core_idx], fcntl.F_GETFL)
            fcntl.fcntl(self.rp_app[core_idx], fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            fl = fcntl.fcntl(self.wp[core_idx], fcntl.F_GETFL)
            fcntl.fcntl(self.wp[core_idx], fcntl.F_SETFL, fl | os.O_NONBLOCK)

def nonblocking_readlines(fd, conf):

    os.lseek(fd, 0, os.SEEK_SET)

    buf = bytearray()
    remaining_bytes = conf.BUF_SIZE
    
    while remaining_bytes > 0:
        try:
            block = os.read(fd, conf.BUF_SIZE) #read BUF_SIZE-byte chunks at a time
        #deleteContent(fd)
        except BlockingIOError:
            None
        
        remaining_bytes -= len(block)
        
        #print >> sys.stderr, "data is %d Bytes"%(len(block))
        
        if not block:
            if buf:
                buf.clear()
            return None
        
        buf.extend(block)

        if remaining_bytes > 0:
            time.sleep(conf.SLEEP_TIME)
        
    return buf

def send_data(fd, snd_data):
    deleteContent(fd)
    os.write(fd, snd_data)

def deleteContent(fd):
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)

def compute_weighted_speedup(bpc_list, conf):

    hwpf_bpc_list = AVG_PERF_BOOK["hwpf"]
    ws = 0.0

    for idx in range(conf.NUM_APPS):
        ws += float(bpc_list[idx])/float(hwpf_bpc_list[idx])

    return float(ws)/float(conf.NUM_APPS)

def monitor_perf(policy, mon_time, conf):

    print >> sys.stderr, "POLMAN -- monitoring performance for policy %s"%(policy)

    i=0

    core_id = [0,1,2,3]
    bpc = [0,0,0,0]
    
    num_mon_wins = mon_time / conf.SLEEP_TIME

    while i < num_mon_wins: #conf.NUM_MON_WIN:

        data = nonblocking_readlines(conf.rp, conf)
        
        if not data:
            continue
        
        (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(conf.STRUCT_FMTSTR, data)

        bpc[0] += bpc0
        bpc[1] += bpc1
        bpc[2] += bpc2
        bpc[3] += bpc3
        
        #print >> sys.stderr, "%f -- %f %f %f %f"%(time.time()-conf.start_time, bpc0, bpc1, bpc2, bpc3)
        
        i += 1
        time.sleep(conf.SLEEP_TIME)

    #revert immediately do default once performance has been recorded
    #if policy != "hwpf":
    #    ready_this_policy("hwpf", conf)

    #average recorded bpc
    for idx in range(conf.NUM_APPS):
        bpc[idx] = float(bpc[idx])/float(num_mon_wins)#conf.NUM_MON_WIN)
    #print >> sys.stderr, "bpc[%d] -- %f"%(idx,bpc[idx])

    if policy in AVG_PERF_BOOK:
        for idx in range(conf.NUM_APPS):
            AVG_PERF_BOOK[policy][idx] += bpc[idx]
    else:
        AVG_PERF_BOOK[policy] = bpc

def wait_for_JIT(conf, revert):

    print >> sys.stderr, "POLMAN -- Waiting for %d JIT instances to complete"%(len(conf.rp_app))

    for fd in conf.rp_app:
        while True:
            data = nonblocking_readlines(fd, conf)
            if not data:
                time.sleep(conf.SLEEP_TIME)
                continue
            (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(conf.STRUCT_FMTSTR, data)
            
            if not revert and swpf_status == ENUMS.SWPF_JIT_ACTIVE:
                break
            elif revert and swpf_status == 0:
                break
            time.sleep(conf.SLEEP_TIME)

def wait_for_hwpf_throttle(hwpf_change_to, conf):

    print >> sys.stderr, "POLMAN -- waiting for HWPF to change to %d"%(hwpf_change_to)

    fd = conf.rp

    while True:
        data = nonblocking_readlines(fd, conf)
        if not data:
            time.sleep(conf.SLEEP_TIME)
            continue
        (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(conf.STRUCT_FMTSTR, data)
        
        if hwpf_status == hwpf_change_to:
            break
        time.sleep(conf.SLEEP_TIME)

def ready_this_policy(policy, conf):

    print >> sys.stderr, "\n----------------------------"
    print >> sys.stderr, "POLMAN -- readying policy %s"%(policy)
    
    
    conf.ENABLED_SWPF = False

    hwpf_change_to = ENUMS.HWPF_ON

    if policy == "hwpf":
        
        rev = ENUMS.REVERT_TO_ORIG
        if conf.curr_policy == "hwpf" or conf.curr_policy == "nopref":
            rev = ENUMS.NO_REVERT_TO_PREV
        
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                                            0.0, 0.0, 0.0, 0.0, 0.0, \
                                            ENUMS.HWPF_ON, 0, rev)
    elif policy == "swpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                             0.0, 0.0, 0.0, 0.0, 0.0, \
                             ENUMS.HWPF_OFF, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)
            
        hwpf_change_to = ENUMS.HWPF_OFF

    elif policy == "l1hwpfswpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.LLC_HWPF_OFF, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)

        hwpf_change_to = ENUMS.LLC_HWPF_OFF

    elif policy == "hwpfswpf":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.HWPF_ON, ENUMS.SWPF_8MBLLC, ENUMS.NO_REVERT_TO_PREV)

        hwpf_change_to = ENUMS.HWPF_ON

    elif policy == "nopref":
        snd_data = struct.pack("iiiiifffffiii", ENUMS.PRT_COMM_RECV, 0, 1, 2, 3, \
                               0.0, 0.0, 0.0, 0.0, 0.0, \
                               ENUMS.HWPF_OFF, 0, ENUMS.REVERT_TO_ORIG)

        hwpf_change_to = ENUMS.HWPF_OFF
    
    for fd in conf.wp:
        send_data(fd, snd_data)

    revert = False
    if (conf.curr_policy == "hwpf" or conf.curr_policy == "nopref") and policy != conf.curr_policy:
        conf.ENABLED_SWPF = True
    elif (conf.curr_policy != "hwpf" and conf.curr_policy != "nopref") and policy != conf.curr_policy:
        revert = True

    if conf.ENABLED_SWPF:
        wait_for_JIT(conf, revert)
    elif revert:
        wait_for_JIT(conf, revert)

    wait_for_hwpf_throttle(hwpf_change_to, conf)

    conf.curr_policy = policy

    print >> sys.stderr, "POLMAN -- policy %s is ready on all cores at %f seconds"%(policy, time.time() - conf.start_time)

def reset_AVG_PERF_BOOK():

    for policy in AVG_PERF_BOOK:
        AVG_PERF_BOOK[policy] = [0.0, 0.0, 0.0, 0.0]

def reexplore_winning(conf):
    
    print >> sys.stderr, "POLMAN -- starting Re-exploration at %f seconds"%(time.time() - conf.start_time)

    curr_max_perf_policy = conf.max_perf_policy

    conf.max_perf_policy = conf.baseline
    conf.max_thruput = 1.0

    total_states = len(EXP_PLAN[conf.NUM_APPS])
    
    num_mon_wins = int(conf.MON_EPOCH / conf.SLEEP_TIME)
    
    retries = 0
    
    while retries < conf.RETRIES:
    
        reset_AVG_PERF_BOOK()
    
        for rep_idx in range(num_mon_wins):
            
            #ready_this_policy(conf.baseline, conf)
            #monitor_perf(conf.baseline, conf.SLEEP_TIME, conf)
            
            for exp_plan_idx in range(total_states):
                
                policy = EXP_PLAN[conf.NUM_APPS][exp_plan_idx]
                ready_this_policy(policy, conf)
                monitor_perf(EXP_PLAN[conf.NUM_APPS][exp_plan_idx], conf.SLEEP_TIME, conf)

        for policy in EXP_PLAN[conf.NUM_APPS]:
            
            if policy == "hwpf":
                continue
                
            bpc_list = AVG_PERF_BOOK[policy]
            ws = compute_weighted_speedup(bpc_list, conf)
            PERF_BOOK[policy] = ws
            
            if ws > conf.max_thruput:
                conf.max_thruput = ws
                conf.max_perf_policy = policy

            print >> sys.stderr, "policy %s -- weighted speedup %f"%(policy, ws)

        retries += 1
        if conf.max_perf_policy != conf.baseline:
            break

#    if curr_max_perf_policy == conf.max_perf_policy:
#        if conf.backoff_reexp_time < 15:
#            conf.backoff_reexp_time += conf.REEXP_TIME
#    else:
#        conf.backoff_reexp_time = conf.REEXP_TIME

    conf.curr_ws = conf.max_thruput

    conf.REP_REEXP -= 1

def explore_policies(conf):

    total_states = len(EXP_PLAN[conf.NUM_APPS])

    num_mon_wins = int(conf.MON_EPOCH / conf.SLEEP_TIME)

    conf.max_perf_policy = conf.baseline
    conf.max_thruput = 1.0

    retries = 0

    while retries < conf.RETRIES:

        reset_AVG_PERF_BOOK()

        for rep_idx in range(num_mon_wins):

            #ready_this_policy(conf.baseline, conf)
            #monitor_perf(conf.baseline, conf.SLEEP_TIME, conf)

            for exp_plan_idx in range(total_states):
                
                policy = EXP_PLAN[conf.NUM_APPS][exp_plan_idx]
                ready_this_policy(policy, conf)
                monitor_perf(EXP_PLAN[conf.NUM_APPS][exp_plan_idx], conf.SLEEP_TIME, conf)

        for policy in EXP_PLAN[conf.NUM_APPS]:

            if policy == "hwpf":
                continue
        
            bpc_list = AVG_PERF_BOOK[policy]
            ws = compute_weighted_speedup(bpc_list, conf)
            PERF_BOOK[policy] = ws
                
            if ws > conf.max_thruput:
                conf.max_thruput = ws
                conf.max_perf_policy = policy
            
            print >> sys.stderr, "policy %s -- weighted speedup %f"%(policy, ws)

        retries += 1
        if conf.max_perf_policy != conf.baseline:
            break

    conf.curr_ws = conf.max_thruput

def monitor_best_policy(conf):

    mon_list = [conf.baseline, conf.max_perf_policy]
    total_states = len(mon_list)
    
    num_mon_wins = int(conf.MON_EPOCH / conf.SLEEP_TIME)

    reset_AVG_PERF_BOOK()

    for rep_idx in range(num_mon_wins):
        
        for exp_plan_idx in range(total_states):
            
            policy = mon_list[exp_plan_idx]
            ready_this_policy(policy, conf)
            monitor_perf(policy, conf.SLEEP_TIME, conf)

    bpc_list = AVG_PERF_BOOK[conf.max_perf_policy]
    ws = compute_weighted_speedup(bpc_list, conf)
    PERF_BOOK[conf.max_perf_policy] = ws
        
    if ws > conf.max_thruput:
        conf.max_thruput = ws
    
    conf.curr_ws = ws

    if conf.curr_ws < 1.0:
        conf.falsepos_count += 1
    else:
        conf.falsepos_count -= 1

    ready_this_policy(conf.max_perf_policy, conf)

    print >> sys.stderr, "policy %s -- weighted speedup %f"%(policy, ws)

def main():
    
    start_time = time.time()
    
    time.sleep(1)
    conf = Conf()
    conf.start_time = start_time
    #ignore the first 10 seconds
    time.sleep(9)

    exp_plan_idx = 0

    total_states = len(EXP_PLAN[conf.NUM_APPS])

    while True:
    
        print >> sys.stderr, "POLMAN -- entering exploration phase"
    
        time.sleep(conf.SLEEP_TIME) # sleep for 100 milli-seconds -- 2X the protean runtime
        
        #retries = 0
        #while retries < conf.RETRIES and conf.max_perf_policy != policy:
        explore_policies(conf)

        #apply policy with max performance
        print >> sys.stderr, "POLMAN -- Applying best prefetching policy: %s"%(conf.max_perf_policy)
        ready_this_policy(conf.max_perf_policy, conf)

        #conf.RETRIES = 3

        time_passed = time.time() - conf.start_time

        re_explore_in = conf.REEXP_TIME + time_passed

        while conf.EXIT_AFTER > time_passed:

            print >> sys.stderr, "POLMAN -- re-explore in %f"%(re_explore_in - time_passed)
            
            if (re_explore_in - time_passed) < 0.1 and conf.REP_REEXP > 0:
                reexplore_winning(conf)
                #apply policy with max performance
                print >> sys.stderr, "POLMAN -- Applying best prefetching policy after re-exploration: %s"%(conf.max_perf_policy)
                ready_this_policy(conf.max_perf_policy, conf)
                time_passed = time.time() - conf.start_time
                re_explore_in = conf.backoff_reexp_time + time_passed
                conf.falsepos_count = 0
            
            if conf.curr_policy != conf.baseline:
                monitor_best_policy(conf)
                
                #If too many false positives occur, revert to baseline policy
                if conf.falsepos_count == conf.falsepos_thr:
                    ready_this_policy(conf.baseline, conf)
                    conf.falsepos_count = 0
                    re_explore_in = time_passed + 0 # restart re-exploration immediately
                    print >> sys.stderr, "POLMAN -- Reverting to baseline policy: %s"%(conf.baseline)
                    print >> sys.stderr, "POLMAN -- Starting Re-exploration soon..."
            else:
                sleep_for = re_explore_in - time_passed
                if sleep_for > 0:
                    time.sleep(sleep_for)
                #break

            if conf.REP_REEXP == 0:
                break

            time_passed = time.time() - conf.start_time

        break


if __name__ == '__main__':
    main()
