import os
import sys
from glob import glob
import subprocess

wavdir = sys.argv[sys.argv.index('-w') + 1]
savedir = sys.argv[sys.argv.index('-s') + 1]

subprocess.call('mkdir -p %s' %(savedir), shell=True)

wavs = glob(os.path.join(wavdir, '*.wav'))

for i, wav in enumerate(wavs):
    base = os.path.splitext(os.path.basename(wav))[0]
    
    filename = base.rsplit('_', 1)[0]
    times = base.split('_')[-1].split('-')
    
    t1 = float(times[0])
    t2 = float(times[1])
    
    subprocess.call('auditok -i %s -r 8000 -n 0.5 -m 1.0 -s 0.1 -d True > /tmp/tmp_audi.txt' %(wav), shell=True)
    
    temp_audi = open('/tmp/tmp_audi.txt').readlines()
    for line in temp_audi:
        split = line.split()
        dt1 = float(split[1])
        dt2 = float(split[2])
        
        new_filename = '%s_%s-%s.wav' % (filename, str(round(t1 + dt1, 2)), str(round(t1 + dt2, 2)))
        
        subprocess.call('sox %s %s trim %s %s' % (wav, os.path.join(savedir, new_filename), str(dt1), str(dt2 - dt1)), shell=True)
    
    print('Finished processing %s' %(wav))

