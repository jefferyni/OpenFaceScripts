import numpy as np
import sys
import subprocess
import os

AUDI = sys.argv[sys.argv.index('-a') + 1]
FACE = sys.argv[sys.argv.index('-f') + 1]
WAV = sys.argv[sys.argv.index('-w') + 1]
PATIENTS = sys.argv[sys.argv.index('-p') + 1]
NONPATIENTS = sys.argv[sys.argv.index('-n') + 1]
THRESH = float(sys.argv[sys.argv.index('-t') + 1])

audi = open(AUDI).readlines()
face = open(FACE).readlines()

frames = {}
for i, line in enumerate(face):
    if i != 0:
        split = line.split()
        
        frame = int(split[0])
        au25_c = int(split[1])
        au26_c = int(split[2])
        conf = float(split[5])
        state = split[6]

        if au25_c == 1:
            au25_r = float(split[3])
        else:
            au25_r = 0.0

        if au26_c == 1:
            au26_r = float(split[4])
        else:
            au26_r = 0.0

        if conf >= 0.80:
            if (au25_c == 1 and au25_r > 1.00) or (au26_c == 1 and au26_r > 1.00):
                frames[frame] = bool(True)
            else:
                frames[frame] = bool(False)
        

speechtimes = {}
nonspeechtimes = {}

for i, line in enumerate(audi):
    split = line.split()
    t1 = float(split[1])
    t2 = float(split[2])
    f1 = int(t1 * 30)
    f2 = int(t2 * 30)
    
    if t2 - t1 >= 2.0:
        turns = 0
        numopenframes = 0
        numcloseframes = 0
        state = None
        for j in range(f1, f2 + 1):
            if j in frames:
                if frames[j] != state:
                    turns += 1
                    state = frames[j]
                if not frames[j]:
                    numcloseframes += 1
                else:
                    numopenframes += 1

        turns = max(turns, 1)
        if (f2 - f1 + 1) / turns < THRESH and (numopenframes + numcloseframes) / (f2 - f1 + 1) > 0.8:
            speechtimes[t1] = t2
        elif numcloseframes / (f2 - f1 + 1) > 0.9:
            nonspeechtimes[t1] = t2

filename = os.path.splitext(os.path.basename(WAV))[0]
path = os.path.dirname(WAV)
subprocess.call('mkdir -p %s' % (PATIENTS), shell=True)
subprocess.call('mkdir -p %s' % (NONPATIENTS), shell=True)

for time in speechtimes:
    new_filename = '%s_%s-%s.wav' % (filename, str(time), str(speechtimes[time]))
    newWAV = os.path.join(PATIENTS, new_filename)
    subprocess.call('sox %s %s trim %s %s' % (WAV, newWAV, time, speechtimes[time] - time), shell=True)

for time in nonspeechtimes:
    new_filename = '%s_%s-%s.wav' % (filename, str(time), str(nonspeechtimes[time]))
    newWAV = os.path.join(NONPATIENTS, new_filename)
    subprocess.call('sox %s %s trim %s %s' % (WAV, newWAV, time, nonspeechtimes[time] - time), shell=True)



