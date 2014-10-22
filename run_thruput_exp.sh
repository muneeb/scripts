#!/bin/bash

SPEC_HOME=/home/muneeb/spec2006_static
SCRIPTS_HOME=/home/muneeb/git/scripts
PAPI_TOOLS=/home/muneeb/papi_tools
FGBPROF=/home/muneeb/protean/fgprof.out
PINHOME=
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

PAPI_CMD_STR=${PAPI_TOOLS}"/papi_profiler -n 4 -e L2_RQSTS:DEMAND_DATA_RD_MISS -e OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL -e UNHALTED_CORE_CYCLES -e BR_INST_EXEC:ALL_BRANCHES -o "


export SCHEDULER_PROFILE_FILE=${BKBPROF}
export PRT_ENABLED=1
export SBO_OPTIMIZER=2

for HWPF_SETTINGS in off #on
do

    ${SCRIPTS_HOME}/hwpf.sh ${HWPF_SETTINGS}

    for FGBENCH in libquantum omnetpp astar soplex
    do

        FGPERF_OUT=/home/muneeb/protean/${FGBENCH}

        cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

        FGARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

        for BKBENCH in lbm mcf libquantum milc
        do

            cd ${SPEC_HOME}/*${BKBENCH}*/src.clean

            BKARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

            PREV_NTA_COUNT=-1
            NTA_COUNT=0

            for NTA_POLICY in $(seq 0 11)
            do
		
                cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

                #${PAPI_CMD_STR}${FGBPROF} -t
                taskset -c 0 ./${FGBENCH}_112012.orig ${FGARGS} > /dev/null &

                FG_PID=$!

                cd ${SPEC_HOME}/*${BKBENCH}*/src.clean

                if [[ ${NTA_POLICY} > 0 ]]
                then
                    NTA_COUNT=$(objdump -d ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm | grep 'prefetchnta' | wc -l)

                    if [[ ${PREV_NTA_COUNT} == ${NTA_COUNT} ]]
                    then
                        continue
                    fi

                    taskset -c 2 ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm ${BKARGS} > /dev/null &
                else
                    taskset -c 2 ./${BKBENCH}_protean.frmasm ${BKARGS} > /dev/null &
                fi

                wait ${FG_PID}

                killall -9 ./${BKBENCH}_protean*

                grep 'CPU=0' ${BKBPROF} | tr -s "[:alpha:][_][:alpha:]=" '====' | tr -d "====" > ${FGPERF_OUT}_FG_${BKBENCH}ntap${NTA_POLICY}.csv

                grep 'CPU=2' ${BKBPROF} | tr -s "[:alpha:][_][:alpha:]=" '====' | tr -d "====" > ${FGPERF_OUT}_BG_${BKBENCH}ntap${NTA_POLICY}.csv

                PREV_NTA_COUNT=${NTA_COUNT}

#                LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${FGBPROF} | awk '{print $2}')
#                CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${FGBPROF} | awk '{print $2}')
#                INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${FGBPROF} | awk '{print $2}')

#                BW=$(echo '('${LLC_MISSES}'*64/1024^3)/4000000000' | bc -l)
#                IPC=$(echo ${INSTRS}'/'${CYCLES} | bc -l)

#                echo ${BKBENCH}"_ntap"${NTA_POLICY}" "${IPC}" "${BW}" "${CYCLES}" "${LLC_MISSES} >>
            done

        done

    done

done

${SCRIPTS_HOME}/hwpf.sh on
