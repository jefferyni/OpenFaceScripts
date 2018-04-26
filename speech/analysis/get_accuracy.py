from glob import glob
import sys
import os

truth_dir = sys.argv[sys.argv.index('-t') + 1]
pred_dir = sys.argv[sys.argv.index('-p') + 1]

truths = glob(os.path.join(truth_dir, '*.txt'))
preds = glob(os.path.join(pred_dir, '*.txt'))

truth_dict = dict()
for truth in truths:
    filename = os.path.basename(truth)
    truth_dict[filename] = set()

    truth_lines = open(truth).readlines()
    for line in truth_lines:
        split = line.split()
        f1 = int(split[0])
        f2 = int(split[1])
        for i in range(f1, f2 + 1):
            truth_dict[filename].add(i)

correct = 0
total = 0
for pred in preds:
    filename = os.path.basename(pred)
    
    if filename in truth_dict:
        pred_lines = open(pred).readlines()
        for line in pred_lines:
            split = line.split()
            f1 = int(split[0])
            f2 = int(split[1])
            for i in range(f1, f2 + 1):
                if i in truth_dict[filename]:
                    correct += 1
                total += 1

print(correct / total)
print(correct, total)


