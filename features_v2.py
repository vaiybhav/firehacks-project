"""
Extended pose features: the original 9 joint angles plus body-orientation
features they structurally cannot express.

WHY THIS EXISTS
---------------
utils.angles.get_angle_features returns 9 INTERNAL joint angles (elbows, knees,
hips, shoulder, spine). Internal angles are orientation-blind: they describe how
bent a limb is, never which way the body is pointing. Measured consequence on
the shipped model - the single largest confusion is

    23x  Chair Pose  ->  Cat-Cow Pose

Chair is standing upright, Cat-Cow is on all fours. Both have bent knees, bent
hips and extended arms, so in the 9-angle space they are near-identical. Same
story for Staff vs Boat (torso lean) and Dolphin Plank vs Chaturanga.

The features below add the missing axis: torso inclination, shoulder/hip tilt,
body aspect ratio and vertical ordering of head/hips/ankles.

DESIGN NOTES
------------
* The original 9 features are passed through UNCHANGED and first, so a v2 model
  is a strict superset of what the v1 model could learn.
* Missing joints keep the 0.0 sentinel convention. That looks like a bug but is
  load-bearing: imputing those values costs 1.1-1.7 accuracy points because
  MediaPipe's failure to see a joint is itself informative (occlusion correlates
  with pose). Measured, not assumed - see train_v2.py.
* Everything added is translation- and scale-invariant (normalised by torso
  length or bounding box), but deliberately NOT rotation-invariant - rotation is
  exactly the signal being added.
* Image coordinates: y grows DOWNWARD. "Above" therefore means smaller y.
"""
import numpy as np

from utils.angles import get_angle_features

# Indices into the 17-keypoint layout produced by PoseDetector.
NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_ELBOW, R_ELBOW = 7, 8
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16

VIS = 0.2          # same visibility threshold the rest of the codebase uses
MISSING = 0.0      # sentinel used by the legacy 9 angles - kept for compatibility

# The new features need a DIFFERENT sentinel. 0.0 is a perfectly ordinary value
# for several of them - an upright torso gives torso_incline == 0.0, level
# shoulders give shoulder_tilt == 0.0 - so reusing 0.0 would make "standing
# straight" indistinguishable from "could not measure", destroying the exact
# signal these features exist to provide. -999 is out of range for angles
# (0-180), ratios (>= 0) and the signed normalised offsets (~ -3..3).
MISSING_V2 = -999.0

FEATURE_NAMES_V2 = [
    "torso_incline",     # torso axis vs vertical: ~0 standing, ~90 horizontal
    "shoulder_tilt",     # shoulder line vs horizontal
    "hip_tilt",          # hip line vs horizontal
    "aspect_ratio",      # bbox height / width of visible joints
    "head_above_hips",   # signed, normalised by torso length
    "ankles_above_hips",
    "knee_symmetry",     # |left - right| joint angle
    "elbow_symmetry",
    "leg_torso_ratio",   # foreshortening / depth cue
    "arm_torso_ratio",
]

BASE_FEATURE_NAMES = [
    "left_elbow", "right_elbow", "left_knee", "right_knee",
    "left_hip", "right_hip", "shoulder_left", "spine_left", "spine_right",
]

ALL_FEATURE_NAMES = BASE_FEATURE_NAMES + FEATURE_NAMES_V2


def _visible(kp, *idx):
    return all(kp[i, 2] > VIS for i in idx)


def _mid(kp, a, b):
    return (kp[a, :2] + kp[b, :2]) / 2.0


def _angle_to_axis(vec, axis):
    """Unsigned angle in degrees between vec and axis, 0-180."""
    n = np.linalg.norm(vec)
    if n < 1e-6:
        return MISSING_V2
    cos = float(np.clip(np.dot(vec / n, axis), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos)))


def get_orientation_features(keypoints: np.ndarray) -> np.ndarray:
    """The 10 orientation features. Missing values use MISSING_V2."""
    kp = keypoints
    f = {name: MISSING_V2 for name in FEATURE_NAMES_V2}

    have_sh = _visible(kp, L_SHOULDER, R_SHOULDER)
    have_hip = _visible(kp, L_HIP, R_HIP)

    torso_len = 0.0
    if have_sh and have_hip:
        mid_sh, mid_hip = _mid(kp, L_SHOULDER, R_SHOULDER), _mid(kp, L_HIP, R_HIP)
        torso = mid_sh - mid_hip
        torso_len = float(np.linalg.norm(torso))
        # Vertical axis pointing "up" the image is (0, -1).
        f["torso_incline"] = _angle_to_axis(torso, np.array([0.0, -1.0]))

    if have_sh:
        f["shoulder_tilt"] = _angle_to_axis(
            kp[R_SHOULDER, :2] - kp[L_SHOULDER, :2], np.array([1.0, 0.0]))
    if have_hip:
        f["hip_tilt"] = _angle_to_axis(
            kp[R_HIP, :2] - kp[L_HIP, :2], np.array([1.0, 0.0]))

    vis = kp[kp[:, 2] > VIS][:, :2]
    if len(vis) >= 3:
        w = float(vis[:, 0].max() - vis[:, 0].min())
        h = float(vis[:, 1].max() - vis[:, 1].min())
        if w > 1e-6:
            f["aspect_ratio"] = h / w

    if torso_len > 1e-6:
        mid_hip = _mid(kp, L_HIP, R_HIP)
        if kp[NOSE, 2] > VIS:
            # positive => head higher up the image than the hips
            f["head_above_hips"] = float((mid_hip[1] - kp[NOSE, 1]) / torso_len)
        if _visible(kp, L_ANKLE, R_ANKLE):
            mid_ank = _mid(kp, L_ANKLE, R_ANKLE)
            f["ankles_above_hips"] = float((mid_hip[1] - mid_ank[1]) / torso_len)
        if _visible(kp, L_HIP, L_KNEE, L_ANKLE):
            leg = (np.linalg.norm(kp[L_KNEE, :2] - kp[L_HIP, :2])
                   + np.linalg.norm(kp[L_ANKLE, :2] - kp[L_KNEE, :2]))
            f["leg_torso_ratio"] = float(leg / torso_len)
        if _visible(kp, L_SHOULDER, L_ELBOW, L_WRIST):
            arm = (np.linalg.norm(kp[L_ELBOW, :2] - kp[L_SHOULDER, :2])
                   + np.linalg.norm(kp[L_WRIST, :2] - kp[L_ELBOW, :2]))
            f["arm_torso_ratio"] = float(arm / torso_len)

    # Symmetry is computed from the base angles so it stays consistent with them.
    base = get_angle_features(kp)
    l_elbow, r_elbow, l_knee, r_knee = base[0], base[1], base[2], base[3]
    if l_knee != MISSING and r_knee != MISSING:
        f["knee_symmetry"] = float(abs(l_knee - r_knee))
    if l_elbow != MISSING and r_elbow != MISSING:
        f["elbow_symmetry"] = float(abs(l_elbow - r_elbow))

    return np.array([f[n] for n in FEATURE_NAMES_V2], dtype=np.float32)


def get_angle_features_v2(keypoints: np.ndarray) -> np.ndarray:
    """Original 9 angle features followed by the 10 orientation features."""
    return np.concatenate([
        get_angle_features(keypoints).astype(np.float32),
        get_orientation_features(keypoints),
    ])
