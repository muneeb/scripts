#!/bin/bash

SPEC_HOME=/home/muneeb/spec2006_static
SCRIPTS_HOME=/home/muneeb/git/scripts
PROTEAN_HOME=/home/muneeb/protean
FGBPROF=/home/muneeb/protean/data/fgprof
BKBPROF=bkprof.out

# llvm and SBO path set up
LLVM_PATH=/home/muneeb/llvm-3.3
LLVM_BUILD=Release+Asserts
SBO_PATH=/home/muneeb/llvm-3.3/lib/Transforms/SBO
export PATH="$PATH:${LLVM_PATH}/${LLVM_BUILD}/bin"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${LLVM_PATH}/${LLVM_BUILD}/lib"

# onlineSch library
ONLINESCH_ROOT=${SBO_PATH}/runtime/Scheduler
export ONLINESCH_LD_FLAGS="-L${ONLINESCH_ROOT}/src -lonlineSch"
export ONLINESCH_INCLUDE="-I${ONLINESCH_ROOT}/src -I${ONLINESCH_ROOT}/include"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${ONLINESCH_ROOT}/lib:${ONLINESCH_ROOT}/src"

# add SBO runtime library to path
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${SBO_PATH}/runtime:/home/muneeb/perfmon2-libpfm4/lib/:/home/muneeb/pin-2.12-53271-gcc.4.4.7-ia32_intel64-linux/intel64/lib-ext"


export PRT_ENABLED=1
export SBO_OPTIMIZER=4
export SBO_SHUTTER_EVERY=100
export SBO_SAMPLE_PERIOD=25000 #50000

POL_MAN_NUM_WIN=5
POL_MAN_SLEEP_TIME=$(echo ${SBO_SAMPLE_PERIOD}"/1000000" | bc -l)
POL_MAN_MON_EPOCH=$(echo ${POL_MAN_SLEEP_TIME}"*"${POL_MAN_NUM_WIN} | bc -l)

RUN_DUR=120

MIX_FILE=comb_4x_160.csv #rerun_mixes.csv #comb_4x_160.csv #test_comb.csv

while read line
do

    ${SCRIPTS_HOME}/hwpf.sh on

    NUM_BENCHS=$(echo ${line} | wc -w)

    MIX=${line}

    BENCH_PID=(0 0 0 0)

    CORE_ID=0

    MON_FLAG=1

    PERF_OUT=${PROTEAN_HOME}/rep4prt_thruput_rtexp_${NUM_BENCHS}x_${MIX// /_}.out

    for BENCH in ${MIX}
    do
        echo ${MIX}" -- Runtime Exploration"

        cd ${SPEC_HOME}/*${BENCH}*/src.clean

        BENCH_ARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

        echo ${BENCH}" "${BENCH_ARGS}

        NTA_POLICY=8
        export REP_OPT_FILE=/home/muneeb/git/scripts/${BENCH}_protean.ntap${NTA_POLICY}MBLLC

        EXEC_BIN=${BENCH}_protean.frmasm

        export SBO_CORE_BIND_MANAGED=${CORE_ID}

        case "${NUM_BENCHS}" in

            1)
                export SBO_CORE_BIND_LAPTRT=$((${CORE_ID}+1))
                ;;
            2)
                export SBO_CORE_BIND_LAPTRT=$((${CORE_ID}+2))
                ;;
            3)
                export SBO_CORE_BIND_LAPTRT=3
                ;;
            4)
                export SBO_CORE_BIND_LAPTRT=$((${CORE_ID}+4))
                ;;
        esac

        echo "SBO_CORE_BIND_LAPTRT -- "${SBO_CORE_BIND_LAPTRT}

        export PRT_MONITOR_APP=0
        export SCHEDULER_PROFILE_FILE=.tmp

        if [[ ${MON_FLAG} == 1 ]]
        then
            export PRT_MONITOR_APP=1
            export SCHEDULER_PROFILE_FILE=${PERF_OUT}
        fi

        if [[ ${BENCH} == leslie3d ]]
        then
            ./${EXEC_BIN} < "../data/ref/input/leslie3d.in" > .out &
        elif [[ ${BENCH} == milc ]]
        then
            ./${EXEC_BIN} < "../data/ref/input/su3imp.in" > .out &
        else
            ./${EXEC_BIN} ${BENCH_ARGS} > .out &
        fi

        BENCH_PID[${CORE_ID}]=$!

        MON_FLAG=0

        CORE_ID=$((${CORE_ID}+1))

    done

    cd ${SCRIPTS_HOME}

    #./pol_man.py -s ${POL_MAN_SLEEP_TIME} -p 100 -e ${POL_MAN_MON_EPOCH} -t 4 -n ${NUM_BENCHS} -x ${RUN_DUR} &> ${PROTEAN_HOME}/polman_${MIX// /_}.log &

    ./pol_man_inter.py -s ${POL_MAN_SLEEP_TIME} -p 100 -e ${POL_MAN_MON_EPOCH} -t 4 -n ${NUM_BENCHS} -x ${RUN_DUR} &> ${PROTEAN_HOME}/polman_${MIX// /_}.log &

    sleep ${RUN_DUR}

    echo "killing processes"

    echo ${BENCH_PID[0]}
    echo ${BENCH_PID[1]}
    echo ${BENCH_PID[2]}
    echo ${BENCH_PID[3]}

    for BENCH_IDX in $(seq 0 $((${NUM_BENCHS}-1)))
    do
        kill -9 ${BENCH_PID[${BENCH_IDX}]}
    done

    killall -9 pol_man.py

done < ${MIX_FILE}

${SCRIPTS_HOME}/hwpf.sh on

if [ ${MIX_FILE} == test_comb.csv ]
then
    exit
fi

cd ${PROTEAN_HOME}

#for file in $(ls rep4prt_thruput_rtexp_4x*)
#do
#    OUTFILE=$(echo ${file} | sed 's/rep4prt_thruput_rtexp_4x_//g' | sed 's/.out//g')
#    echo ${file}
#    REC=$(./process_rel_thruput_rep4prt_data.py -i ${file} -d 45)
#    SETNGS="RTEXP-"$(grep "Applying best prefetching policy" ${PROTEAN_HOME}/polman_${OUTFILE}.log | awk '{print $7}')
#    echo ${SETNGS}" "${REC} > thruput_rtexp_4x_mix_prt_${OUTFILE}.out
#    grep "HWPF " thruput_rel_4x_mix_prt_${OUTFILE}.out >> thruput_rtexp_4x_mix_prt_${OUTFILE}.out
#done

for file in $(ls thruput_rtexp_4x_mix_prt_*.out); do cat ${file} | sed 's/after //g' > .tmp; mv .tmp ${file}; done

./print_thruput_rtexp_inc_exp_perf_stats.sh

#./print_thruput_rtexp_perf_stats.sh
cd ${SCRIPTS_HOME}
