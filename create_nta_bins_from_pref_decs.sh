#!/bin/bash

SCRIPTS_HOME=/home/muneeb/git/scripts
SPEC_HOME=/home/muneeb/spec2006_static

for BENCH in soplex #lbm mcf
do

    BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

    cd ${BENCH_DIR}

    ASM_SRC_FILE=${BENCH}_protean.s
    EXEC_FILE=${BENCH}_protean.frmasm

    for NTA_POLICY in $(seq 0 2)
    do

        OPT_EXE_BASE_NAME=${BENCH}_protean_ntap${NTA_POLICY}
        ASM_OUTFILE=${OPT_EXE_BASE_NAME}.s

        PREF_DEC_FILE=${SCRIPTS_HOME}/${BENCH}_protean.ntap${NTA_POLICY}

        ${SCRIPTS_HOME}/insert_pref.py -i ${ASM_SRC_FILE} -o ${ASM_OUTFILE} -f ${PREF_DEC_FILE} -e ${EXEC_FILE}

        /home/muneeb/llvm-3.3/Release+Asserts/bin/clang -O3 -sbo ${ASM_OUTFILE} -o ${OPT_EXE_BASE_NAME}.sbo.nobc -L/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime -lSBO_runtime -ldl -lrt  -Wl,--export-dynamic

        objcopy --add-section .sbo_ir=${BENCH}_protean.sbo.ll ${OPT_EXE_BASE_NAME}.sbo.nobc ${OPT_EXE_BASE_NAME}.frmasm

        NTA_COUNT=$(/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-objdump -d ${OPT_EXE_BASE_NAME}.frmasm | grep 'prefetchnta' | wc -l)

        echo ${NTA_COUNT}" NTAs inserted in "${OPT_EXE_BASE_NAME}.frmasm


    done


done
