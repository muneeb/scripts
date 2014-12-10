#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <stdlib.h>
#include <aio.h>

struct aiocb aiocb_snd;
struct aiocb aiocb_rcv;
static int fd_snd, fd_rec;

static int SBO_CORE_BIND=3;

//PRT_Comm_Bundle type
enum {
    PRT_COMM_SEND = 1,
    PRT_COMM_RECV
};

//PRT_Comm_Bundle hwpf_status -- ignored for send
enum {
    HWPF_ON = 0,
    LLC_HWPF_OFF,
    HWPF_OFF
};

//PRT_Comm_Bundle swpf_status -- ignored for send
enum {
    SWPF_8MBLLC = 1,
    SWPF_6MBLLC,
    SWPF_4MBLLC,
    SWPF_2MBLLC,
    SWPF_1MBLLC,
    SWPF_0MBLLC
};

//PRT_Comm_Bundle revert -- ignored for send
enum {
    NO_REVERT_TO_PREV = 0,
    REVERT_TO_PREV
};

struct PRT_Comm_Bundle{
    int type;
    int core_id[4];
    float bpc[4];
    int hwpf_status;
    int swpf_status;
    int revert;
};


int PRT_MONITOR_APP = 1;

void create_comm_pipes(){
    
#define TNAME "PRT_COMM"
    
    char fname[256];
    
    if (PRT_MONITOR_APP){
    
        snprintf(fname, sizeof(fname), "/tmp/PRT_POL_MAN_RECV");
        
        /* create the FIFO (named pipe) */
        mkfifo(fname, 0666);
        
        unlink(fname);
        fd_snd = open(fname, O_CREAT | O_WRONLY | O_EXCL, S_IRUSR | S_IWUSR);
        
        if (fd_snd == -1) {
            fprintf(stderr," Error at open(): %s\n", strerror(errno));
            exit(1);
        }
        
        //unlink(fname);
        
        aiocb_snd.aio_fildes = fd_snd;
        aiocb_snd.aio_lio_opcode = LIO_WRITE;
        
        fprintf(stdout, "PRT_MONITOR_APP -- ready to SEND info!\n");
    
    }
    
    snprintf(fname, sizeof(fname), "/tmp/PRT_RECV_INFO_%d", SBO_CORE_BIND);
    /* create the FIFO (named pipe) */
    mkfifo(fname, 0666);
    
    unlink(fname);
    fd_rec = open(fname, O_CREAT | O_RDONLY | O_EXCL, S_IRUSR | S_IWUSR);
    
    if (fd_rec == -1) {
        fprintf(stderr," Error at open(): %s\n", strerror(errno));
        exit(1);
    }
    
    //unlink(fname);
    
    aiocb_rcv.aio_fildes = fd_rec;
    aiocb_rcv.aio_lio_opcode = LIO_READ;
    
    fprintf(stdout, "PRT -- ready to RECIEVE info!\n");
    
}

void send_bpc_info(int* core_id, float* bpc){
    
    static struct PRT_Comm_Bundle comm_bundle;
    int err, ret;
    
    //if(ftruncate(aiocb_snd.aio_fildes, 0) == -1)
    //    fprintf(stderr," Error at ftruncate(): %s\n", strerror(errno));;
    
    comm_bundle.type = PRT_COMM_SEND;
    
    for (int i=0; i<4; i++) {
        comm_bundle.core_id[i] = core_id[i];
        comm_bundle.bpc[i] = bpc[i] + rand();
    }
    
    comm_bundle.hwpf_status = 0;
    comm_bundle.swpf_status = 0;
    comm_bundle.revert = 0;
    
    aiocb_snd.aio_buf = &comm_bundle;
    aiocb_snd.aio_nbytes = sizeof(comm_bundle);
    
    
    if (aio_write(&aiocb_snd) == -1) {
        fprintf(stderr," Error at open(): %s\n", strerror(errno));
        close (fd_snd);
        exit(2);
    }
    
    /* Wait until completion */
    while (aio_error (&aiocb_snd) == EINPROGRESS);
    
    err = aio_error(&aiocb_snd);
    ret = aio_return(&aiocb_snd);
    
    if (err != 0) {
        fprintf(stderr," Error at aio_error() : %s", strerror(err));
        close(fd_snd);
        exit(2);
    }
    
    if (ret != sizeof(comm_bundle)) {
        fprintf(stderr," Error at aio_return()");
        close(fd_snd);
        exit(2);
    }
    
}

void rec_bpc_info(){
    
    #define BUF_SIZE 48
    static char buf[BUF_SIZE];
    static struct PRT_Comm_Bundle comm_bundle;
    int err, ret;
    
    memset(&comm_bundle, 0, sizeof(struct PRT_Comm_Bundle));
    
    aiocb_rcv.aio_buf = buf;
    aiocb_rcv.aio_nbytes = BUF_SIZE;
    aiocb_rcv.aio_lio_opcode = LIO_WRITE;
    
    if (aio_read(&aiocb_rcv) == -1) {
        printf(TNAME " Error at aio_read(): %s\n",
               strerror(errno));
        exit(2);
    }
    
    /* Wait until end of transaction */
    while ((err = aio_error (&aiocb_rcv)) == EINPROGRESS);
    
    err = aio_error(&aiocb_rcv);
    ret = aio_return(&aiocb_rcv);
    
    if (err != 0) {
        printf(TNAME " Error at aio_error() : %s\n", strerror (err));
        close(fd_rec);
        exit(2);
    }
    
    if (ret != sizeof(comm_bundle)) {
        printf(TNAME " No communication!\n");
        return;
    }
    
    comm_bundle = *(PRT_Comm_Bundle *) buf;
    //memcpy(&comm_bundle, buf, sizeof(comm_bundle));
    
    fprintf(stderr, "core_id - %d, hwpf_status - %d, swpf_status - %d, revert - %d\n", 3, comm_bundle.hwpf_status, comm_bundle.swpf_status, comm_bundle.revert);
}

int main(){
    
    int core_id[4] = {0,1,2,3};
    float bpc[4] = {0.0, 0.0, 0.66, 0.71};
    
    create_comm_pipes();
    
    for (int i = 0; i < 4; i++){
        sleep(1);
        send_bpc_info(core_id, bpc);
        rec_bpc_info();
    
    }
    close(fd_snd);
    close(fd_rec);
    
    return 0;
}


