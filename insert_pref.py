#!/usr/bin/python

from optparse import OptionParser
import sys
import subprocess
import re

class Conf:
    def __init__(self):
        parser = OptionParser("usage: %prog [OPTIONS...] INFILE")

        parser.add_option("-i",
                          type="str", default=None,
                          dest="src_file",
                          help="Specify assembler (.s) file")

        parser.add_option("-o",
                          type="str", default=None,
                          dest="outfile",
                          help="Specify assembler (.s) output file with embedded prefetch instructions")

        parser.add_option("-f",
                          type="str", default=None,
                          dest="infile",
                          help="File containing prefetch decisions")
                          
        parser.add_option("-e",
                          type="str", default=None,
                          dest="exec_file",
                          help="Executable file to inspect")

        (opts, args) = parser.parse_args()

        if not opts.infile or not opts.outfile or not opts.src_file \
                or not opts.exec_file:
            print >> sys.stderr, "Invalid argument, parameter missing!"
            sys.exit(1)

        self.src_file = opts.src_file
        self.outfile = opts.outfile
        self.infile = opts.infile
        self.exec_file = opts.exec_file
        self.re_memop = re.compile("(?:0[xX][0-9a-fA-F]+|0[bB][01]*|\d+|[a-zA-Z_.$][0-9a-zA-Z_.$]*)?\([^)]*\)")
        self.re_offset = re.compile("[\s]+[+-]?0[xX][0-9a-fA-F]+|[\s]+[+-]?\d+")
        self.re_regs = re.compile("\([^)]*\)")
        self.ind_regs = re.compile("\%r[0-9a-zA-z]+")

def main():

    conf = Conf()

    src_file = open(conf.src_file, "r")
    infile = open(conf.infile, "r")
    outfile = open(conf.outfile, "w")

    pref_dec_dict = {}

    for line in infile:

        fline = line.rstrip()
        fline_tok = fline.split(":")

        insert_at_PC = fline_tok[0]
        pref_type = fline_tok[1]
        pref_dist = int(fline_tok[2])

        src_FILE_LINE = subprocess.Popen(["/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-dwarfdump", "-address="+insert_at_PC, conf.exec_file], stdout=subprocess.PIPE).communicate()[0]

        src_file_from_dbg = src_FILE_LINE.split(":")[0]
        src_line = int(src_FILE_LINE.split(":")[1])
        insert_at_PC = insert_at_PC.lstrip("0x")
        
        src_line_raw = subprocess.Popen("llvm-objdump -d "+conf.exec_file+" | grep "+insert_at_PC+" | sed 's/[[:xdigit:]]\+:\s*\([[:xdigit:]]*\s\)*//g'", shell=True, stdout=subprocess.PIPE).communicate()[0]

        pref_dec_dict[src_line] = [pref_type, pref_dist, src_line_raw]

    lineno = 1
    for line in src_file:
        
        if lineno in pref_dec_dict:
            
            [pref_type, sd, src_line_raw] = pref_dec_dict[lineno]
            
            memop = conf.re_memop.findall(src_line_raw)
            offset = conf.re_offset.findall(src_line_raw)
            
            if not memop:
                print "as in binary: %s"%src_line_raw
                print line
                print memop
                outfile.write(line)
                continue
            
            regs = conf.re_regs.findall(memop[0])
        
            if offset:
                off = long(offset[0]) + int(sd)
            else:
                off = int(sd)
            pref_reg_off = str(off)+regs[0]
            
            if pref_type == 'nta':
                outfile.write("\n\tprefetchnta %s\n"%(pref_reg_off))
            else:
                outfile.write("\n\tprefetcht0 %s\n"%(pref_reg_off))

        outfile.write(line)

        lineno += 1

    src_file.close()
    infile.close()
    outfile.close()

if __name__ == "__main__":
    main()