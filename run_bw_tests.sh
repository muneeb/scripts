#!/bin/bash

SPEC_HOME=/home/muneeb/spec2006_static
SCRIPT_HOME=/home/muneeb/git/scripts

for HWPF_SETTINGS in on off

    ${SCRIPT_HOME}/hwpf.sh ${HWPF_SETTINGS}

    for BENCH in mcf lbm soplex
    do

        BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

        cd ${BENCH_DIR}

        INFO_STR=""

        OUTFILE=/home/muneeb/protean/${BENCH}_perins_bw_hwpf${HWPF_SETTINGS}.csv

        echo "#num_nta, CYCLES, MEM_BW, L3_MISSES, L2_HITS" > ${OUTFILE}

        for NUM_NTA in $(seq 0 15)
        do
            ARGS=$(grep PARAM Makefile | tr -d 'PARAMS=' )

            LD_LIBRARY_PATH=/home/muneeb/llvm-3.3/Release+Asserts/lib:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime/Scheduler/lib:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime/Scheduler/src:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime:/home/muneeb/perfmon2-libpfm4/lib/ SCHEDULER_PROFILE_FILE=.tmp PRT_ENABLED=0 /home/muneeb/papi_tools/papi_profiler -n 4 -e MEM_LOAD_UOPS_RETIRED:L2_HIT -e OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL_DRAM -e LLC_MISSES -e UNHALTED_CORE_CYCLES -o .tmp -t ./${BENCH}_protean_nta${NUM_NTA}.frmasm ${ARGS}

            L3_MISSES=$(grep "OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL_DRAM:" .tmp | awk '{print $2}')
            L2_HITS=$(grep "MEM_LOAD_UOPS_RETIRED:L2_HIT:" .tmp | awk '{print $2}')
            CYCLES=$(grep "UNHALTED_CORE_CYCLES:" .tmp | awk '{print $2}')
            MEM_BW=$(echo "("${L3_MISSES}"*64/1024^3)/("${CYCLES}"/3400000000)" | bc -l)

            INFO_STR=${NUM_NTA}" "${CYCLES}" "${MEM_BW}" "${L3_MISSES}" "${L2_HITS}

            echo ${INFO_STR} >> ${OUTFILE}
        done

    done
done