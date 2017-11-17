import functools
import json
import multiprocessing
import os
import shutil
import subprocess
import sys

sys.path.append('/home/gvelchuru/')

from OpenFaceScripts.runners.VidCropper import duration
from OpenFaceScripts.scoring import AUScorer
from OpenFaceScripts.helpers.SecondRunHelper import height_width, get_vid_from_dir


import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.animation as manimation
import matplotlib.pyplot as plt
import progressbar
from sklearn.externals import joblib


from pathos.multiprocessing import ProcessingPool as Pool

OpenDir = sys.argv[sys.argv.index('-d') + 1]
os.chdir(OpenDir)


def bar_movie(vid, vid_dir, times, corr):
    FFMpegWriter = manimation.writers['ffmpeg']
    metadata = dict(title='Movie Test', artist='Matplotlib',
                    comment='Movie support!')
    writer = FFMpegWriter(fps=len(times) / duration(vid), metadata=metadata)

    test_line = os.path.join(vid_dir, 'writer_test_line.mp4')

    norm = plt.Normalize()
    colors = plt.cm.jet(norm(corr))

    fig = plt.figure(figsize=(14, 2))
    ax = fig.add_subplot(111)

    li, = ax.plot(times, corr)
    vl = ax.vlines(0, 0, 1)

    with writer.saving(fig, test_line, 100):
        for i in range(len(times)):
            # sys.stdout.write('{:.2f} {}/{}\r'.format(100 * i / len(times), i, len(times)))
            # sys.stdout.flush()

            low = max(i - 50, 0)
            high = min(i + 51, len(times) - 1)
            vl.set_segments([[[times[i], 0], [times[i], 1]]])
            fig.canvas.draw()
            writer.grab_frame()
    orig = .269
    width = height_width(vid)[1]
    subprocess.Popen('ffmpeg -loglevel quiet -y -i {0} -vf "movie={1}, '
                     'scale={width}:-1, format=argb, colorchannelmixer=aa=.75 [inner]; [in][inner] overlay=.269 [out]" '
                     '-strict -2 {2}'.format(vid, test_line, os.path.join(vid_dir, 'completed_{0}.mp4'.format(
        os.path.basename(vid).replace('.avi', ''))),
                                             width=width),
                     shell=True).wait()
    plt.close()


scores_file = 'au_emotes.txt'
scores = json.load(open(scores_file))
classifier = joblib.load('happy_trained_RandomForest_with_pose.pkl')


def mark_vid_dir(out_q, vid_dir):
    if 'inter_out.avi' not in os.listdir(vid_dir):
        shutil.copy(get_vid_from_dir(vid_dir), os.path.join(vid_dir, 'inter_out.avi'))
    vid = os.path.join(vid_dir, 'out.avi')

    emotion_data = []
    scores_dict = scores[os.path.basename(vid_dir)]
    for frame in range(int(duration(vid) * 30)):
        if str(frame) in scores_dict:
            emotion_data.append(scores_dict[str(frame)])
        else:
            emotion_data.append(None)

    aus_list = AUScorer.AUList

    predicted_arr = []
    for frame in emotion_data:
        if frame:
            aus = frame[0]
            au_data = ([float(aus[str(x)]) for x in aus_list])
            predicted = classifier.predict_proba(np.array(au_data).reshape(1, -1))[0]
            predicted_arr.append(predicted)
        else:
            predicted_arr.append(np.array([0, 0]))

    times = [x for x in range(0, len(predicted_arr), 10)]
    corr = [predicted_arr[a][1] for a in times]

    # bar_movie(vid, vid_dir, times, corr)
    # bar_movie(os.path.join(vid_dir, 'inter_out.avi'), vid_dir, times, corr)

    subprocess.Popen('ffmpeg -loglevel quiet -y -i {1} -i {2} -filter_complex "[0:v]pad=iw*2:ih[int];[int]['
                     '1:v]overlay=W/2:0[vid]" -map [vid] -c:v libx264 -crf 23 -preset veryfast {0}'.format(
        os.path.join(vid_dir, 'combined_out.avi'), vid, os.path.join(vid_dir, 'inter_out.avi')), shell=True).wait()

    bar_movie(os.path.join(vid_dir, 'combined_out.avi'), vid_dir, times, corr)

    out_q.put({vid_dir: sum(corr) / len(corr)})


vids_file = 'happy_predic_vids.txt'
vids_done = {}
original_len = len(vids_done)
files = [x for x in (os.path.join(OpenDir, vid_dir) for vid_dir in os.listdir(OpenDir)) if
         (os.path.isdir(x) and 'au.txt' in os.listdir(x))]
if os.path.exists(vids_file):
    vids_done = json.load(vids_file)
remaining = [x for x in files if x not in vids_done]
out_q = multiprocessing.Manager().Queue()
f = functools.partial(mark_vid_dir, out_q)
bar = progressbar.ProgressBar(redirect_stdout=True, max_value=len(remaining))
for i, _ in enumerate(Pool().imap(f, remaining), 1):
    bar.update(i)
while not out_q.empty():
    vids_done.update(out_q.get())
if len(vids_done) != original_len:
    json.dump(vids_done, open(scores_file, 'w'))
