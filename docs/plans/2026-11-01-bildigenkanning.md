# Bildigenkänning (Kök etapp 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recognise pantry items from the webcam picture (nearest neighbour over MobileNetV2 embeddings), learn new items from a few pictures, and manage learned pictures on the phone.

**Architecture:** Pure logic in `backend/app/kitchen/vision.py` (embedders, gallery, decision, motion/background watcher, pending tokens) and `backend/app/kitchen/vision_service.py` (ties scanner frames, DB and files together, owns the worker thread). HTTP in `backend/app/routers/kitchen_vision.py`. UI in `frontend/src/kitchen/` (scan sheet additions, `VisionResult.jsx`, `LearnSheet.jsx`) and `frontend/src/kitchen/admin/VisionImages.jsx`.

**Tech Stack:** as before. No new Python or npm dependency; model run with `cv2.dnn`.

**Spec:** `docs/specs/2026-11-01-bildigenkanning-design.md`

## Global Constraints

- UI text Swedish; code, comments, commits English.
- Model id `mobilenetv2-2022apr`, file `~/tvatt-data/models/mobilenetv2.onnx` (`TVATT_VISION_MODEL`), sha256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`. Fake embedder id `histogram-v1` via `TVATT_FAKE_VISION=1`.
- Thresholds: SURE 0.80, MAYBE 0.65, MARGIN 0.05, duplicate 0.97, background 0.92, still diff 6/255 over 2 checks at 4 Hz, cap 40 images per item, tokens 30 / 10 min, barcode quiet time 2 s.
- Learn: 8 pictures, one per 700 ms, max 16 attempts.
- Errors `{"detail": "<svensk text>"}`; non-integer ids → 422/404, never 500.
- Kiosk tap targets ≥ 72 px; fits 800×480.

## Review Focus

1. Worker thread and scanner thread share the embedder: all `cv2.dnn` calls under one lock; scanner stop ends the worker; no exception in the worker can stop the scanner → `test_worker_error_does_not_stop_scanner`.
2. Cap/duplicate logic never deletes `learn` pictures while automatic ones exist → `test_cap_removes_oldest_automatic_first`.
3. Background/stillness: an empty scene never produces a suggestion; holding the same item still produces exactly one suggestion until the picture moves → `test_watcher_*`.
4. Confirm with an unknown/expired token or archived item never raises 500.
5. Deleting images removes files and refreshes the gallery.

---

### Task 1: Embedders and gallery (`kitchen/vision.py`)
- [ ] Tests: center crop geometry; preprocess shape/normalisation; feature-layer choice with fake net and a tiny Darknet net through `cv2.dnn`; histogram embedder separates colours; gallery top-3/max-per-item; decisions sure/maybe/none incl. margin; float16 round-trip; token store limit + expiry; watcher (still, background, one suggestion per hold, barcode quiet time).
- [ ] Implement `center_crop`, `OnnxEmbedder`, `HistogramEmbedder`, `load_embedder()`, `Gallery`, `decide()`, `TokenStore`, `Watcher`.

### Task 2: Schema, service and scanner hooks
- [ ] `item_image` table in `kitchen/schema.py`; `Scanner.latest_frame()`; scanner calls `on_scan(code)` after storing the frame.
- [ ] `VisionService`: `status()`, `identify()`, `capture(item_id)`, `confirm(token, item_id)`, `on_barcode(code)`, `on_linked(code, item_id)`, `start_session()` (worker), image listing/deleting, duplicate + cap.
- [ ] Wire in `main.py` (`vision_embedder` factory param for tests), mount `/vision`.
- [ ] Tests for service with fake camera frames and histogram embedder.

### Task 3: API (`routers/kitchen_vision.py`) + barcode hooks
- [ ] Routes from spec §7; `scan_start` starts the vision session; `link_barcode` calls `on_linked`.
- [ ] API tests incl. 503/409/422/404 paths and auto-learn.

### Task 4: Kiosk UI
- [ ] Store: `vision` state + topic, `visionStatus`.
- [ ] `ScanSheet`: header buttons, automatic suggestion when idle, identify button.
- [ ] `VisionResult.jsx` (sure/maybe/none), `KnownItem` `onAction` confirm hook + "Lär in bilder", `LearnSheet.jsx`.
- [ ] Build static bundle.

### Task 5: Phone admin page
- [ ] Hantera → Inlärda bilder list + item page (thumb grid, delete with Ångra, Ta bort alla with confirm).

### Task 6: E2E tests
- [ ] Fake camera colour frames + `TVATT_FAKE_VISION=1`: learn, recognise, act; admin page delete.

### Task 7: Install, calibration script, docs
- [ ] `deploy/get-model.sh` (+ called from install/update, non-fatal); tests with stub curl/sha256sum.
- [ ] `camera_test.py --recognize`.
- [ ] README (Bildigenkänning section, felsökning).

### Task 8: Final review
- [ ] Independent reviewer against spec + Review Focus; fix important findings; full test suite; push; update `kontext.md`.
