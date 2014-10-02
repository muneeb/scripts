#!/bin/bash

SPEC_HOME=/home/muneeb/spec2006_static
SCRIPT_HOME=/home/muneeb/git/scripts

${SCRIPT_HOME}/hwpf.sh off

for BENCH in mcf lbm soplex
do

    BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

    cd ${BENCH_DIR}

    INFO_STR=""

    OUTFILE=/home/muneeb/protean/${BENCH}_perins_bw.csv

    echo "#num nta, CYCLES, MEM_BW, L3_MISSES, L2_MISSES" > ${OUTFILE}

    for NUM_NTA in $(seq 0 15)
    do
        ARGS=$(grep PARAM Makefile | tr -d 'PARAMS=' )

        LD_LIBRARY_PATH=/home/muneeb/llvm-3.3/Release+Asserts/lib:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime/Scheduler/lib:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime/Scheduler/src:/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime:/home/muneeb/perfmon2-libpfm4/lib/ SCHEDULER_PROFILE_FILE=.tmp PRT_ENABLED=0 /home/muneeb/papi_tools/papi_profiler -n 4 -e L2_RQSTS:DEMAND_DATA_RD_MISS -e OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL -e LONGEST_LAT_CACHE:MISS -e UNHALTED_CORE_CYCLES -o .tmp -t ./${BENCH}_protean_nta${NUM_NTA}.frmasm ${ARGS}

        L3_MISSES=$(grep "OFFCORE_RESPONSE_0:ANY_REQUEST:LLC_MISS_LOCAL:" .tmp | awk '{print $2}')
        L2_MISSES=$(grep "L2_RQSTS:DEMAND_DATA_RD_MISS:" .tmp | awk '{print $2}')
        CYCLES=$(grep "UNHALTED_CORE_CYCLES:" .tmp | awk '{print $2}')
        MEM_BW=$(echo "("${L3_MISSES}"*64/1024^3)/("${CYCLES}"/4000000000)" | bc -l)

        INFO_STR=${NUM_NTA}" "${CYCLES}" "${MEM_BW}" "${L3_MISSES}" "${L2_MISSES}

        echo ${INFO_STR} >> ${OUTFILE}
    done

done
