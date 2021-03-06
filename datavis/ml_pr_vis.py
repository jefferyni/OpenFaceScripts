import functools
import glob
import json
import sys

import progressbar
from sklearn.model_selection import train_test_split

sys.path.append('/home/gvelchuru/OpenFaceScripts')

from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier, ExtraTreesClassifier
from sklearn.metrics import precision_recall_curve

from scoring import AUScorer

import multiprocessing
import numpy as np
import os

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from collections import defaultdict
from progressbar import ProgressBar
from pathos.multiprocessing import ProcessingPool as Pool
from sklearn.naive_bayes import GaussianNB, BernoulliNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC

all_emotions = AUScorer.emotion_list()
all_emotions.extend(['Neutral', 'Sleeping'])


def use_classifier(classifier, au_train, au_test, target_train, target_test):
    classifier.fit(au_train, target_train)
    expected = target_test
    decision_function = classifier.predict_proba(au_test)[:, 1]
    return expected, decision_function


def thresh_calc(out_q, short_patient, thresh):
    curr_dict = {
        thresh: {emotion: {'true_neg': 0, 'false_neg': 0, 'true_pos': 0, 'false_pos': 0} for emotion in all_emotions}}
    for patient in [x for x in scores if x in csv_file and short_patient in x]:
        for vid in scores[patient]:
            curr_vid_dict = scores[patient][vid]
            csv_vid_dict = csv_file[patient][vid]
            for frame in curr_vid_dict:
                if frame in csv_vid_dict and csv_vid_dict[frame]:
                    actual = csv_vid_dict[frame][2]
                else:
                    actual = None
                if actual:
                    if actual in curr_vid_dict[frame]:
                        score = curr_vid_dict[frame][actual]
                    else:
                        score = 0
                    # curr_dict[thresh][actual]['total_pos'] += 1 Try labeling components
                    for other_emotion in (x for x in curr_dict[thresh] if x != actual):
                        if other_emotion in curr_vid_dict[frame]:
                            other_score = curr_vid_dict[frame][other_emotion]
                        else:
                            other_score = 0
                        if other_score >= thresh:
                            curr_dict[thresh][other_emotion]['false_pos'] += 1
                        else:
                            curr_dict[thresh][other_emotion]['true_neg'] += 1
                    if score >= thresh:
                        curr_dict[thresh][actual]['true_pos'] += 1
                    else:
                        curr_dict[thresh][actual]['false_neg'] += 1

    out_q.put(curr_dict)


def clean_csv(csv_file):
    out_dict = {}
    for direc in csv_file:
        remove_crop = direc.replace('_cropped', '')
        dir_num = remove_crop[len(remove_crop) - 4:len(remove_crop)]
        patient_name = remove_crop.replace('_' + dir_num, '')
        if patient_name not in out_dict:
            out_dict[patient_name] = {}
        out_dict[patient_name][str(int(dir_num))] = csv_file[direc]

    return out_dict


def validate_thresh_dict(thresh_dict):
    thresh_list = sorted(thresh_dict.keys())
    for index, thresh in enumerate(thresh_list):
        if index:
            prev_thresh = thresh_list[index - 1]
            assert thresh > prev_thresh
            for emotion in thresh_dict[thresh]:

                total_pos = thresh_dict[thresh][emotion]['true_pos'] + thresh_dict[thresh][emotion]['false_neg']
                prev_total_pos = thresh_dict[prev_thresh][emotion]['true_pos'] + thresh_dict[prev_thresh][emotion][
                    'false_neg']
                assert total_pos == prev_total_pos

                total_neg = thresh_dict[thresh][emotion]['false_pos'] + thresh_dict[thresh][emotion]['true_neg']
                prev_total_neg = thresh_dict[prev_thresh][emotion]['false_pos'] + thresh_dict[prev_thresh][emotion][
                    'true_neg']
                assert total_neg == prev_total_neg

                # false positive decreases, true negative increases
                assert thresh_dict[thresh][emotion]['false_pos'] <= thresh_dict[prev_thresh][emotion]['false_pos']

                # true positive decreases, false negative increases
                assert thresh_dict[thresh][emotion]['true_pos'] <= thresh_dict[prev_thresh][emotion]['true_pos']

                # assert that recall is monotonically decreasing
                if total_pos:
                    assert thresh_dict[thresh][emotion]['true_pos'] / total_pos <= thresh_dict[prev_thresh][emotion][
                                                                                       'true_pos'] / prev_total_pos


def make_emotion_data(emotion, short_patient):
    if short_patient == "all":
        diction = json.load(open('au_emotes.txt'))
        emotion_data = [item for sublist in
                        [b for b in
                         [[a for a in x.values() if a] for x in diction.values() if x]
                         if b]
                        for item in sublist]

        ck_dict = json.load(open('ck_dict.txt'))
        for patient_list in ck_dict.values():
            to_add = AUScorer.TrainList
            au_dict = {str(int(float(x))): y for x, y in patient_list[0].items()}
            for add in to_add:
                if add not in au_dict:
                    au_dict[add] = 0
            emotion_data.append([au_dict, patient_list[1]])

        au_data = []
        target_data = []
        aus_list = AUScorer.TrainList
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] == emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                target_data.append(1)
        index = 0
        happy_len = len(target_data)
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] and frame[1] != emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                target_data.append(0)
                index += 1
            if index == happy_len:
                break

        au_train, au_test, target_train, target_test = train_test_split(au_data, target_data, test_size=.1)
        return au_train, au_test, target_train, target_test
    else:
        au_emote_dict = json.load(open('au_emotes.txt'))
        keys = [x for x in au_emote_dict if short_patient not in x]
        values = [au_emote_dict[x] for x in keys if x]
        emotion_data = [item for sublist in
                        [b for b in [[a for a in x.values() if a] for x in values]
                         if b]
                        for item in sublist if item[1]]

        ck_dict = json.load(open('ck_dict.txt'))
        for patient_list in ck_dict.values():
            to_add = AUScorer.TrainList
            au_dict = {str(int(float(x))): y for x, y in patient_list[0].items()}
            for add in to_add:
                if add not in au_dict:
                    au_dict[add] = 0
            emotion_data.append([au_dict, patient_list[1]])

        au_data = []
        target_data = []
        aus_list = AUScorer.TrainList
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] == emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                # target_data.append(frame[1])
                target_data.append(1)
        index = 0
        happy_len = len(target_data)
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] and frame[1] != emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                # target_data.append('Neutral/Sleeping')
                target_data.append(0)
                index += 1
            if index == happy_len:
                break
        au_train = au_data.copy()
        target_train = target_data.copy()
        n_samples = len(au_data)

        keys = [x for x in au_emote_dict if short_patient in x]
        values = [au_emote_dict[x] for x in keys if x]
        emotion_data = [item for sublist in
                        [b for b in [[a for a in x.values() if a] for x in values]
                         if b]
                        for item in sublist]
        au_data = []
        target_data = []
        aus_list = AUScorer.TrainList
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] == emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                # target_data.append(frame[1])
                target_data.append(1)
        for frame in emotion_data:
            aus = frame[0]
            if frame[1] and frame[1] != emotion:
                au_data.append([float(aus[str(x)]) for x in aus_list])
                # target_data.append('Neutral/Sleeping')
                target_data.append(0)
        au_test = au_data
        target_test = target_data

        return au_train, au_test, target_train, target_test


def vis(short_patient, thresh_file=None):
    if not thresh_file:
        thresh_file = short_patient + '_threshes.txt'
    thresh_dict = json.load(open(thresh_file)) if os.path.exists(thresh_file) else {}
    if not thresh_dict:
        out_q = multiprocessing.Manager().Queue()
        threshes = np.linspace(0, 1.5, 100)
        bar = ProgressBar(max_value=len(threshes))
        f = functools.partial(thresh_calc, out_q, short_patient)
        for i, _ in enumerate(Pool().imap(f, threshes, chunksize=10)):
            while not out_q.empty():
                thresh_dict.update(out_q.get())
            bar.update(i)
        json.dump(thresh_dict, open(thresh_file, 'w'))

    for emotion in ['Happy', 'Angry', 'Sad', 'Disgust']:
        # precision-recall
        out_vals = {}
        for thresh in sorted(thresh_dict.keys()):
            if emotion in thresh_dict[thresh]:
                curr_emote_dict = thresh_dict[thresh][emotion]
                false_pos = curr_emote_dict['false_pos']
                true_pos = curr_emote_dict['true_pos']
                false_neg = curr_emote_dict['false_neg']
                total_pos = true_pos + false_neg
                if total_pos and (false_pos + true_pos):
                    precision = true_pos / (false_pos + true_pos)
                    recall = true_pos / total_pos
                    out_vals[thresh] = [precision, recall]
        x_vals = [out_vals[thresh][0] for thresh in sorted(out_vals.keys())]
        y_vals = [out_vals[thresh][1] for thresh in sorted(out_vals.keys())]
        z_vals = [float(x) for x in sorted(out_vals.keys())]

        if x_vals and y_vals and len(x_vals) == len(y_vals):
            fig = plt.figure()
            ax = fig.gca()
            ax.plot(x_vals, y_vals, label='Substring')

            OpenDir = sys.argv[sys.argv.index('-d') + 1]
            os.chdir(OpenDir)
            au_train, au_test, target_train, target_test = make_emotion_data(emotion, short_patient)

            classifier_dict = {
                KNeighborsClassifier(): 'KNeighbors',
                SVC(kernel='linear', probability=True): 'SVCLinear',
                SVC(probability=True): 'SVC',
                # GaussianProcessClassifier(),
                # DecisionTreeClassifier(),
                RandomForestClassifier(): 'RandomForest',
                ExtraTreesClassifier(): 'ExtraTrees',
                MLPClassifier(): 'MLP',
                AdaBoostClassifier(): 'AdaBoost',
                GaussianNB(): 'GaussianNB',
                QuadraticDiscriminantAnalysis(): 'QuadraticDiscriminantAnalysis',
                BernoulliNB(): 'BernoulliNB'
            }

            for classifier in classifier_dict.keys():
                expected, decision_function = use_classifier(classifier, au_train, au_test, target_train, target_test)
                precision, recall, thresholds = precision_recall_curve(expected, decision_function)
                ax.plot(precision, recall, label=classifier_dict[classifier])

            ax.set_title(
                'Performance of Different Methods for' + "\' " + emotion + " \'" + 'Recognition from Continuous AUs')
            ax.set_xlabel('Precision')
            ax.set_ylabel('Recall')
            ax.legend()
            fig.tight_layout()
            plt.savefig(short_patient + '_{0}_pr_with_ML_and_pose'.format(emotion))
            plt.close()

            # plt.show()


def make_scores_file(scores_file, patient_dirs):
    all_dict = multiprocessing.Manager().dict()
    Pool().map(functools.partial(add_patient_dir_scores, all_dict), patient_dirs)
    dump_dict = dict()
    dump_dict.update(all_dict)
    json.dump(dump_dict, open(scores_file, 'w'))


def add_patient_dir_scores(all_dict, patient_dir):
    if 'all_dict.txt' in os.listdir(patient_dir):
        emotion_dict = AUScorer.make_frame_emotions(
            AUScorer.convert_dict_to_int(json.load(open(os.path.join(patient_dir, 'all_dict.txt')))))
    else:
        emotion_dict = AUScorer.AUScorer(patient_dir).emotions
    all_dict[patient_dir.replace('_cropped', '')] = emotion_dict


if __name__ == '__main__':
    OpenDir = sys.argv[sys.argv.index('-d') + 1]
    os.chdir(OpenDir)
    au_emote_dict = json.load(open('au_emotes.txt'))
    patient_dirs = glob.glob('*cropped')  # Directories have been previously cropped by CropAndOpenFace
    scores = defaultdict()
    scores_file = 'predic_substring_dict.txt'
    if not os.path.exists(scores_file):
        make_scores_file(scores_file, patient_dirs)
    scores = json.load(open(scores_file))
    csv_file = json.load(open('scores.txt'))
    csv_file = clean_csv(csv_file)
    short_patient_list = set()
    for direc in csv_file:
        short_direc = direc[:direc.index('_')]
        short_patient_list.add(short_direc)

    vis('all', 'threshes.txt')

    bar = ProgressBar(max_value=len(short_patient_list))
    for i, short_patient in enumerate(short_patient_list, 1):
        vis(short_patient)
        bar.update(i)
