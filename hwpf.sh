#!/bin/bash

SETTINGS=${1}

VAL=0

if [ ${SETTINGS} == "off" ]
then
	VAL=15	
else
	VAL=0
fi

modprobe msr

for CPU in $(seq 0 7)
do

	wrmsr -p${CPU} 0x1a4 ${VAL}
	rdmsr -p${CPU} 0x1a4
	
done
