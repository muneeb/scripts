#!/usr/bin/python

from optparse import OptionParser

class Conf:
    def __init__(self):
        parser = OptionParser("usage: %prog [OPTIONS...] INFILE")
        
        parser.add_option("-i",
                          type="string", default=None,
                          dest="infile",
                          help="Infile containing raw data from Protean runtime")

        parser.add_option("-d",
                          type="float", default=10.0,
                          dest="ignore_time",
                          help="ignore the first XX seconds measurments")
                  
        parser.add_option("-c",
                          type="int", default=None,
                          dest="core_id",
                          help="CPU core you're interested in")
                          
        parser.add_option("-f",
                          type="long", default=3400000000,
                          dest="cpu_freq",
                          help="CPU frequency")

        (opts, args) = parser.parse_args()

        self.infile = opts.infile
        self.ignore_time = opts.ignore_time
        self.core_id = opts.core_id
        self.cpu_freq = opts.cpu_freq

def main():
    conf = Conf()

    f = open(conf.infile, "r")
    lines = f.readlines()
    f.close()
    
    prev_time = 0
    avg_IPC = 0
    avg_BPC = 0
    avg_BW = 0
    avg_misses_per_kilo_branch = 0

    sample_count = 0

    for line in lines:

        line_tok = line.split()

        core_id = int((line_tok[0].split('='))[1])

        if core_id > 3:
            continue
        
        cur_time = float((line_tok[2].split('='))[1])
        
        if cur_time < conf.ignore_time:
            continue
        
        if cur_time - prev_time < 0.2:
            continue
        
        if core_id == 3:
            prev_time = cur_time
            sample_count += 1

        ins = long((line_tok[3].split('='))[1])
        br = long((line_tok[5].split('='))[1])
        llc_miss = long((line_tok[6].split('='))[1])
        cycles = long((line_tok[4].split('='))[1])

        ipc = float(ins)/float(cycles)
        bpc = float(br)/float(cycles)
        bw = ((float(llc_miss)*64)/float(1024*1024*1024))/(float(cycles)/float(conf.cpu_freq))
        llc_miss_per_kilo_br = ((float(llc_miss))/float(br/1000))

        avg_IPC += round(ipc,3)
        avg_BPC += round(bpc,3)
        avg_BW += round(bw,3)
        avg_misses_per_kilo_branch += round(llc_miss_per_kilo_br,3)

    avg_IPC = round(avg_IPC/float(sample_count),3)
    avg_BPC = round(avg_BPC/float(sample_count),3)
    avg_BW = round(avg_BW/float(sample_count),3)
    avg_misses_per_kilo_branch = round(avg_misses_per_kilo_branch/float(sample_count),3)

    print avg_IPC, avg_BPC, avg_BW, avg_misses_per_kilo_branch

if __name__ == "__main__":
    main()