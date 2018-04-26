#!/bin/bash

wavs=${1%/}
saves=${2%/}

mkdir -p $saves

for wav in $wavs/*.wav
do
  base=$(basename $wav)
  basebase=${base%.wav}
  
  auditok -i $wav -r 8000 -n 1.0 -m 5.0 -d True > $saves/$basebase.txt
  
  echo file saved at $saves/$basebase.txt
done

