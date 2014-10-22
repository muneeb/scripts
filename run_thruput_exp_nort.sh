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

PAPI_CMD_STR=${PAPI_TOOLS}"/papi_profiler -n 4 -e INSTRUCTIONS_RETIRED -e OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL -e UNHALTED_CORE_CYCLES -e BR_INST_EXEC:ALL_BRANCHES -o "


export SCHEDULER_PROFILE_FILE=${BKBPROF}
export PRT_ENABLED=0
export SBO_OPTIMIZER=2

for HWPF_SETTINGS in off #on
do

    ${SCRIPTS_HOME}/hwpf.sh ${HWPF_SETTINGS}

    for FGBENCH in libquantum omnetpp astar soplex
    do

        FGPERF_THRUPUT_OUT=/home/muneeb/protean/${FGBENCH}_thrupt.out
        FGPERF_ISO_OUT=/home/muneeb/protean/${FGBENCH}_isolated.out

        cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

        FGARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

        ${PAPI_CMD_STR}${FGBPROF} -t ./${FGBENCH}_112012.orig ${FGARGS} > /dev/null &

        wait

        FG_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${FGBPROF} | awk '{print $2}')
        FG_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${FGBPROF} | awk '{print $2}')
        FG_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${FGBPROF} | awk '{print $2}')
        FG_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${FGBPROF} | awk '{print $2}')

        FG_BW=$(echo '('${FG_LLC_MISSES}'*64/1024^3)/3400000000' | bc -l)
        FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
        FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)

        echo ${FGBENCH}" "${FG_IPC}" "${FG_BW}" "${FG_CYCLES}" "${FG_LLC_MISSES}" "${FG_BPC} > ${FGPERF_ISO_OUT}

        for BKBENCH in lbm mcf libquantum milc
        do

            cd ${SPEC_HOME}/*${BKBENCH}*/src.clean

            BKARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

            PREV_NTA_COUNT=-1
            NTA_COUNT=0

            for NTA_POLICY in $(seq 0 11)
            do
		
                cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

                ${PAPI_CMD_STR}${FGBPROF} -t ./${FGBENCH}_112012.orig ${FGARGS} > /dev/null &

                cd ${SPEC_HOME}/*${BKBENCH}*/src.clean

                if [[ ${NTA_POLICY} > 0 ]]
                then
                    NTA_COUNT=$(objdump -d ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm | grep 'prefetchnta' | wc -l)

                    if [[ ${PREV_NTA_COUNT} == ${NTA_COUNT} ]]
                    then
                        continue
                    fi

                    if [[ ${BKBENCH} == milc ]]
                    then
                        ${PAPI_CMD_STR}${BKBPROF} -t ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm < "su3imp.in" > /dev/null &
                    else
                        ${PAPI_CMD_STR}${BKBPROF} -t ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm ${BKARGS} > /dev/null &
                    fi

                else
                    if [[ ${BKBENCH} == milc ]]
                    then
                        ${PAPI_CMD_STR}${BKBPROF} -t ./${BKBENCH}_protean.frmasm < "su3imp.in"  > /dev/null &
                    else
                        ${PAPI_CMD_STR}${BKBPROF} -t ./${BKBENCH}_protean.frmasm ${BKARGS} > /dev/null &
                    fi
                fi

                wait

                PREV_NTA_COUNT=${NTA_COUNT}

                FG_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${FGBPROF} | awk '{print $2}')
                FG_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${FGBPROF} | awk '{print $2}')
                FG_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${FGBPROF} | awk '{print $2}')
                FG_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${FGBPROF} | awk '{print $2}')

                FG_BW=$(echo '('${FG_LLC_MISSES}'*64/1024^3)/3400000000' | bc -l)
                FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
                FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)


                BK_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${BKBPROF} | awk '{print $2}')
                BK_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${BKBPROF} | awk '{print $2}')
                BK_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${BKBPROF} | awk '{print $2}')
                BK_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${BKBPROF} | awk '{print $2}')

                BK_BW=$(echo '('${BK_LLC_MISSES}'*64/1024^3)/3400000000' | bc -l)
                BK_IPC=$(echo ${BK_INSTRS}'/'${BK_CYCLES} | bc -l)
                BK_BPC=$(echo ${BK_BRANCHES}'/'${BK_CYCLES} | bc -l)


                echo ${BKBENCH}"_prefp"${NTA_POLICY}" "${FG_IPC}" "${FG_BW}" "${FG_CYCLES}" "${FG_LLC_MISSES}" "${FG_BPC}" "${BK_IPC}" "${BK_BW}" "${BK_CYCLES}" "${BK_LLC_MISSES}" "${BK_BPC} >> ${FGPERF_THRUPUT_OUT}

            done

        done

    done

done

${SCRIPTS_HOME}/hwpf.sh on
