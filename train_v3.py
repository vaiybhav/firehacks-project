#!/usr/bin/env python3
"""
Retrain the pose classifier from the Yoga-82 dataset with orientation features.

Differences from the shipped training path (pose_classifier.prepare_training_data):

  1. NO 100-image-per-pose cap.  The original did `image_files[:100]  # for speed`
     and read only the FIRST split it found, using 1955 of 5251 available images.
     This merges train+valid+test and uses everything.
  2. 19 features instead of 9 - adds body orientation (see features_v2.py), which
     targets the measured top confusion (Chair -> Cat-Cow, 23x: standing vs on
     all fours, indistinguishable from internal joint angles alone).
  3. IMAGE-mode detection. Live capture uses MediaPipe VIDEO mode for speed, but
     that tracks between frames - catastrophic on a folder of unrelated stills.
  4. Held-out evaluation, which the original had none of.

Extracted features are cached to features_v3.npz so retraining is instant.

Usage:
    python train_v3.py                 # extract (slow, once) + train
    python train_v3.py --reuse-cache   # skip extraction
"""
import argparse
import os
import pickle
import time

import cv2
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

import config
from features_v2 import ALL_FEATURE_NAMES, get_angle_features_v2
from pose_detector import PoseDetector

SPLITS = ["train", "valid", "test"]
CACHE = "features_v3.npz"
OUT = os.path.join("models", "pose_classifier_v3.pkl")

# Matches train_v2.py: n_jobs=1 because predict() runs on a single row inside a
# 33 ms frame budget, where n_jobs=-1 costs 28.8 ms of thread dispatch vs 2.7 ms.
N_ESTIMATORS = 40
MIN_SAMPLES_LEAF = 2
RANDOM_STATE = 0


def extract():
    root = config.DATASET_ROOT
    if not os.path.isdir(root):
        raise SystemExit(f"DATASET_ROOT {root!r} not found (cwd={os.getcwd()})")

    # video_mode=False: unrelated still images, no inter-frame tracking.
    detector = PoseDetector(video_mode=False)

    X, y = [], []
    stats = []
    t0 = time.time()
    for idx, pose in enumerate(config.TOP_POSES):
        seen = kept = 0
        for split in SPLITS:
            d = os.path.join(root, split, pose)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                seen += 1
                try:
                    img = cv2.imread(os.path.join(d, fn))
                    if img is None:
                        continue
                    kp = detector.detect_pose(img)
                    if kp is None:
                        continue
                    if float(np.mean(kp[:, 2])) < config.POSE_CONFIDENCE_THRESHOLD:
                        continue
                    feats = get_angle_features_v2(kp)
                    if not np.all(np.isfinite(feats)) or not np.any(feats > 0):
                        continue
                    X.append(feats)
                    y.append(idx)
                    kept += 1
                except Exception:
                    continue
        stats.append((pose, seen, kept))
        print(f"  [{idx + 1:2d}/24] {pose[:44]:44s} {kept:4d}/{seen:4d} usable", flush=True)

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y)
    print(f"\nExtraction took {time.time() - t0:.0f}s -> {X.shape[0]} samples, {X.shape[1]} features")
    tot_seen = sum(s for _, s, _ in stats)
    print(f"Detection yield: {X.shape[0]}/{tot_seen} = {X.shape[0] / max(tot_seen,1) * 100:.1f}%")
    np.savez_compressed(CACHE, X=X, y=y)
    return X, y


def report(name, X, y, cv):
    clf = ExtraTreesClassifier(n_estimators=N_ESTIMATORS, min_samples_leaf=MIN_SAMPLES_LEAF,
                               random_state=RANDOM_STATE, n_jobs=1)
    s = cross_val_score(clf, X, y, cv=cv, n_jobs=-1)
    print(f"  {name:34s} {s.mean() * 100:5.1f}%  (+/- {s.std() * 100:.1f})")
    return s.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-cache", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    if args.reuse_cache and os.path.exists(CACHE):
        d = np.load(CACHE)
        X, y = d["X"], d["y"]
        print(f"Loaded cache {CACHE}: {X.shape[0]} samples, {X.shape[1]} features")
    else:
        X, y = extract()

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    print(f"\n{'=' * 60}\n  ABLATION (same model, same samples)\n{'=' * 60}")
    n_base = 9
    base_only = report("9 angle features only", Xs[:, :n_base], y, cv)
    full = report("19 features (+ orientation)", Xs, y, cv)
    print(f"  {'orientation features add':34s} {(full - base_only) * 100:+5.1f} points")

    print("\nFitting final model on all samples ...")
    clf = ExtraTreesClassifier(n_estimators=N_ESTIMATORS, min_samples_leaf=MIN_SAMPLES_LEAF,
                               random_state=RANDOM_STATE, n_jobs=1)
    clf.fit(Xs, y)

    label_to_pose = {i: p for i, p in enumerate(config.TOP_POSES)}
    bundle = {
        "classifier": clf,
        "scaler": scaler,
        "pose_labels": list(config.TOP_POSES),
        "label_to_pose": label_to_pose,
        "pose_to_label": {p: i for i, p in label_to_pose.items()},
        "n_neighbors": 5,          # unused; kept for load() format compatibility
        "feature_version": 2,      # marks that this needs get_angle_features_v2
        "feature_names": ALL_FEATURE_NAMES,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump(bundle, f)
    print(f"Wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB)")
    print("\nNOTE: this model expects 19 features - it needs get_angle_features_v2,")
    print("      so it is NOT drop-in for the stock PoseClassifier.predict().")


if __name__ == "__main__":
    main()
