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

PERF_CMD_STR="perf_3.2.0-34 stat -e cycles -e r1004102f0 -e instructions -e branches -o "

export SCHEDULER_PROFILE_FILE=${BKBPROF}
export PRT_ENABLED=0
export SBO_OPTIMIZER=2

VENDOR=$(grep -m 1 vendor_id /proc/cpuinfo | awk '{print $3}')

USING_PAPI=0
CPU=amd_ph2

if [[ ${VENDOR} == AuthenticAMD ]]
then
    echo "AMD detected. Using Perf tool..."
    APP_TRACE_TOK=
    /home/muneeb/sdist_pref/hwpf.sh on
else
    echo "Intel detected. Using Papi tool..."
    PERF_CMD_STR=${PAPI_CMD_STR}
    USING_PAPI=1
    CPU=intel_snb
    ${SCRIPTS_HOME}/hwpf.sh on
    APP_TRACE_TOK="-t"
fi


for HWPF_SETTINGS in on #off
do

#${SCRIPTS_HOME}/hwpf.sh ${HWPF_SETTINGS}

    for FGBENCH in libquantum omnetpp astar soplex
    do

        FGPERF_THRUPUT_OUT=/home/muneeb/protean/${FGBENCH}_thruput_${CPU}.out
        FGPERF_ISO_OUT=/home/muneeb/protean/${FGBENCH}_isolated_${CPU}.out

        cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

        FGARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

        taskset -c 0 ${PERF_CMD_STR}${FGBPROF} ${APP_TRACE_TOK} ./${FGBENCH}_112012.orig ${FGARGS} > /dev/null &

        wait

        if [[ ${USING_PAPI} == 1 ]]
        then
            FG_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${FGBPROF} | awk '{print $2}')
            FG_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${FGBPROF} | awk '{print $2}')
            FG_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${FGBPROF} | awk '{print $2}')
            FG_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${FGBPROF} | awk '{print $2}')

            FG_BW=$(echo '(('${FG_LLC_MISSES}'*64)/1024^3)/('${FG_CYCLES}'/3400000000)' | bc -l)
            FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
            FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)
        else
            FG_LLC_MISSES=$(grep r1004102f0 ${FGBPROF} | awk '{print $1}' | tr -d ',')
            FG_CYCLES=$(grep cycles ${FGBPROF} | awk '{print $1}' | tr -d ',')
            FG_INSTRS=$(grep instructions ${FGBPROF} | awk '{print $1}' | tr -d ',')
            FG_BRANCHES=$(grep branches ${FGBPROF} | awk '{print $1}' | tr -d ',')

            FG_BW=$(echo '(('${FG_LLC_MISSES}'*64)/1024^3)/('${FG_CYCLES}'/2800000000)'  | bc -l)
            FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
            FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)
        fi

        echo ${FGBENCH}" "${FG_IPC}" "${FG_BW}" "${FG_CYCLES}" "${FG_LLC_MISSES}" "${FG_BPC} > ${FGPERF_ISO_OUT}

        for BKBENCH in lbm mcf libquantum milc
        do

            cd ${SPEC_HOME}/*${BKBENCH}*/src.clean

            BKARGS=$(grep 'PARAMS=' Makefile | tr -d 'PARAMS=')

            PREV_NTA_COUNT=-1
            NTA_COUNT=0

            BKPERF_ISO_OUT=/home/muneeb/protean/${BKBENCH}_isolated_${CPU}.out

            if [ ! -f ${BKPERF_ISO_OUT} ]
            then

                if [[ ${BKBENCH} == milc ]]
                then
                    taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm < "su3imp.in" > /dev/null &
                else
                    taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm ${BKARGS} > /dev/null &
                fi

                wait

                if [[ ${USING_PAPI} == 1 ]]
                then
                    BK_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${BKBPROF} | awk '{print $2}')
                    BK_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${BKBPROF} | awk '{print $2}')
                    BK_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${BKBPROF} | awk '{print $2}')
                    BK_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${BKBPROF} | awk '{print $2}')

                    BK_BW=$(echo '(('${BK_LLC_MISSES}'*64)/1024^3)/('${BK_CYCLES}'/3400000000)' | bc -l)
                    BK_IPC=$(echo ${BK_INSTRS}'/'${BK_CYCLES} | bc -l)
                    BK_BPC=$(echo ${BK_BRANCHES}'/'${BK_CYCLES} | bc -l)
                else
                    BK_LLC_MISSES=$(grep r1004102f0 ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_CYCLES=$(grep cycles ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_INSTRS=$(grep instructions ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_BRANCHES=$(grep branches ${BKBPROF} | awk '{print $1}' | tr -d ',')

                    BK_BW=$(echo '(('${BK_LLC_MISSES}'*64)/1024^3)/('${BK_CYCLES}'/2800000000)' | bc -l)
                    BK_IPC=$(echo ${BK_INSTRS}'/'${BK_CYCLES} | bc -l)
                    BK_BPC=$(echo ${BK_BRANCHES}'/'${BK_CYCLES} | bc -l)
                fi

                echo ${BKBENCH}" "${BK_IPC}" "${BK_BW}" "${BK_CYCLES}" "${BK_LLC_MISSES}" "${BK_BPC} > ${BKPERF_ISO_OUT}

            fi

            for NTA_POLICY in $(seq 0 11)
            do

                cd ${SPEC_HOME}/*${FGBENCH}*/src.clean

                taskset -c 0 ${PERF_CMD_STR}${FGBPROF} ${APP_TRACE_TOK} ./${FGBENCH}_112012.orig ${FGARGS} > /dev/null &

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
                        taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm < "su3imp.in" > /dev/null &
                    else
                        taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean_prefp${NTA_POLICY}.frmasm ${BKARGS} > /dev/null &
                    fi

                else
                    if [[ ${BKBENCH} == milc ]]
                    then
                        taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean.frmasm < "su3imp.in"  > /dev/null &
                    else
                        taskset -c 2 ${PERF_CMD_STR}${BKBPROF} ${APP_TRACE_TOK} ./${BKBENCH}_protean.frmasm ${BKARGS} > /dev/null &
                    fi
                fi

                wait

                PREV_NTA_COUNT=${NTA_COUNT}
                if [[ ${USING_PAPI} == 1 ]]
                then
                    FG_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${FGBPROF} | awk '{print $2}')
                    FG_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${FGBPROF} | awk '{print $2}')
                    FG_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${FGBPROF} | awk '{print $2}')
                    FG_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${FGBPROF} | awk '{print $2}')

                    FG_BW=$(echo '(('${FG_LLC_MISSES}'*64)/1024^3)/('${FG_CYCLES}'/3400000000)' | bc -l)
                    FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
                    FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)


                    BK_LLC_MISSES=$(grep 'OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL' ${BKBPROF} | awk '{print $2}')
                    BK_CYCLES=$(grep 'UNHALTED_CORE_CYCLES' ${BKBPROF} | awk '{print $2}')
                    BK_INSTRS=$(grep 'INSTRUCTIONS_RETIRED' ${BKBPROF} | awk '{print $2}')
                    BK_BRANCHES=$(grep 'BR_INST_EXEC:ALL_BRANCHES' ${BKBPROF} | awk '{print $2}')

                    BK_BW=$(echo '(('${BK_LLC_MISSES}'*64)/1024^3)/('${BK_CYCLES}'/3400000000)' | bc -l)
                    BK_IPC=$(echo ${BK_INSTRS}'/'${BK_CYCLES} | bc -l)
                    BK_BPC=$(echo ${BK_BRANCHES}'/'${BK_CYCLES} | bc -l)
                else
                    FG_LLC_MISSES=$(grep r1004102f0 ${FGBPROF} | awk '{print $1}' | tr -d ',')
                    FG_CYCLES=$(grep cycles ${FGBPROF} | awk '{print $1}' | tr -d ',')
                    FG_INSTRS=$(grep instructions ${FGBPROF} | awk '{print $1}' | tr -d ',')
                    FG_BRANCHES=$(grep branches ${FGBPROF} | awk '{print $1}' | tr -d ',')

                    FG_BW=$(echo '(('${FG_LLC_MISSES}'*64)/1024^3)/('${FG_CYCLES}'/2800000000)' | bc -l)
                    FG_IPC=$(echo ${FG_INSTRS}'/'${FG_CYCLES} | bc -l)
                    FG_BPC=$(echo ${FG_BRANCHES}'/'${FG_CYCLES} | bc -l)

                    BK_LLC_MISSES=$(grep r1004102f0 ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_CYCLES=$(grep cycles ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_INSTRS=$(grep instructions ${BKBPROF} | awk '{print $1}' | tr -d ',')
                    BK_BRANCHES=$(grep branches ${BKBPROF} | awk '{print $1}' | tr -d ',')

                    BK_BW=$(echo '(('${BK_LLC_MISSES}'*64)/1024^3)/('${BK_CYCLES}'/2800000000)' | bc -l)
                    BK_IPC=$(echo ${BK_INSTRS}'/'${BK_CYCLES} | bc -l)
                    BK_BPC=$(echo ${BK_BRANCHES}'/'${BK_CYCLES} | bc -l)
                fi

                echo ${BKBENCH}"_prefp"${NTA_POLICY}" "${FG_IPC}" "${FG_BW}" "${FG_CYCLES}" "${FG_LLC_MISSES}" "${FG_BPC}" "${BK_IPC}" "${BK_BW}" "${BK_CYCLES}" "${BK_LLC_MISSES}" "${BK_BPC} >> ${FGPERF_THRUPUT_OUT}

            done

        done

    done

done

#${SCRIPTS_HOME}/hwpf.sh on
