#!/bin/bash

DATA_DIR=../

for BENCH in lbm #mcf soplex
do

    OUTFILE=${BENCH}_perins_mr.gnuplot

    echo "#!/usr/local/bin/gnuplot" > ${OUTFILE}

    echo "set term postscript eps enhanced color font 'Helvetica,18' size 29cm,200cm" >> ${OUTFILE}
    echo "set output '"${BENCH}_perins_mr.eps"'" >> ${OUTFILE}

    echo "load \""colors.gnuplot"\"" >> ${OUTFILE}

    echo "unset title" >> ${OUTFILE}
    echo "set key bmargin center Left nobox horiz reverse samplen 3" >> ${OUTFILE}
    echo "set yrange [0:105]" >> ${OUTFILE}
    echo "set xrange [32:8192]" >> ${OUTFILE}
    echo "set ylabel \"miss ratio(%)\"" >> ${OUTFILE}
    echo "set xlabel \"cache size\"" >> ${OUTFILE}
    echo "set border 15" >> ${OUTFILE}
#    echo "set logscale x" >> ${OUTFILE}

    echo "K=1024" >> ${OUTFILE}

    echo "set xtics(\"32k\" 32, \"256k\" 256, \"1M\" 1*K, \"2M\" 2*K, \"4M\" 4*K, \"6M\" 6*K, \"8M\" 8*K)" >> ${OUTFILE}
    echo "set xtics rotate by -45 offset character 0,0,0" >> ${OUTFILE}

    echo "set rmargin 3.5" >> ${OUTFILE}

    echo "set multiplot" >> ${OUTFILE}
    echo "set size 0.45,0.025" >> ${OUTFILE}

    X=0.0
    Y=0.95
    XSTEP=0.45
    YSTEP=0.035

    IMR_LINE=3
    FMR_LINE=7

    for IDX in $(seq 1 43)
    do
        echo "set origin "${X}","${Y} >> ${OUTFILE}

        ITITLE=$(sed -n $((${IMR_LINE}-1)),$((${IMR_LINE}-1))p ../data/${BENCH}_protean.perinsmsr |  sed 's/^.*pc:/pc:/'  | sed 's/l2-l3[^l]*$//')

        echo "set title '"${IDX}".   "${ITITLE}"'" >> ${OUTFILE}

        echo "plot \"<(sed -n '"${IMR_LINE}","$((${IMR_LINE}+2))"p' ../data/"${BENCH}"_protean.perinsmsr)\" using 1:(\$2*100) ls 1 lw 4 w linespoints noti" >> ${OUTFILE}

        RTITLE=$(sed -n $((${IMR_LINE}-1)),$((${IMR_LINE}-1))p ../data/${BENCH}_protean.perinsmsr |  sed 's/^.*l2-l3-reuse-freq:/l2-l3-reuse-freq:/')

        echo "set title '"${RTITLE}"'" >> ${OUTFILE}

        X=$(echo ${X}"+"${XSTEP} | bc -l)
        echo "set origin "${X}","${Y} >> ${OUTFILE}
        echo "plot \"<(sed -n '"${FMR_LINE}","$((${FMR_LINE}+9))"p' ../data/"${BENCH}"_protean.perinsmsr)\" using 1:(\$2*100) ls 2 lw 4 w linespoints noti" >> ${OUTFILE}
        X=0
        Y=$(echo ${Y}"-"${YSTEP} | bc -l)

        IMR_LINE=$((${IMR_LINE}+17))
        FMR_LINE=$((${FMR_LINE}+17))
    done


    echo "unset ylabel" >> ${OUTFILE}
    echo "unset xlabel" >> ${OUTFILE}
    echo "unset xtics" >> ${OUTFILE}
    echo "unset ytics" >> ${OUTFILE}
    echo "unset border" >> ${OUTFILE}
    echo "set size 1.0, 0.01" >> ${OUTFILE}
    echo "set origin 0.0,0.98" >> ${OUTFILE}
    echo "unset title" >> ${OUTFILE}
    echo "plot -1 w lp ti \"Instruction-MR\" ls 1,-1 w lp ti \"FWD-L3-reuse\" ls 2" >> ${OUTFILE}

    echo "replot" >> ${OUTFILE}

    chmod a+x ${OUTFILE}

    ./${OUTFILE}
    open ${BENCH}_perins_mr.eps
done