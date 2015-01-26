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
            3:["hwpf", "l1hwpfswpf", "hwpfswpf", "swpf"], \
            2:["hwpf", "hwpfswpf", "l1hwpfswpf"],\
            1:["hwpf", "hwpfswpf", "l1hwpfswpf"]}

PERF_BOOK = {"hwpf":1}

AVG_PERF_BOOK = {}
MON_WIN_BOOK = {}

BPC_ACC_SCORE_POL = {}
BPC_SMP_COUNT = {}
TIME_ACC_BOOK = {}
OVERALL_PERF = []
WS_BOOK = []

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
                          type="int", default="20",
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
                          type="int", default="2",
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
        self.SLOWDOWN_QUOTA = 7.9
        self.REEXP_FAIL_THR = 4
        self.reexp_fail_count = 0
        self.consec_beating = 3
        self.curr_ws = 1
        self.falsepos_count = 0
        self.falsepos_thr= 3
        self.win_policies = []
        self.backoff_reexp_time = self.REEXP_TIME
        self.MON_BASELINE_AFTER_ITER = 4
        self.mon_baseline_after = self.MON_BASELINE_AFTER_ITER
        self.exp_overhead = 0.0

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

        empty_list = [0, 0, 0, 0]
        for policy in EXP_PLAN[self.NUM_APPS]:
            BPC_ACC_SCORE_POL[policy] = empty_list
            BPC_SMP_COUNT[policy] = 0
            TIME_ACC_BOOK[policy] = 0
            AVG_PERF_BOOK[policy] = [0, 0, 0, 0]

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

def policy_mon_duration(policy):

    if not policy in BPC_SMP_COUNT:
        return 0

    total = 0
    for pol in BPC_SMP_COUNT:
        total += BPC_SMP_COUNT[pol]

    return float(BPC_SMP_COUNT[policy])/float(total)


def compare_policies_perf(conf):
    
    policy1 = conf.win_policies[0]
    policy2 = conf.win_policies[1]
    
    pol1_bpc_list = AVG_PERF_BOOK[policy1]
    pol2_bpc_list = AVG_PERF_BOOK[policy2]
    ws = 0.0
    
    for idx in range(conf.NUM_APPS):
        ws += float(pol1_bpc_list[idx])/float(pol2_bpc_list[idx])
    
    if (float(ws)/float(conf.NUM_APPS)) < 1.0:
        return policy2
    else:
        return policy1

def find_top2_policies(conf):

    max_ws = 0
    max_perf_policy = conf.baseline
    top2_pol_list = [max_perf_policy]

    for policy in AVG_PERF_BOOK:
        if policy == conf.baseline:
            continue
        
        bpc_list = AVG_PERF_BOOK[policy]
        ws = compute_weighted_speedup(bpc_list, conf)

        if ws > max_ws:
            max_ws = ws
            top2_pol_list.insert(0, policy)
            if len(top2_pol_list) > 2:
                top2_pol_list.pop()

    return top2_pol_list


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
    offchip_bw = 0
    
    num_mon_wins = mon_time / conf.SLEEP_TIME

    start_time = time.time()

    while i < num_mon_wins: #conf.NUM_MON_WIN:
        
        for fd_idx in range(len(conf.rp_app)):
            
            data = None
            while not data:
                data = nonblocking_readlines(conf.rp_app[fd_idx], conf) #nonblocking_readlines(conf.rp, conf)
        
            (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(conf.STRUCT_FMTSTR, data)
            
            if fd_idx == 0:
                bpc[0] += bpc0
                offchip_bw += sys_bw
            elif fd_idx == 1:
                bpc[1] += bpc1
            elif fd_idx == 2:
                bpc[2] += bpc2
            elif fd_idx == 3:
                bpc[3] += bpc3

        i += 1
        time.sleep(conf.SLEEP_TIME)

#    while i < num_mon_wins: #conf.NUM_MON_WIN:
#
#        data = nonblocking_readlines(conf.rp, conf)
#        
#        if not data:
#            continue
#        
#        (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert) = struct.unpack(conf.STRUCT_FMTSTR, data)
#
#        bpc[0] += bpc0
#        bpc[1] += bpc1
#        bpc[2] += bpc2
#        bpc[3] += bpc3
#        
#        #print >> sys.stderr, "%f -- %f %f %f %f"%(time.time()-conf.start_time, bpc0, bpc1, bpc2, bpc3)
#        
#        i += 1
#        time.sleep(conf.SLEEP_TIME)

    #revert immediately do default once performance has been recorded
    #if policy != "hwpf":
    #    ready_this_policy("hwpf", conf)

    BPC_SMP_COUNT[policy] += mon_time #float(time.time() - start_time)
    #average recorded bpc
    for idx in range(conf.NUM_APPS):
        BPC_ACC_SCORE_POL[policy][idx] += float(bpc[idx])
        #bpc[idx] = float(bpc[idx])/float(num_mon_wins)#conf.NUM_MON_WIN)
    
    offchip_bw = float(offchip_bw)/float(num_mon_wins)
    #print >> sys.stderr, "bpc[%d] -- %f"%(idx,bpc[idx])

    for idx in range(conf.NUM_APPS):
        AVG_PERF_BOOK[policy][idx] = float(BPC_ACC_SCORE_POL[policy][idx])/float(BPC_SMP_COUNT[policy])
        #AVG_PERF_BOOK[policy][idx] = float(AVG_PERF_BOOK[policy][idx]+bpc[idx])/float(2)  # simple-moving average

    if policy != conf.baseline:
        bpc_list = AVG_PERF_BOOK[policy]
        ws = compute_weighted_speedup(bpc_list, conf)
        PERF_BOOK[policy] = ws

        if ws > conf.max_thruput:
            conf.max_thruput = ws
            conf.max_perf_policy = policy
        
        if ws > 1.0 and not policy in conf.win_policies:
            conf.win_policies.insert(0, policy)

        if ws < 1.0:
            conf.exp_overhead += mon_time

        OVERALL_PERF.append(ws)

        conf.curr_ws = ws
        print >> sys.stderr, "policy %s -- weighted speedup %f  --  off-chip bandwidth %f GB/s"%(policy, ws, offchip_bw)
    else:
        print >> sys.stderr, "policy %s --  off-chip bandwidth %f GB/s"%(policy, offchip_bw)
        OVERALL_PERF.append(1.0)

    #print >> sys.stderr, "%s -- bpc_acc "%(policy), BPC_SMP_COUNT[policy], BPC_ACC_SCORE_POL[policy], AVG_PERF_BOOK[policy]
    for policy in BPC_SMP_COUNT:
        print >> sys.stderr, "%s -- bpc_acc %f sec"%(policy, BPC_SMP_COUNT[policy]) #float(BPC_SMP_COUNT[policy] * conf.SLEEP_TIME)/float(1000))

def wait_for_JIT(conf, revert):

    print >> sys.stderr, "POLMAN -- Waiting for %d JIT instances to complete"%(len(conf.rp_app))

    for fd in conf.rp_app:
        while True:
            data = nonblocking_readlines(fd, conf)
            if not data:
                time.sleep(conf.SLEEP_TIME)
                continue
            (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert_status) = struct.unpack(conf.STRUCT_FMTSTR, data)
            
            if not revert and swpf_status == ENUMS.SWPF_JIT_ACTIVE:
                break
            elif revert and swpf_status == 0:
                break
            time.sleep(conf.SLEEP_TIME)

def wait_for_hwpf_throttle(hwpf_change_to, conf):

    print >> sys.stderr, "POLMAN -- waiting for HWPF to change to %d"%(hwpf_change_to)

    fd = conf.rp_app[0]

    while True:
        data = nonblocking_readlines(fd, conf)
        if not data:
            time.sleep(conf.SLEEP_TIME)
            continue
        (comm_type, core0, core1, core2, core3, bpc0, bpc1, bpc2, bpc3, sys_bw, hwpf_status, swpf_status, revert_status) = struct.unpack(conf.STRUCT_FMTSTR, data)
        
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
    elif (conf.curr_policy != "hwpf" and conf.curr_policy != "nopref") and (policy == "hwpf" or policy == "nopref"):#and policy != conf.curr_policy:
        revert = True

    if conf.ENABLED_SWPF:
        wait_for_JIT(conf, revert)
    elif revert:
        wait_for_JIT(conf, revert)

    wait_for_hwpf_throttle(hwpf_change_to, conf)

    conf.curr_policy = policy

    print >> sys.stderr, "POLMAN -- policy %s is ready on all cores at %f seconds"%(policy, time.time() - conf.start_time)

def reexplore_winning(conf):
    
    print >> sys.stderr, "POLMAN -- starting Re-exploration at %f seconds"%(time.time() - conf.start_time)

    curr_max_perf_policy = conf.max_perf_policy

    conf.max_perf_policy = conf.baseline
    conf.max_thruput = 1.0

    # will make comparison of max_perf_policy with recent baseline performance
    #ready_this_policy(curr_max_perf_policy, conf)

    #retries = 0
    
    #monitor_perf(curr_max_perf_policy, 0.5, conf)
    #while retries < (conf.RETRIES - 1) and conf.max_perf_policy != curr_max_perf_policy:
    #    monitor_perf(curr_max_perf_policy, 0.5, conf)
    #    retries += 1

    # if curr_max_perf_policy still performs better than baseline, then don't explore
    #if conf.max_perf_policy == curr_max_perf_policy:
    #    print >> sys.stderr, "POLMAN -- keeping policy %s"%(conf.max_perf_policy)
    #    return

    i = 0

    if conf.NUM_APPS > 2:
        conf.win_policies = ["hwpfswpf", "swpf", "l1hwpfswpf"]
    else:
        conf.win_policies = ["hwpfswpf", "l1hwpfswpf"]

    conf.win_policies = find_top2_policies(conf)

    win_policies_count = len(conf.win_policies)

    print >> sys.stderr, "POLMAN -- Top 2 performing policies",(conf.win_policies)

    # do one whole circle over all winnging policies, then choose the best
    while i < win_policies_count:
        
        ready_this_policy(conf.baseline, conf)
        monitor_perf(conf.baseline, conf.MON_EPOCH, conf)
        
        policy = conf.win_policies.pop()
        print >> sys.stderr, "POLMAN -- Re-exploration testing policy %s"%(policy)
        
        if policy == conf.baseline:
            continue
        
        ready_this_policy(policy, conf)
        
        retries = 0
        
        monitor_perf(policy, conf.MON_EPOCH, conf)
        while retries < (conf.RETRIES - 1) and conf.max_perf_policy != policy:
            monitor_perf(policy, conf.MON_EPOCH, conf)
            retries += 1
        
        i += 1

    #conf.max_perf_policy = compare_policies_perf(conf)

    #ready_this_policy(conf.max_perf_policy, conf)

#   if curr_max_perf_policy == conf.max_perf_policy:
#        conf.backoff_reexp_time += 5
#    else:
#        conf.backoff_reexp_time = conf.REEXP_TIME

    conf.consec_beating = 0
    conf.REP_REEXP -= 1

def monitor_best_policy(conf):
    
    mon_list = [conf.max_perf_policy]
    
    prev_ws = conf.curr_ws
    max_ws = 0
    prev_policy = conf.max_perf_policy
    
    print >> sys.stderr, "policy monitor duration %f"%(policy_mon_duration(conf.baseline))
    
    if policy_mon_duration(conf.baseline) < 0.15: #conf.mon_baseline_after == 0:
        mon_list = [conf.baseline, conf.max_perf_policy]
        #for policy in conf.win_policies:
            #if not policy in mon_list:
            #   mon_list.append(policy)
        
        conf.MON_BASELINE_AFTER_ITER += 2
        conf.mon_baseline_after = conf.MON_BASELINE_AFTER_ITER
        print >> sys.stderr, "Monitor baseline after ... %d sec"%(conf.MON_BASELINE_AFTER_ITER)

    for policy in mon_list:
        
        ready_this_policy(policy, conf)
        monitor_perf(policy, conf.MON_EPOCH, conf)

        if policy == conf.baseline:
            continue

        bpc_list = AVG_PERF_BOOK[policy]
        ws = compute_weighted_speedup(bpc_list, conf)
        #PERF_BOOK[policy] = ws

        if ws > conf.max_thruput:
            conf.max_thruput = ws
            conf.curr_ws = ws

        if ws > max_ws:
            max_ws = ws
            conf.max_perf_policy = policy

    if max_ws < 1.0:# and prev_policy == conf.max_perf_policy:
        conf.falsepos_count += 1
    else:
        conf.falsepos_count -= 1


    if max_ws < prev_ws:
        conf.consec_beating += 1
    else:
        conf.consec_beating = 0

    ready_this_policy(conf.max_perf_policy, conf)
        
    conf.mon_baseline_after -= 1
    
    print >> sys.stderr, "policy %s -- weighted speedup %f -- falsepos_count %d -- conf.consec_beating %d"%(conf.max_perf_policy, PERF_BOOK[conf.max_perf_policy], conf.falsepos_count, conf.consec_beating)
    #print >> sys.stderr, "hwpf_bpc_list -- %f %f %f"%(AVG_PERF_BOOK[conf.baseline][0], AVG_PERF_BOOK[conf.baseline][1], AVG_PERF_BOOK[conf.baseline][2])
    #print >> sys.stderr, "maxperf_bpc_list -- %f %f %f"%(AVG_PERF_BOOK[conf.max_perf_policy][0], AVG_PERF_BOOK[conf.max_perf_policy][1], AVG_PERF_BOOK[conf.max_perf_policy][2])

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
        
        for exp_plan_idx in range(total_states):
        
            policy = EXP_PLAN[conf.NUM_APPS][exp_plan_idx]
            
            retries = 0
            
	    #ready_this_policy(policy, conf)

            if policy == conf.baseline:
                #ready_this_policy(policy, conf)
                #monitor_perf(EXP_PLAN[conf.NUM_APPS][exp_plan_idx], 0.5, conf)
                continue
            else:
                while retries < conf.RETRIES and conf.max_perf_policy != policy:
                    ready_this_policy(conf.baseline, conf)
                    monitor_perf(conf.baseline, conf.MON_EPOCH, conf)
                    ready_this_policy(policy, conf)
                    monitor_perf(EXP_PLAN[conf.NUM_APPS][exp_plan_idx], conf.MON_EPOCH, conf)
                    retries += 1

        #apply policy with max performance
        print >> sys.stderr, "POLMAN -- Applying best prefetching policy: %s"%(conf.max_perf_policy)
        ready_this_policy(conf.max_perf_policy, conf)

        #conf.RETRIES = 3

        time_passed = time.time() - conf.start_time

        re_explore_in = conf.REEXP_TIME + time_passed

        hwpf_best_count = 0

        while conf.EXIT_AFTER > time_passed:

            print >> sys.stderr, "POLMAN -- re-explore in %f"%(re_explore_in - time_passed)
            print >> sys.stderr, "POLMAN -- exploration overhead %f sec -- overall speedup %f"%(float(conf.exp_overhead), float(sum(OVERALL_PERF))/float(len(OVERALL_PERF)))
            
            if (re_explore_in - time_passed) < 0.1 and conf.REP_REEXP > 0:
                reexplore_winning(conf)
                #apply policy with max performance
                print >> sys.stderr, "POLMAN -- Applying best prefetching policy after re-exploration: %s"%(conf.max_perf_policy)
                ready_this_policy(conf.max_perf_policy, conf)
                time_passed = time.time() - conf.start_time
                if conf.max_perf_policy == conf.baseline:
                    re_explore_in = time_passed + 10
                    hwpf_best_count += 1
                else:
                    re_explore_in = conf.backoff_reexp_time + time_passed
                    hwpf_best_count = 0
                conf.falsepos_count = 0
        
        #if hwpf_best_count == 3:
        #   break
        
            if conf.curr_policy != "hwpf":
                monitor_best_policy(conf)
                
                #If too many false positives occur, revert to baseline policy
                #if conf.falsepos_count == conf.falsepos_thr or conf.exp_overhead > conf.SLOWDOWN_QUOTA:
                if conf.consec_beating >= 2 or conf.falsepos_count == conf.falsepos_thr or conf.exp_overhead > conf.SLOWDOWN_QUOTA:
                    conf.reexp_fail_count += 1
                    #ready_this_policy(conf.baseline, conf)
                    conf.falsepos_count = 0
                    re_explore_in = time_passed + 0 # restart re-exploration immediately
                    if conf.exp_overhead > conf.SLOWDOWN_QUOTA:
                    #if conf.reexp_fail_count == conf.REEXP_FAIL_THR or conf.exp_overhead > conf.SLOWDOWN_QUOTA:
                        print >> sys.stderr, "POLMAN -- Abondoning exploration..."
                        for policy in PERF_BOOK:
                            print >> sys.stderr, "policy %s -- weighted speedup %f"%(policy, PERF_BOOK[policy])
                        re_explore_in = conf.REEXP_TIME # slowdown quota has been filled for REEXP_TIME -- start again in REEXP_TIME
                    print >> sys.stderr, "POLMAN -- Reverting to baseline policy: %s"%(conf.baseline)
                    print >> sys.stderr, "POLMAN -- Starting Re-exploration soon..."
            
#                if conf.consec_beating == 2 and conf.exp_overhead < conf.SLOWDOWN_QUOTA:
#                    ready_this_policy(conf.baseline, conf)
#                    re_explore_in = time_passed + 10
#                    while (re_explore_in - time_passed) > 0.1:
#                        monitor_perf(conf.baseline, conf.MON_EPOCH, conf)
#                        time_passed = time.time() - conf.start_time

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
