#!/bin/bash

SCRIPTS_HOME=/home/muneeb/git/scripts
SPEC_HOME=/home/muneeb/spec2006_static

for BENCH in mcf #lbm
do

    BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

    cd ${BENCH_DIR}

    ASM_SRC_FILE=${BENCH}_protean.s
    EXEC_FILE=${BENCH}_protean.frmasm

    for LINES in $(seq 2 16)
    do

        rm -f .tmp

        OPT_EXE_BASE_NAME=${BENCH}_protean_nta$((${LINES}-1))
        ASM_OUTFILE=${OPT_EXE_BASE_NAME}.s

        for CURR_LINE in $(seq 2 ${LINES})
        do
            ADDR=$(sed ${CURR_LINE}'q;d' ${SCRIPTS_HOME}/${BENCH}_protean.perinsntabw | awk '{print $1}')
            echo ${ADDR}':nta:0' >> .tmp

        done

        ${SCRIPTS_HOME}/insert_pref.py -i ${ASM_SRC_FILE} -o ${ASM_OUTFILE} -f .tmp -e ${EXEC_FILE}

        /home/muneeb/llvm-3.3/Release+Asserts/bin/clang -O3 -sbo ${ASM_OUTFILE} -o ${OPT_EXE_BASE_NAME}.sbo.nobc -L/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime -lSBO_runtime -ldl -lrt  -Wl,--export-dynamic

        objcopy --add-section .sbo_ir=${BENCH}_protean.sbo.ll ${OPT_EXE_BASE_NAME}.sbo.nobc ${OPT_EXE_BASE_NAME}.frmasm

        NTA_COUNT=$(/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-objdump -d ${OPT_EXE_BASE_NAME}.frmasm | grep 'prefetchnta' | wc -l)

        echo ${NTA_COUNT}" NTAs inserted in "${OPT_EXE_BASE_NAME}.frmasm


    done


done




#./insert_pref.py -i ~/spec2006_static/470.lbm/src.clean/lbm_protean.s -o ~/protean/lbm_protean_opt.s -f ~/protean/lbm_protean.cons -e ~/spec2006_static/470.lbm/src.clean/lbm_protean.frmasm