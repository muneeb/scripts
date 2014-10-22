#!/bin/bash

SCRIPTS_HOME=/home/muneeb/git/scripts
SPEC_HOME=/home/muneeb/spec2006_static

for BENCH in mcf libquantum lbm milc #soplex
do

    BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

    cd ${BENCH_DIR}

    ASM_SRC_FILE=${BENCH}_protean.s
    EXEC_FILE=${BENCH}_protean.frmasm

    PREF_DEC_FILE=${SCRIPTS_HOME}/${BENCH}_protean.ntap0

    NTAOPP_COUNT=$(grep ntaopp ${PREF_DEC_FILE} | wc -l)

    if [[ $((${NTAOPP_COUNT}%10)) > 0 ]]
    then
        NTAOPP_COUNT=$((${NTAOPP_COUNT}/10+1))
    else
        NTAOPP_COUNT=$((${NTAOPP_COUNT}/10))
    fi

    COUNTER=0

    for NTA_VER in $(seq 1 11)
    do

        NTAOPP_FILE=

        if [[ ${NTA_VER} > 1 ]]
        then
            NTAOPP_FILE=${SCRIPTS_HOME}/${BENCH}_protean.ntaopp$((${NTA_VER}-1))
            COUNTER=$((${COUNTER}+${NTAOPP_COUNT}))
            grep 'ntaopp' ${PREF_DEC_FILE} | sed -n 1,${COUNTER}p > ${NTAOPP_FILE}
        fi

        OPT_EXE_BASE_NAME=${BENCH}_protean_prefp${NTA_VER}
        ASM_OUTFILE=${OPT_EXE_BASE_NAME}.s

        if [[ ${NTA_VER} > 1 ]]
        then
            ${SCRIPTS_HOME}/insert_pref.py -i ${ASM_SRC_FILE} -o ${ASM_OUTFILE} -f ${PREF_DEC_FILE} -e ${EXEC_FILE} -x ${NTAOPP_FILE}
        else
            ${SCRIPTS_HOME}/insert_pref.py -i ${ASM_SRC_FILE} -o ${ASM_OUTFILE} -f ${PREF_DEC_FILE} -e ${EXEC_FILE}
        fi

        BENCH_LD_FLAGS=$(grep BENCH_LDFLAGS Makefile.clang | tr -d 'BENCH_LDFLAGS=')

        /home/muneeb/llvm-3.3/Release+Asserts/bin/clang -O3 -sbo ${ASM_OUTFILE} -o ${OPT_EXE_BASE_NAME}.sbo.nobc -L/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime -lSBO_runtime -ldl -lrt ${BENCH_LD_FLAGS} -Wl,--export-dynamic

        #avoid inserting inline assembler in the IR mean to be used by JIT
        grep -v 'call void asm' ${BENCH}_protean.sbo.ll > ${BENCH}_protean.sbo2.ll

        objcopy --add-section .sbo_ir=${BENCH}_protean.sbo2.ll ${OPT_EXE_BASE_NAME}.sbo.nobc ${OPT_EXE_BASE_NAME}.frmasm

        NTA_COUNT=$(/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-objdump -d ${OPT_EXE_BASE_NAME}.frmasm | grep 'prefetchnta' | wc -l)

        PREF_COUNT=$(/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-objdump -d ${OPT_EXE_BASE_NAME}.frmasm | grep 'prefetch' | wc -l)

        echo ${NTA_COUNT}" NTAs of "${PREF_COUNT}" prefetches inserted in "${OPT_EXE_BASE_NAME}.frmasm

    done


done
