# Horizons — Handoff

Real-time yoga coach: webcam → MediaPipe pose detection → pose classification →
form correction → live feedback in a React UI.

**Project root:** `~/Programming/Quackathon/Horizons`
*(moved from `~/Downloads/Horizons` — anything referencing the old path is stale)*

---

## Architecture

Three local services. Nothing is cloud-hosted except Deepgram TTS.

```
Browser (React/Vite, :5003)
   │  HTTP  ──────────────►  yoga_api_server.py (:5002)
   │  WebSocket ◄─────────►      └─ guided_session.py
   │                                 ├─ pose_detector.py    (MediaPipe)
   │                                 ├─ pose_classifier.py  (ExtraTrees)
   │                                 ├─ form_corrector.py
   │                                 └─ nlg_engine.py
   └─ audio ──────────────►  tts_test/backend.py (:5001 → Deepgram)
```

| Port | Service | Entry point |
|---|---|---|
| 5003 | React web app | `one-breath-app/` (Vite) |
| 5002 | Yoga API + WebSocket | `yoga_api_server.py` |
| 5001 | TTS backend | `tts_test/backend.py` |

`GET /health`, `GET /list-cameras`, `POST /start-session`, `POST /stop-session`.
Socket.IO emits `video_frame`, `session_update`, `debug_update`, `pose_changed`,
`session_complete`; listens for `next_pose`, `pause_session`, `resume_session`,
`repeat_instruction`, `end_session`.

---

## Running it

```bash
cd ~/Programming/Quackathon/Horizons

# TTS (:5001)
cd tts_test && nohup ../.venv/bin/python -u backend.py > /tmp/yoga_tts_backend.log 2>&1 &

# Yoga API (:5002)
cd .. && nohup .venv/bin/python -u yoga_api_server.py > /tmp/yoga_api_server.log 2>&1 &

# Web app (:5003)
cd one-breath-app && nohup npm run dev > /tmp/horizons_app.log 2>&1 &
```

Then open **http://localhost:5003**. Starting a session opens the webcam
(macOS will prompt for permission).

Kill everything:

```bash
lsof -ti:5001,5002,5003 | xargs kill -9
```

> **Do not** use the bundled `start_all_servers.sh` as-is — it runs
> `lsof -ti:5000,... | xargs kill -9`, and **port 5000 on macOS is Control Center
> (AirPlay Receiver)**, not this project. It also references the old `Downloads` path.

Optional env flags:

- `YOGA_PROFILE=1` — per-stage frame timings every 60 frames
- `YOGA_PREDICT_DEBUG=1` — classifier logging (off by default; it used to print 4 lines *per frame*)

---

## Current state

Everything below is measured, not estimated.

| | before | now |
|---|---|---|
| App loads at all | ❌ JSX syntax error | ✅ |
| Frame rate | 11.7 FPS | **28 FPS** (camera-capped) |
| Frame time | ~85 ms | **32.7 ms** |
| Classifier accuracy (5-fold CV) | 67.8% | **86.4%** |
| Training samples | 1,955 | **4,661** |
| Features | 9 | **19** |
| Stream bandwidth | 9.6 MB/s | 3.4 MB/s |

### Models

| file | acc | notes |
|---|---|---|
| `models/pose_classifier.pkl` | 67.8% | original KNN, 262 KB — **keep as fallback** |
| `models/pose_classifier_v2.pkl` | 73.8% | ExtraTrees, 9 features, 11 MB |
| `models/pose_classifier_v3.pkl` | **86.4%** | ExtraTrees, 19 features, 21 MB — **in use** |

`guided_session.py` picks v3 → v2 → v1, whichever exists. `PoseClassifier` reads
`feature_version` from the pickle and selects the matching feature extractor, so
old models still behave exactly as before.

---

## Traps — read before changing anything

These all cost real debugging time. Each is enforced by a comment in the code.

**1. The `0.0` missing-joint sentinel is load-bearing. Do not "fix" it.**
`utils/angles.py` substitutes `0.0` when MediaPipe can't see a joint; 38.7% of
training rows contain one. It looks like a bug. Imputing those values makes
accuracy *worse* by 1.1–1.7 points across seeds, because MediaPipe failing to see
a joint is itself informative — occlusion correlates with pose. The missingness
pattern **alone** classifies at 9.9% vs 4.2% chance.

**2. `n_jobs=1` on the classifier is mandatory.**
`predict()` runs on a single row inside a 33 ms frame budget. With `n_jobs=-1`
that single-row call takes **28.8 ms** of pure thread dispatch vs **2.67 ms**
single-threaded. It's baked into the saved pickles.

**3. `PoseDetector(video_mode=...)` must match the workload.**
`True` (default) = MediaPipe VIDEO mode, tracks between frames, ~14 ms cheaper —
correct for live camera. `False` = IMAGE mode — **required** for batch-processing
unrelated still images (training, template generation), where tracking would leak
one image's pose into the next.

**4. `curl http://localhost:5003/` returning 200 proves nothing.**
Vite serves `index.html` statically and only compiles modules when a browser
requests them. A file with a syntax error still gives you a 200 on `/`. To
actually verify the frontend:

```bash
curl -o /dev/null -w "%{http_code}\n" \
  http://localhost:5003/src/components/YogaSessionPage.tsx
```

**5. The frame budget has no headroom left.** 32.7 ms of a 33 ms budget.
MediaPipe is 23.4 ms of it. Anything added to the loop will drop frames — profile
with `YOGA_PROFILE=1` before and after.

**6. Feature changes require a retrained model.** The 19-feature extractor uses
`-999.0` as its sentinel, *not* `0.0`, because `0.0` is a legitimate value for
several of them (an upright torso genuinely has `torso_incline == 0.0`).

---

## Reproducing / evaluating the model

```bash
# Retrain from cached features (fast, ~20s)
.venv/bin/python train_v3.py --reuse-cache

# Full re-extraction from the dataset (~200s for 5,251 images)
.venv/bin/python train_v3.py

# Compare models: CV accuracy, per-pose recall, top confusions
.venv/bin/python evaluate_model.py --compare \
  models/pose_classifier.pkl models/pose_classifier_v3.pkl
```

`features_v3.npz` caches the extracted 19-feature matrix so retraining doesn't
need the images.

### Why v3 is better — the ablation

```
67.8%   original: KNN, 1,955 samples, 9 features
78.1%   full data, 9 features        (uncapping data: +10.3)
86.4%   full data, 19 features       (orientation:     +8.4)
```

The original capped training at `image_files[:100]` per pose *and* read only one
split, using 1,955 of 5,251 available images.

The orientation features exist because the top confusion was **Chair → Cat-Cow,
23×**. Chair is standing upright; Cat-Cow is on all fours. All 9 original features
were *internal joint angles*, which are orientation-blind — bent knees and bent
hips look identical either way. Adding torso inclination, shoulder/hip tilt, body
aspect ratio and head/ankle vertical ordering fixed it: **Chair went 26.7% → 88.9%**
and that confusion pair is gone entirely.

---

## Dataset

Yoga-82 at `archive 2/` (2.5 GB, `train/valid/test`, 82 classes; this project uses 24).

`config.DATASET_ROOT` previously pointed at `"archive (1) 2"`, which never
existed. Fixing that one line also **revived the pose reference images** — a
feature that was fully built end-to-end (`yoga_program.get_pose_image_path` →
base64 → `YogaSessionPage.tsx:770` reference card) and silently dead because the
path never resolved.

Detection yield: 4,661 / 5,251 = 88.8%.

---

## Behaviour notes

**Timer pauses, never resets.** Breaking form banks the elapsed time via
`_pause_hold_timer()`; re-entering resumes from there. Only `next_pose()` zeroes
it. There were four separate reset sites, plus a latent double-count (resume set
`hold_start_time = now - accumulated` while elapsed was computed as
`accumulated + (now - hold_start_time)`).

**The timer only starts on a confirmed, stable pose.** An `elif can_start_timer:`
branch used to start the clock on looser thresholds *and* skipped the stability
check entirely, so one weak frame started timing a pose you weren't in. Removed;
those frames now fall through to the pause path. `can_start_timer` is still used
elsewhere for voice feedback.

**Feedback is gated on `in_pose` and does not flicker.** `overall_status` is
computed from angles every frame regardless of whether anyone is posing, so an
empty room could score `correct` — the UI was showing "Perfect form!" at 0s hold
and 26% accuracy. Separately, `generate_summary_feedback` called `random.choice`
on every emission (~9.4/sec), so the text changed **6.4 times per second**. Now
the wording is held until the status changes (3s minimum) and all commentary is
suppressed unless `in_pose`.

---

## Open items

1. **:5002 is currently not running.** Only TTS and Vite are up. Restart it with
   the command above.
2. **Feedback bar is blank when not in the pose.** Deliberate — honest beats
   chatty — but a stable "Get into Tree Pose to begin" prompt would be friendlier.
   Design call, not a bug.
3. **86.4% is on *dataset* images**, which are scraped web photos. Real webcam
   accuracy is unmeasured and will differ. Measuring it needs labelled footage of
   an actual user.
4. **`ANGLE_TOLERANCE` in `config.py` was recently retuned** (dangerous 45°,
   improvable 25°, correct 12°). These are read at runtime by
   `form_corrector._classify_angle`, so changes apply on restart with **no
   template regeneration needed** — templates carry their own min/max.
5. **Deepgram configuration:** `tts_test/backend.py` reads `DEEPGRAM_API_KEY`
   from the environment and returns HTTP 503 for speech requests if it is absent.
6. **`pose_classifier.pkl` was pickled under scikit-learn 1.7.2**; the venv runs
   1.8.0, which warns on load. v3 was written by the current version so it's fine,
   but the v1 fallback may eventually stop loading.
7. **Frontend re-renders on every frame.** `YogaSessionPage.tsx` calls
   `setVideoFrame()` per frame, re-rendering the whole component ~30×/sec. Moving
   the feed to a `<canvas>` or isolated child would help if the UI feels heavy.
8. **Session accuracy is genuinely low in practice** (~26–30% observed with nobody
   posing). Worth checking whether `form_corrector` thresholds and the templates
   agree with the retuned `ANGLE_TOLERANCE`.

---

## Highest-leverage idea not yet done

The app **already knows which pose it asked you to hold**, and currently ignores
that when classifying — it does open-set classification across all 24 poses every
frame. Weighting predictions toward the expected pose, or scoring form against the
target template instead of classifying, would beat any further model work. The
whole Chair/Cat-Cow class of error disappears if the session simply trusts that it
asked for Chair.

The classifier costs 1.1–3.9 ms of a 32.7 ms frame, so there is compute headroom
for this — but not for anything that adds to the per-frame budget.

---

## Related directories

- `~/Downloads/Horizons-main` — older copy, **missing `models/pose_classifier.pkl`**, won't run
- `~/Downloads/PoseFlow-Merged-Archive` — different lineage, separate GitHub remote,
  flattened layout, 3.1 GB including 1.4 GB of IDE history archives. Not this project.
