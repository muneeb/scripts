#!/usr/bin/python

import os
import struct
import locale
import fcntl
import time

def nonblocking_readlines(fd):

    buf = bytearray()
    remaining_bytes = 48
    
    while remaining_bytes > 0:
        try:
            block = os.read(fd, 48) #read 48-byte chunks at a time
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

def send_data(fd):
    
    print "in nbrdl..."
    #fd = f.fileno()
    #fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    #fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    enc = locale.getpreferredencoding(False)
    
    buf = bytearray()
    while True:
        try:
            block = os.read(fd, 48) #read 48-byte chunks at a time
        except BlockingIOError:
            yield ""
            continue
        
        if not block:
            if buf:
                yield buf.decode(enc)
                buf.clear()
            break
    
        buf.extend(block)
        
        while True:
            r = buf.find(b'\r')
            n = buf.find(b'\n')
            if r == -1 and n == -1: break
            
            if r == -1 or r > n:
                yield buf[:(n+1)].decode(enc)
                buf = buf[(n+1):]
            elif n == -1 or n > r:
                yield buf[:r].decode(enc) + '\n'
                if n == r+1:
                    buf = buf[(r+2):]
                else:
                    buf = buf[(r+1):]

def deleteContent(fd):
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)

def main():

    rp = os.open("/tmp/PRT_POL_MAN_RECV", os.O_RDONLY )
    wp = os.open("/tmp/PRT_RECV_INFO_3", os.O_WRONLY )

    fl = fcntl.fcntl(rp, fcntl.F_GETFL)
    fcntl.fcntl(rp, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    fl = fcntl.fcntl(wp, fcntl.F_GETFL)
    fcntl.fcntl(wp, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    i=0

    while i < 4:
    
        data = nonblocking_readlines(rp)
        #next(data)
        os.lseek(rp, 0, os.SEEK_SET)
        core_id = [0,1,2,3]
        bpc = [0,0,0,0]
        
        if data:
        
            (comm_type, core_id[0], core_id[1], core_id[2], core_id[3], bpc[0], bpc[1], bpc[2], bpc[3], hwpf_status, swpf_status, revert) = struct.unpack("iiiiiffffiii", data)
            print "POLMAN"
            print "core - %d, BPC - %f"%(core_id[0], bpc[0])
            print "core - %d, BPC - %f"%(core_id[1], bpc[1])
            print "core - %d, BPC - %f"%(core_id[2], bpc[2])
            print "core - %d, BPC - %f"%(core_id[3], bpc[3])

        snd_data=struct.pack("iiiiiffffiii", 2, 0, 1, 2, 3, 0.1+i, 0.1+i, 0.1+i, 0.1+i, 1+i, 1+i, 0+i)
        deleteContent(wp)
        os.write(wp, snd_data)
        i += 1
        time.sleep(1)

if __name__ == '__main__':
    main()