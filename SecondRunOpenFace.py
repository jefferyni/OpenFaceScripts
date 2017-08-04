"""
.. module SecondRunOpenFace
    :synopsis: Module for use after an initial run of OpenFace on a video set, attempts to rerun on the videos
        that OpenFace could not recognize a face in the first time.
"""
import functools
import glob
import json
import os
import sys
import progressbar
import multiprocessing
import subprocess
import copy

from collections import defaultdict
from pathos.multiprocessing import ProcessingPool as Pool

import cv2
import numpy as np

sys.path.append('/home/gvelchuru/')
from OpenFaceScripts import AUScorer, CropAndOpenFace, VidCropper


def make_more_bright(ims, i):
    """
    Makes an image brighter.

    :param ims: List of image names.
    :param i: Index of image within ims.
    """
    name = ims[i]
    im = cv2.imread(name)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype("float64")
    h, s, v = cv2.split(hsv)
    change = 50
    v += np.float64(change)
    v = np.clip(v, 0, 255)
    final_hsv = cv2.merge((h, s, v))
    im = cv2.cvtColor(final_hsv.astype("uint8"), cv2.COLOR_HSV2BGR)
    cv2.imwrite(name, im)
    print(name)


def height_width(vid_file_path):
    """
    Gets height and width of a video.
    :param vid_file_path: Path to video.
    :return: [Vid height, Vid width]
    """
    _json = VidCropper.probe(vid_file_path)

    if 'streams' in _json:
        height = None
        width = None
        for s in _json['streams']:
            if 'height' in s:
                height = s['height']
            if 'width' in s:
                width = s['width']
            if height and width:
                return [height, width]

    raise Exception('No Height and Width found')


def get_dimensions(vid_dir):
    with open(os.path.join(vid_dir, 'bb_arr.txt')) as bb_file:
        lines = bb_file.readlines()
        if lines[0] == 'None\n' and lines[1] == 'None\n' and lines[2] == 'None\n' and lines[3] == 'None\n':
            return [None, None, None, None, int(lines[5])]
        return {
            'x_min': int(lines[0]),
            'y_min': int(lines[1]),
            'x_max': int(lines[2]),
            'y_max': int(lines[3]),
            'rescale_factor': int(lines[5])
        }


def throw_vid_in_reverse(vid_dir, include_eyebrows):
    """
    Reverse a video and run OpenFace on it.
    :param vid_dir: Crop directory for video (created from CropAndOpenFace)
    :return: Dictionary with emotions detected from reversed video
    """
    vid = get_vid_from_dir(vid_dir)
    out_dir = os.path.join(vid_dir, 'reverse')
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    if 'au.txt' not in os.listdir(out_dir):
        subprocess.Popen("ffmpeg -y -i {0} -vf reverse {1}".format(vid, os.path.join(out_dir, 'inter_out.avi')),
                         shell=True).wait()
        CropAndOpenFace.run_open_face(out_dir, vid_mode=True, remove_intermediates=True)
    old_scorer = AUScorer.AUScorer(vid_dir, 0, include_eyebrows)
    new_scorer = AUScorer.AUScorer(out_dir, 0, include_eyebrows)
    num_frames = int(VidCropper.duration(os.path.join(vid_dir, 'out.avi')) * 30)
    new_dict = None
    if len(old_scorer.emotions) > 0 or len(new_scorer.emotions) > 0:
        new_dict = {num_frames - i: k for i, k in new_scorer.emotions.items()}
        old_dict = copy.copy(old_scorer.emotions)
        new_dict.update(old_dict)
    return new_dict


def re_crop(vid, original_crop_coords, scorer, out_dir):
    vid_height, vid_width = height_width(vid)
    min_x = None
    max_x = None
    min_y = None
    max_y = None

    if 'x_min' not in original_crop_coords:
        original_crop_coords = {
            'x_min': 0,
            'y_min': 0,
            'x_max': vid_width,
            'y_max': vid_height,
            'rescale_factor': original_crop_coords[4]
        }
    bb_arr = []  # min_x, min_y, max_x, max_y
    for frame in scorer.emotions:
        if frame in scorer.x_y_dict:
            rescale_factor = original_crop_coords['rescale_factor']
            x_y_dict = scorer.x_y_dict[frame]
            x_arr = [x / rescale_factor for v, x in x_y_dict.items() if 'x_' in v]
            y_arr = [y / rescale_factor for v, y in x_y_dict.items() if 'y_' in v]
            min_x = min(x_arr)
            min_y = min(y_arr)
            max_x = max(x_arr)
            max_y = max(y_arr)
            if not bb_arr:
                bb_arr = [min_x, min_y, max_x, max_y]
            else:
                bb_arr = [min(min_x, bb_arr[0]), min(min_y, bb_arr[1]), max(max_x, bb_arr[2]),
                          max(max_y, bb_arr[3])]
    offset = 50

    if not min_x:
        min_x = original_crop_coords['x_min']
    if not max_x:
        max_x = original_crop_coords['x_max']
    if not max_y:
        max_y = original_crop_coords['y_max']
    if not min_y:
        min_y = original_crop_coords['y_min']

    x_arr = np.clip(
        [original_crop_coords['x_min'] + min_x - offset, original_crop_coords['x_min'] + max_x + offset], 0,
        vid_width)
    y_arr = np.clip(
        [original_crop_coords['y_min'] + min_y - offset, original_crop_coords['y_min'] + max_y + offset], 0,
        vid_height)

    min_x = x_arr[0]
    min_y = y_arr[0]
    max_x = x_arr[1]
    max_y = y_arr[1]
    width = max_x - min_x
    height = max_y - min_y
    if 'au.txt' not in os.listdir(out_dir):
        VidCropper.crop_and_resize(vid, width, height, min_x, min_y, out_dir, 5)
        CropAndOpenFace.run_open_face(out_dir, vid_mode=True, remove_intermediates=True)
    new_scorer = AUScorer.AUScorer(out_dir)
    return new_scorer.emotions


def reverse_re_crop_vid_dir(vid_dir, include_eyebrows):
    reverse_vid_dir = os.path.join(vid_dir, 'reverse')
    scorer = AUScorer.AUScorer(reverse_vid_dir, 0, include_eyebrows)
    if scorer.emotions:
        out_dir = os.path.join(reverse_vid_dir, 're_crop')
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)
        vid = glob.glob(os.path.join(reverse_vid_dir, '*.avi'))[0]
        original_crop_coords = get_dimensions(vid_dir)
        return re_crop(vid, original_crop_coords, scorer, out_dir)


def re_crop_vid_dir(vid_dir, include_eyebrows):
    scorer = AUScorer.AUScorer(vid_dir, 0, include_eyebrows)
    if scorer.emotions:
        out_dir = os.path.join(vid_dir, 're_crop')
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)
        vid = get_vid_from_dir(vid_dir)
        original_crop_coords = get_dimensions(vid_dir)
        return re_crop(vid, original_crop_coords, scorer, out_dir)


def process_vid_dir(eyebrow_dict, queue, vid_dir):
    out_dict = {vid_dir: []}
    if vid_dir in eyebrow_dict['Eyebrows']:
        include_eyebrows = True
    else:
        include_eyebrows = False
    orig_dict = AUScorer.AUScorer(vid_dir).emotions
    func_dict = [(re_crop_vid_dir, 'cropped'), (throw_vid_in_reverse, 'reversed'), (reverse_re_crop_vid_dir,  'rev_cropped')]

    for func, name in func_dict:
        post_func_dict = func(vid_dir, include_eyebrows)
        if post_func_dict:
            diff = len([x for x in post_func_dict if x not in orig_dict])
            orig_dict.update(post_func_dict)
            out_dict[vid_dir].append('{0}: {1}'.format(name, diff))

    json.dump(orig_dict, open(os.path.join(vid_dir, 'all_dict.txt'), 'w'))
    queue.put(out_dict)


def get_vid_from_dir(vid_dir):
    """
    Returns the full path to a video associated with a crop directory.

    :param vid_dir: The crop directory.
    :return: The full path to a video associated with a crop directory.
    """
    return os.path.join(os.path.dirname(vid_dir), (vid_dir.replace('_cropped', '') + '.avi'))


def process_eyebrows(dir, file):
    exact_dict = {'Eyebrows': [], 'No Eyebrows': []}
    lines = file.read().splitlines()
    if lines[0] == "eyebrows:":
        eyebrow_mode = True
        for line in (x for x in lines if x):
            if line == "no eyebrows:":
                eyebrow_mode = False
            crop_dir = os.path.join(dir, line + '_cropped')
            if os.path.exists(crop_dir):
                if eyebrow_mode:
                    exact_dict['Eyebrows'].append(crop_dir)
                else:
                    exact_dict['No Eyebrows'].append(crop_dir)
        for line in (x for x in lines if x):
            if line == "no eyebrows:":
                eyebrow_mode = False
            crop_dir = os.path.join(dir, line + '_cropped')
            if not os.path.exists(crop_dir):
                if eyebrow_mode:
                    exact_dict['Eyebrows'] += [x for x in os.listdir(dir) if os.path.isdir(os.path.join(dir, x)) and line in x and os.path.join(dir, x) not in exact_dict['No Eyebrows']]
                else:
                    exact_dict['No Eyebrows'] += [x for x in os.listdir(dir) if os.path.isdir(os.path.join(dir, x)) and line in x and os.path.join(dir, x) not in exact_dict['No Eyebrows']]
    for eyebrow_dir in exact_dict['No Eyebrows']:
        if eyebrow_dir in exact_dict['Eyebrows']:
            exact_dict['Eyebrows'].remove(eyebrow_dir)
    return exact_dict

if __name__ == '__main__':
    patient_directory = sys.argv[sys.argv.index('-od') + 1]
    second_runner_files = os.path.join(patient_directory, 'edited_files.txt')
    already_ran = json.load(open(second_runner_files)) if os.path.exists(second_runner_files) else {}
    files = [x for x in (os.path.join(patient_directory, vid_dir) for vid_dir in os.listdir(patient_directory)) if
             (os.path.isdir(x) and 'au.txt' in os.listdir(
                 x) and x not in already_ran)]
    out_q = multiprocessing.Manager().Queue()
    eyebrow_file = os.path.join(patient_directory, 'eyebrows.txt')
    eyebrow_dict = process_eyebrows(patient_directory, open(eyebrow_file)) if os.path.exists(eyebrow_file) else {}
    f = functools.partial(process_vid_dir, eyebrow_dict, out_q)
    bar = progressbar.ProgressBar(redirect_stdout=True, max_value=1)
    for i, _ in enumerate(Pool().imap(f, files), 1):
        bar.update(i/len(files))

    while not out_q.empty():
        already_ran.update(out_q.get())
    json.dump(already_ran, open(second_runner_files, 'w'), indent='\t')
