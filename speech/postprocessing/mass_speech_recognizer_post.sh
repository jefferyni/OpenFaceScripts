#!/bin/bash

audi=${1%/}
face=${2%/}
wavs=${3%/}
patients=${4%/}
nonpatients=${5%/}
thresh=${6%/}

for file in $face/*.txt
do
  base=$(basename $file)
  basebase=${base%.txt}
  
  if [[ -f $audi/$basebase.txt && -f $wavs/$basebase.wav ]]
  then
    python3 /home/jeffery/OpenFaceScripts/speech/postprocessing/speech_recognizer_post.py -a $audi/$basebase.txt -f $face/$basebase.txt -w $wavs/$basebase.wav -p $patients -n $nonpatients -t $thresh
  fi

  echo $basebase done processing
  echo ""
done


