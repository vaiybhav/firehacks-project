#!/usr/bin/env python3
"""
Evaluate a saved pose classifier.

The training pipeline has no evaluation at all - PoseClassifier.train() fits on
100% of the data and reports nothing (train_test_split is imported and never
used), which is how a 67.8% model shipped without anyone knowing the number.
This script exists so any future change to features, model or data can be
measured instead of guessed at.

Evaluation uses the (scaled) training matrix embedded in the shipped KNN pickle,
so it runs without the Yoga-82 dataset. Numbers are therefore accuracy on
DATASET images under cross-validation - real webcam accuracy will differ, since
the dataset is scraped web photos rather than someone in a room facing a laptop.

Usage:
    python evaluate_model.py                                   # shipped model
    python evaluate_model.py models/pose_classifier_v2.pkl     # a specific model
    python evaluate_model.py --compare models/pose_classifier.pkl models/pose_classifier_v2.pkl
"""
import argparse
import os
import pickle
import sys

import numpy as np
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict

DEFAULT_MODEL = os.path.join("models", "pose_classifier.pkl")
DATA_SOURCE = os.path.join("models", "pose_classifier.pkl")
N_SPLITS = 5
RANDOM_STATE = 0


def load_bundle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


V3_CACHE = "features_v3.npz"


def load_eval_data(path=DATA_SOURCE):
    """Recover the scaled training matrix + labels embedded in the KNN pickle."""
    bundle = load_bundle(path)
    knn = bundle["classifier"]
    if not hasattr(knn, "_fit_X"):
        raise SystemExit(
            f"{path} has no embedded training data (classifier is "
            f"{type(knn).__name__}). Point --data at the original KNN pickle."
        )
    return np.asarray(knn._fit_X), np.asarray(knn._y), bundle["label_to_pose"]


def load_v2_feature_data(bundle):
    """Dataset-extracted 19-feature matrix, rescaled with the model's scaler."""
    if not os.path.exists(V3_CACHE):
        raise SystemExit(
            f"{V3_CACHE} not found - it holds the 19-feature data this model was "
            "trained on. Regenerate it with: python train_v3.py"
        )
    d = np.load(V3_CACHE)
    X = bundle["scaler"].transform(d["X"])
    return X, d["y"], bundle["label_to_pose"]


def data_for(model_path):
    """Pick the evaluation matrix matching the model's feature version."""
    bundle = load_bundle(model_path)
    if bundle.get("feature_version", 1) >= 2:
        return load_v2_feature_data(bundle)
    return load_eval_data()


def short_name(name):
    return (name.replace("_Pose", "").replace("_or_", " / ")
                .replace("_", " ").strip())[:36]


def evaluate(model_path, X, y, labels, show_confusions=True):
    bundle = load_bundle(model_path)
    clf = bundle["classifier"]
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    # clone() gives an unfitted copy with identical hyperparameters, so we
    # measure the configuration rather than a model that has already seen
    # every evaluation row.
    pred = cross_val_predict(clone(clf), X, y, cv=cv, n_jobs=-1)
    acc = (pred == y).mean()

    print(f"\n{'=' * 66}")
    print(f"  {model_path}")
    print(f"  estimator: {type(clf).__name__}")
    print(f"{'=' * 66}")
    print(f"  samples {X.shape[0]}   features {X.shape[1]}   classes {len(np.unique(y))}")
    print(f"  {N_SPLITS}-fold CV accuracy : {acc * 100:.1f}%")
    print(f"  random baseline    : {100 / len(np.unique(y)):.1f}%")

    print("\n  per-pose recall (worst first):")
    rows = sorted(((pred[y == c] == c).mean(), (y == c).sum(), c) for c in np.unique(y))
    for r, n, c in rows:
        bar = "#" * int(r * 30)
        print(f"    {r * 100:5.1f}%  n={n:3d}  {bar:<30} {short_name(labels[c])}")

    if show_confusions:
        print("\n  top confusions (true -> predicted):")
        cm = confusion_matrix(y, pred)
        np.fill_diagonal(cm, 0)
        flat = [(cm[i, j], i, j) for i in range(len(cm)) for j in range(len(cm)) if cm[i, j]]
        for n, i, j in sorted(flat, reverse=True)[:8]:
            print(f"    {n:3d}x  {short_name(labels[i]):<36} -> {short_name(labels[j])}")

    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default=DEFAULT_MODEL)
    ap.add_argument("--compare", nargs="+", metavar="MODEL",
                    help="evaluate several models and summarise")
    ap.add_argument("--data", default=DATA_SOURCE,
                    help="pickle to harvest evaluation data from")
    args = ap.parse_args()

    targets = args.compare if args.compare else [args.model]

    missing = [p for p in targets if not os.path.exists(p)]
    if missing:
        raise SystemExit("Not found: " + ", ".join(missing))

    # Each model is scored on the feature set it was actually trained on, so a
    # 9-feature and a 19-feature model can be compared in one run.
    results = []
    for p in targets:
        X, y, labels = data_for(p)
        results.append((p, evaluate(p, X, y, labels, show_confusions=not args.compare)))

    if len(results) > 1:
        print(f"\n{'=' * 66}\n  SUMMARY\n{'=' * 66}")
        best = max(r[1] for r in results)
        for p, a in results:
            print(f"    {a * 100:5.1f}%  {p}{'   <- best' if a == best else ''}")


if __name__ == "__main__":
    sys.exit(main())
