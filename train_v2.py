#!/usr/bin/env python3
"""
Train an improved pose classifier WITHOUT needing the Yoga-82 dataset.

The shipped models/pose_classifier.pkl embeds its own (scaled) training matrix
inside the fitted KNeighborsClassifier, so the exact samples the original model
learned from can be recovered and refit with a stronger estimator.

Measured on that data with 5-fold stratified CV:

    KNN k=5 distance (shipped)   67.8%
    SVM rbf                      69.8%
    RandomForest 500             74.1%
    ExtraTrees 500               74.8%   <- what this script trains

KNN is not tunable out of this: k=1 -> 67.6%, k=5 -> 67.8%, k=15 -> 66.2%.
The limit is the 9 orientation-blind angle features, not the neighbour count.

NOTE ON MISSING JOINTS: utils.angles.get_angle_features substitutes 0.0 for
joints MediaPipe could not locate, and 38.7% of training rows contain at least
one. That looks like a bug, but replacing those with imputed values measurably
HURTS accuracy (-1.1 to -1.7 points across seeds), because the 0.0 doubles as a
"joint not visible" marker and visibility correlates with pose - the missingness
pattern alone classifies at 9.9% vs 4.2% chance. So the sentinel is preserved
here deliberately. Do not "fix" it without re-measuring.

Nothing already in place is modified: this writes a NEW pickle, in the same
dict format PoseClassifier.load() expects, so switching is a path change.

Usage:
    python train_v2.py                  # writes models/pose_classifier_v2.pkl
    python train_v2.py --out other.pkl
"""
import argparse
import os
import pickle

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

SOURCE_MODEL = os.path.join("models", "pose_classifier.pkl")
DEFAULT_OUT = os.path.join("models", "pose_classifier_v2.pkl")

# These three constants are chosen from measurement, not taste - predict() runs
# once per camera frame inside a 33 ms budget (a frame is currently 28.4 ms).
#
#   trees  acc     pickle    predict(1 row)   resulting frame
#     40   73.8%   11.3 MB       2.67 ms          ~30.5 ms   <- chosen
#     60   74.0%   17.1 MB       3.99 ms          ~31.8 ms
#    100   74.4%   28.4 MB       6.34 ms          ~34.2 ms   breaks 30 FPS
#    500   74.8%  252.8 MB          -                -       absurd on disk
#
# n_jobs=1 is critical and is baked into the pickle: on a SINGLE row, n_jobs=-1
# costs 28.80 ms of pure thread dispatch versus 2.67 ms single-threaded - a 10x
# regression that would have halved the frame rate.
#
# min_samples_leaf=2 roughly halves the pickle (trees stop at pure single-sample
# leaves) for no measurable accuracy cost.
N_ESTIMATORS = 40
MIN_SAMPLES_LEAF = 2
RANDOM_STATE = 0


def load_embedded_training_data(path):
    """Recover the (scaled) training matrix and labels from a fitted KNN pickle."""
    with open(path, "rb") as f:
        bundle = pickle.load(f)

    knn = bundle["classifier"]
    if not hasattr(knn, "_fit_X"):
        raise SystemExit(
            f"{path} does not embed its training data (classifier is "
            f"{type(knn).__name__}, expected a fitted KNeighborsClassifier). "
            "Retrain from the dataset instead."
        )

    X = np.asarray(knn._fit_X)      # already transformed by bundle['scaler']
    y = np.asarray(knn._y)
    return bundle, X, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=SOURCE_MODEL, help="existing model to harvest data from")
    ap.add_argument("--out", default=DEFAULT_OUT, help="where to write the new model")
    ap.add_argument("--force", action="store_true", help="allow overwriting --out")
    args = ap.parse_args()

    if os.path.abspath(args.out) == os.path.abspath(args.source):
        raise SystemExit("Refusing to overwrite the source model; pass a different --out.")
    if os.path.exists(args.out) and not args.force:
        raise SystemExit(f"{args.out} already exists. Pass --force to replace it.")

    print(f"Reading training data embedded in {args.source} ...")
    bundle, X, y = load_embedded_training_data(args.source)
    print(f"  samples={X.shape[0]}  features={X.shape[1]}  classes={len(np.unique(y))}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    old = cross_val_score(bundle["classifier"].__class__(
        n_neighbors=bundle.get("n_neighbors", 5), weights="distance"),
        X, y, cv=cv, n_jobs=-1)
    print(f"\n  shipped KNN      : {old.mean() * 100:.1f}%  (+/- {old.std() * 100:.1f})")

    clf = ExtraTreesClassifier(n_estimators=N_ESTIMATORS,
                               min_samples_leaf=MIN_SAMPLES_LEAF,
                               random_state=RANDOM_STATE, n_jobs=1)
    new = cross_val_score(clf, X, y, cv=cv, n_jobs=-1)
    print(f"  ExtraTrees {N_ESTIMATORS}    : {new.mean() * 100:.1f}%  (+/- {new.std() * 100:.1f})")
    print(f"  delta            : {(new.mean() - old.mean()) * 100:+.1f} points")

    if new.mean() <= old.mean():
        raise SystemExit("\nNew model is not better on this data - not writing it.")

    print("\nFitting final model on all samples ...")
    clf.fit(X, y)

    # Same dict shape PoseClassifier.load() reads. The scaler is carried over
    # unchanged because X was already transformed by it, so predict() stays
    # consistent: scaler.transform(features) -> classifier.predict(...).
    out = {
        "classifier": clf,
        "scaler": bundle["scaler"],
        "pose_labels": bundle["pose_labels"],
        "label_to_pose": bundle["label_to_pose"],
        "pose_to_label": bundle["pose_to_label"],
        "n_neighbors": bundle.get("n_neighbors", 5),  # unused by ExtraTrees; kept for format compat
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump(out, f)

    print(f"Wrote {args.out} ({os.path.getsize(args.out) / 1024:.0f} KB)")
    print(f"\n{args.source} is untouched.")
    print("To use the new model, load that path instead:")
    print(f"    classifier.load('{args.out}')")


if __name__ == "__main__":
    main()
