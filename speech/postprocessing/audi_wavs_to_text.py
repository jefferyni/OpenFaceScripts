import os
import sys
from glob import glob
import subprocess

wavdir = sys.argv[sys.argv.index('-w') + 1]
subprocess.call('rm -rf %s' %(os.path.join(wavdir, '*.txt')), shell=True)

wavs = glob(os.path.join(wavdir, '*.wav'))

for i, wav in enumerate(wavs):
    filename = os.path.basename(wav)
    basefile, _ = os.path.splitext(filename)
    
    split_base = basefile.rsplit('_', 1)[-1].split('-')
    

    t1 = float(split_base[0])
    t2 = float(split_base[1])

    f1 = int(t1 * 30)
    f2 = int(t2 * 30)
    
    with open(os.path.join(wavdir, basefile.rsplit('_', 1)[0] + '.txt'), 'a') as text:
        text.write('%s\t%s \n' %(f1, f2))


