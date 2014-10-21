#!/bin/bash

SCRIPTS_HOME=/home/muneeb/git/scripts
SPEC_HOME=/home/muneeb/spec2006_static

INFILE=${1}

for BENCH in sphinx #bzip2 milc libquantum omnetpp astar xalan lbm soplex mcf
do

    echo "\nprocessing "${BENCH}" NTA binaries..."

    BENCH_DIR=${SPEC_HOME}/*${BENCH}*/src.clean

    cd ${BENCH_DIR}

    ASM_SRC_FILE=${BENCH}_protean.s
    EXEC_FILE=${BENCH}_protean.frmasm

    for LINES in $(seq 2 16)
    do

        rm -f .tmp

        OPT_EXE_BASE_NAME=${BENCH}_protean_nta_$((${LINES}-1))
        ASM_OUTFILE=${OPT_EXE_BASE_NAME}.s

        for CURR_LINE in $(seq 2 ${LINES})
        do
            ADDR=$(sed ${CURR_LINE}'q;d' ${SCRIPTS_HOME}/${BENCH}_protean.perinsntabw | awk '{print $1}')
            echo ${ADDR}':nta:0' >> .tmp
        done

        ${SCRIPTS_HOME}/insert_pref.py -i ${ASM_SRC_FILE} -o ${ASM_OUTFILE} -f .tmp -e ${EXEC_FILE}

        BENCH_LDFLAGS=$(grep "BENCH_LDFLAGS=" Makefile.clang | tr -d 'BENCH_LDFLAGS=')

        BENCHLANG=$(grep "BENCHLANG=" Makefile.clang | tr -d 'BENCHLANG=')

        if [[ ${BENCHLANG} == "C" ]]
        then
            BENCHLANG=/home/muneeb/llvm-3.3/Release+Asserts/bin/clang
        else
            BENCHLANG=/home/muneeb/llvm-3.3/Release+Asserts/bin/clang++
        fi

        ${BENCHLANG} -O3 -sbo ${ASM_OUTFILE} -o ${OPT_EXE_BASE_NAME}.sbo.nobc -L/home/muneeb/llvm-3.3/lib/Transforms/SBO/runtime -lSBO_runtime -ldl -lrt ${BENCH_LDFLAGS} -Wl,--export-dynamic

        objcopy --add-section .sbo_ir=${BENCH}_protean.sbo.ll ${OPT_EXE_BASE_NAME}.sbo.nobc ${OPT_EXE_BASE_NAME}.frmasm

        rm ${OPT_EXE_BASE_NAME}.sbo.nobc

        NTA_COUNT=$(/home/muneeb/llvm-3.3/Release+Asserts/bin/llvm-objdump -d ${OPT_EXE_BASE_NAME}.frmasm | grep 'prefetchnta' | wc -l)

        echo ${NTA_COUNT}" NTAs inserted in "${OPT_EXE_BASE_NAME}.frmasm


    done


done
