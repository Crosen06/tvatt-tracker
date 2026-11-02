# Item outline, scores and more learned pictures – implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recognise only the item held in a guide box (not the person holding it), draw its outline with name and score in the camera picture, and learn 24 pictures per item.

**Architecture:** A new `kitchen/locate.py` cuts the item out of a centred guide box with GrabCut, with faces (YuNet) as forced background, and returns a masked 224×224 picture plus the contour. `vision_service` embeds that picture instead of the old 80 % centre square. Its worker analyses every 0.4 s and keeps the latest analysis, and `kitchen/overlay.py` draws it into the MJPEG preview through a new `Scanner(overlay=…)` hook.

**Tech Stack:** Python 3, OpenCV (`cv2.grabCut`, `cv2.FaceDetectorYN`, `cv2.dnn`), numpy, Pillow (text), Starlette, React 19 (esbuild via `node frontend/build.mjs`), pytest, Playwright.

**Spec:** `docs/specs/2026-11-02-varans-kontur-design.md` (changes `docs/specs/2026-11-01-bildigenkanning-design.md`).

## Global Constraints

- UI text in Swedish; code, comments and commits in English. Commit messages end with the Co-Authored-By/Claude-Session lines.
- Guide box: centred square, side = `TVATT_VISION_BOX` × shorter side, default 0.6, clamped to 0.3–0.9. Work area = box + 20 % of side each way, clipped to the frame. GrabCut runs on the work area downscaled so its longest side is ≤ 200 px, 3 iterations.
- A cut-out counts as the item when it covers 4–92 % of the box. Outside the item mask (dilated 3 px) pixels become BGR (124, 116, 104). Crop = square around the item's bounding rectangle + 10 %.
- Faces: YuNet `face_yunet.onnx` (sha256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`, 232 589 bytes), detection at 320 px width, score ≥ 0.7, boxes grown 15 % each way; `TVATT_FACE_MODEL` overrides the path.
- Model ids get the suffix `-obj1`: `mobilenetv2-2022apr-<dim>-obj1`, `histogram-v1-obj1`. Legacy ids `mobilenetv2-2022apr-<digits>` and `histogram-v1` are purged on first load.
- Item score = mean of its 3 best cosines. Thresholds unchanged (0.80 / 0.65 / 0.05). Max 80 pictures per item.
- Worker analyses every 0.4 s. An analysis older than 1.5 s is not drawn. Colours: sure #2fbf71, maybe #f2b33d, none white. Contour 3 px. Labels: "Mjölk 87 %", "Mjölk? 71 %", "Okänd (Mjölk 42 %)", "Okänd". Hint "Håll varan i rutan". Font Poppins Medium `backend/app/static/fonts/poppins-medium.woff` at 16 px per 640 px width, falling back to Pillow's default font.
- Lär in: 24 pictures, one try per 400 ms, max 48 tries. `POST /api/vision/capture` → `{saved, count, found}`; nothing is saved when `found` is false.
- No new Python or npm packages. Pillow and OpenCV are already dependencies.

## Review Focus

1. **Preview frame aliasing:** at ≤ 640 px wide, `scanner.preview()` returns the frame itself, so drawing on it would corrupt `latest_frame()` (barcodes and recognition). Expected: the overlay draws on a copy. Test in Task 3.
2. **Item held very close (fills the box):** the cut-out covers > 92 % → `found=False` → fallback picture, and `capture` saves nothing. Expected: no crash, no picture saved, and the hint "Håll varan i rutan" shows. Tests in Tasks 1 and 2.
3. **Odd frames:** grey (2-D) frames, tiny frames (64×48) and frames where GrabCut raises. Expected: `locate` never raises and returns a valid 224×224×3 picture. Test in Task 1.
4. **Stale outline after the camera stops or the worker dies:** expected no old contour drawn, only the box, or nothing when the worker is not running. Test in Task 3.
5. **Broken face model file:** expected `load_faces` returns None, logs once, and recognition works. Test in Task 1.

---

### Task 1: `locate.py` – guide box, faces, cut-out

**Files:**
- Create: `backend/app/kitchen/locate.py`
- Modify: `backend/tests/kitchen/vision_images.py` (smaller package and an optional person)
- Test: `backend/tests/kitchen/test_locate.py`

**Interfaces:**
- Produces:
  - `box_fraction() -> float`
  - `guide_box(shape: tuple, fraction: float | None = None) -> tuple[int, int, int, int]` (x, y, w, h; w == h)
  - `@dataclass Located: box: tuple; contour: list[tuple[int, int]] | None; found: bool; image: np.ndarray (224×224×3 uint8); area: float` (share of the box covered by the item, 0 when not found)
  - `locate(frame, faces: Sequence[tuple[int, int, int, int]] = ()) -> Located`
  - `class FaceFinder(path)` with `.find(frame) -> list[tuple[int, int, int, int]]` (grown boxes, frame coords)
  - `load_faces(data_dir: Path) -> FaceFinder | None`
  - Constants `FACE_FILE = "face_yunet.onnx"`, `FACE_SHA256`, `GREY = (124, 116, 104)`
  - `vision_images.scene(item=None, size=(480, 640), seed=0, shift=0, person=False, shirt=0)`. The package is now 0.42·h tall × 0.32·h wide, centred (+shift). `person=True` draws a torso in shirt pattern `shirt` (0: blue/white stripes, 1: green checks) under the package and a skin-coloured oval "face" at the top centre. Existing callers keep working.

- [ ] **Step 1: Write failing tests** in `test_locate.py`:
  - `test_box_fraction_env_and_limits`: unset → 0.6; "0.5" → 0.5; "0.1" → 0.3; "2" → 0.9; "x" → 0.6.
  - `test_guide_box_is_centred_square`: shape (480, 640) → (176, 96, 288, 288).
  - `test_cut_out_follows_package`: `scene("milk", person=True)`. `found` is True, and the IoU between the filled contour mask and the true package rectangle is ≥ 0.8. `image.shape == (224, 224, 3)`, and the image corners equal `GREY` (±2).
  - `test_empty_box_never_raises`: `scene(None, person=True)` and `scene(None)` → a `Located` with a 224×224×3 image.
  - `test_too_big_is_not_found`: a package covering the whole box gives `found` False and `area == 0`, and the image is the box resized.
  - `test_face_is_never_item`: with a face box over the package's top quarter, no contour point lies inside the face box, and the face region of the box image is `GREY` in the not-found case.
  - `test_odd_frames`: a grey 2-D frame, a 64×48 frame and a monkeypatched `cv2.grabCut` that raises all return a 224×224×3 `Located`.
  - `test_load_faces`: missing file → None; garbage file → None, and the warning is logged once over two calls (`caplog`).
  - `test_real_face_model` (skipped unless `TVATT_TEST_MODELS` points at a folder with `face_yunet.onnx`): `FaceFinder.find` on a blank frame → `[]`.
- [ ] **Step 2:** `cd backend && python3 -m pytest tests/kitchen/test_locate.py -q` → fails (ImportError).
- [ ] **Step 3: Implement `locate.py`** per Global Constraints and spec §4. Build the GrabCut mask from `GC_BGD` (work area outside the box, faces, outer 1 px ring) and `GC_PR_FGD` (box). Then: `cv2.grabCut(..., cv2.GC_INIT_WITH_MASK)` → open 3×3 → largest component → fill holes via `drawContours(FILLED)` → `approxPolyDP(0.01·perimeter)` → scale to frame coords. Catch `cv2.error` and other exceptions in `locate` → not found. Grey frames are converted with `COLOR_GRAY2BGR` first. `FaceFinder` uses `cv2.FaceDetectorYN.create(path, "", (320, h·320/w), 0.7)` with `setInputSize` per frame size.
- [ ] **Step 4:** the same command passes. Also `python3 -m pytest tests/kitchen/test_vision.py -q` still passes, since `scene` callers are unchanged.
- [ ] **Step 5: Commit** `feat(kitchen): find the held item in a guide box with GrabCut`.

### Task 2: Embed the cut-out, top-3 scores, legacy purge, capture `found`

**Files:**
- Modify: `backend/app/kitchen/vision.py` (remove `CROP_FRACTION`, `center_crop`, `model_input`; add `METHOD`, `is_legacy`, `TOP_K`; `MAX_PER_ITEM = 80`)
- Modify: `backend/app/kitchen/vision_service.py`
- Modify: `backend/app/routers/kitchen_vision.py` (pass through `found`)
- Test: `backend/tests/kitchen/test_vision.py`, `backend/tests/kitchen/test_vision_api.py`, new `backend/tests/kitchen/test_vision_real.py`

**Interfaces:**
- Consumes: `locate.locate`, `locate.load_faces`, `Located`.
- Produces:
  - `vision.METHOD = "obj1"`; `OnnxEmbedder.model_id == f"{MODEL_ID}-{dim}-obj1"`; `HistogramEmbedder.model_id == "histogram-v1-obj1"`
  - `vision.is_legacy(model_id: str) -> bool` (regex `^mobilenetv2-2022apr-\d+$` or `== "histogram-v1"`)
  - `Gallery.match(vec, k=3)` returns per-item mean of the top `TOP_K = 3` cosines
  - `VisionService.__init__(..., face_loader=locate.load_faces)`
  - `VisionService._analyse(frame) -> tuple[vec, bytes, Located]` (replaces `_embed`)
  - `VisionService.capture(item_id, frame) -> {"saved": bool, "count": int, "found": bool}`
  - `VisionService._suggest(vec, jpeg, matches) -> bool`

- [ ] **Step 1: Write failing tests / update old ones.**
  - `test_vision.py`: delete `test_center_crop_is_middle_square` and `test_model_input_size_and_grey`. Add:
    - `test_gallery_scores_mean_of_best_three`: item 1 with sims [0.9, 0.8, 0.7, 0.1] → 0.8; item 2 with [0.85] → 0.85, ranked first.
    - `test_is_legacy` covering `mobilenetv2-2022apr-1280` (True), `mobilenetv2-2022apr-1280-obj1` (False), `histogram-v1` (True), `histogram-v1-obj1` (False).
  - Update `test_model_id_includes_feature_length` to expect the `-obj1` suffix.
  - `test_vision_api.py`: make the `Cam` scenes use the new `scene` (package fits the box). Add:
    - `test_capture_without_item_saves_nothing`: an empty scene → `{"saved": False, "found": False, "count": 0}`.
    - `test_legacy_pictures_removed_on_start`: insert rows and files with model `histogram-v1` and `histogram-v1-obj1` before first use. After `GET /api/vision/status`, only the `-obj1` row and its file remain, and only the legacy file is deleted.
    - `test_same_item_different_shirt`: the histogram embedder gives cosine ≥ 0.9 between `scene("milk", person=True, shirt=0)` and `shirt=1`.
  - Change cap tests from 40 to `vision.MAX_PER_ITEM`.
  - `test_vision_real.py` (skipped unless `TVATT_TEST_MODELS` has `mobilenetv2.onnx`): with the real embedder and faces, milk on shirt 0 vs milk on shirt 1 scores higher than milk vs coffee on shirt 0. Print both numbers.
- [ ] **Step 2:** `python3 -m pytest tests/kitchen/test_vision.py tests/kitchen/test_vision_api.py -q` → the new tests fail.
- [ ] **Step 3: Implement.** `_ensure` loads the embedder and faces, then runs `_purge_legacy()` once when available (one transaction via `_delete_rows`, unlink afterwards, publish `vision` if anything was removed). `_analyse` calls `locate.locate(frame, faces.find(frame) if faces else ())` and embeds `located.image` under `self._lock`. `capture` returns early without saving when not found, with `count` = current count. `identify`, `_learn_barcode` and `on_linked` use `_analyse` and do not depend on `found`. The router returns the service dict unchanged.
- [ ] **Step 4:** the whole backend suite passes, apart from e2e and the 120 s stream test: `python3 -m pytest -q --ignore=tests/e2e --deselect tests/kitchen/test_scan_api.py::test_stream_returns_jpeg_parts`. Then run the real-model test with `TVATT_TEST_MODELS=/tmp/eval-models` (folder holding `mobilenetv2.onnx` and `face_yunet.onnx`) and record its two numbers in the commit message.
- [ ] **Step 5: Commit** `feat(kitchen): recognise only the cut-out item; mean of best three; purge old pictures`.

### Task 3: Live analysis and the outline in the camera picture

**Files:**
- Create: `backend/app/kitchen/overlay.py`
- Modify: `backend/app/kitchen/vision_service.py` (worker every 0.4 s, `analysis`, `draw_overlay`), `backend/app/kitchen/scanner.py` (`overlay` hook), `backend/app/main.py` (wiring)
- Test: `backend/tests/kitchen/test_overlay.py`, `backend/tests/kitchen/test_scanner.py`, `backend/tests/kitchen/test_vision_api.py`

**Interfaces:**
- Consumes: `locate.guide_box`, `VisionService._analyse`, `_matches`, `_suggest`.
- Produces:
  - `overlay.FRESH = 1.5`
  - `overlay.label_text(analysis: dict) -> str`
  - `overlay.draw(img, frame_size: tuple[int, int], box, analysis: dict | None, now: float) -> np.ndarray`. `frame_size` is (h, w), and `analysis` has keys `at, contour, found, label, score, decision, has_gallery`.
  - `VisionService.analysis: dict | None` and `VisionService.draw_overlay(img, frame_size) -> np.ndarray`
  - `Scanner(..., overlay: Callable[[np.ndarray, tuple[int, int]], np.ndarray] | None = None)`

- [ ] **Step 1: Write failing tests.**
  - `test_overlay.py`:
    - `test_label_text`: the four labels from Global Constraints, with scores 0.87, 0.71, 0.42 and an empty gallery.
    - `test_draw_sure_is_green`: the contour pixels of a 640×360 image drawn from a 1920×1080 analysis are #2fbf71 (BGR (113, 191, 47) ±10) at the scaled positions.
    - `test_stale_analysis_draws_box_only`: with `now - at = 2.0`, no green or yellow pixels, and some white box-corner pixels.
    - `test_label_with_swedish_letters_without_font`: monkeypatch the font path to a missing file → the picture is drawn without an exception and has the same shape.
  - `test_scanner.py`:
    - `test_overlay_draws_on_copy`: a 640×480 fake source with an overlay that fills the image red. `latest_frame()` is never red, and the decoded preview JPEG is red.
    - `test_overlay_error_keeps_preview`: an overlay that raises still yields JPEG frames.
  - `test_vision_api.py`:
    - `test_worker_keeps_latest_analysis`: after learning milk and showing it, `vision.analysis["decision"] == "sure"`, `found`, and `label == "Mjölk"` within 3 s. After `scanner.stop()` and `wait_idle()`, `analysis is None` and `draw_overlay(img, size)` returns `img` unchanged.
- [ ] **Step 2:** run the three test files → the new tests fail.
- [ ] **Step 3: Implement.**
  - `overlay.draw` scales by `img.shape[1] / frame_size[1]`. It draws the box corners (white, 2 px, corner length 18 % of side), and the hint under the box when there is no fresh, found analysis. It draws the contour (3 px) and a label pill above the contour's top point, clamped inside the image, with text through Pillow on the label region only.
  - Load the font once with `ImageFont.truetype(path, size)`, and fall back to `ImageFont.load_default(size)`.
  - In the worker: `CHECK_EVERY = 0.4`. Each loop runs `_analyse`, then `_matches`, sets `self.analysis`, then `watcher.step(frame, lambda f: vec, lambda v: self._suggest(vec, jpeg, matches))`. Clear `analysis` in a `finally`.
  - `draw_overlay` returns `img` untouched unless available and the worker thread is alive. It catches every exception and logs once.
  - `Scanner._run` passes `preview(frame, cv2).copy()` to the overlay, catching exceptions and encoding the undrawn preview on error.
  - `main.py`: `overlay=lambda img, size: app.state.vision.draw_overlay(img, size)`.
- [ ] **Step 4:** run the backend suite command from Task 2 Step 4 → it passes.
- [ ] **Step 5: Commit** `feat(kitchen): draw the guide box, item outline and score in the camera picture`.

### Task 4: Installation, camera_test and README

**Files:**
- Modify: `deploy/get-model.sh`, `scripts/camera_test.py`, `README.md`
- Test: `backend/tests/test_deploy.py`, `backend/tests/kitchen/test_camera_test.py`

**Interfaces:**
- Consumes: `locate.FACE_FILE`, `locate.FACE_SHA256`, `locate.load_faces`, `locate.locate`, `overlay.draw`, `overlay.label_text`.
- Produces:
  - `get-model.sh` downloads both models. Env overrides: `TVATT_MODEL_URL`/`TVATT_MODEL_SHA256` (MobileNetV2) and `TVATT_FACE_URL`/`TVATT_FACE_SHA256` (YuNet). The script exits 1 only when MobileNetV2 fails. A face failure prints "Ansiktsmodellen kunde inte hämtas; ansikten filtreras inte bort." to stderr and exits 0.

- [ ] **Step 1: Write failing tests.**
  - `test_deploy.py`: extend `_model_env` so the stub curl copies a per-URL source (face bytes for URLs containing `yunet`).
    - `test_get_model_downloads_once`: both `mobilenetv2.onnx` and `face_yunet.onnx` exist, and `curl.log` has 2 lines after two runs.
    - `test_get_model_face_failure_is_not_fatal`: a wrong face sha → exit 0, the message on stderr, and no face file.
    - `test_face_checksum_matches_app`: the script's default face sha equals `locate.FACE_SHA256`.
  - `test_camera_test.py`: `test_camera_test_recognize_prints_best_matches` additionally asserts that the output mentions `vara hittad` or `ingen vara i rutan` per second, and that the saved JPEG differs from the raw frame (the overlay is drawn).
- [ ] **Step 2:** `python3 -m pytest tests/test_deploy.py tests/kitchen/test_camera_test.py -q` → fails.
- [ ] **Step 3: Implement.**
  - `camera_test --recognize`: each second print `✓ vara hittad (34 % av rutan)` or `– ingen vara i rutan`, the analysis time in ms, and the top 3. Save the last recognised frame with `overlay.draw` applied (full size).
  - README section "Känna igen varor på bilden": cover the box, the colours and labels, 24 pictures, the removal of old pictures, `TVATT_VISION_BOX`, the face model and `TVATT_FACE_MODEL`.
- [ ] **Step 4:** the same command passes.
- [ ] **Step 5: Commit** `feat(deploy): fetch the face model; camera_test shows the outline`.

### Task 5: Lär in with 24 pictures and a live picture; e2e

**Files:**
- Modify: `frontend/src/kitchen/LearnSheet.jsx`, `frontend/src/kitchen/kitchen.css`, rebuilt `backend/app/static/*` (`cd frontend && node build.mjs`)
- Test: `backend/tests/e2e/test_kitchen_ui.py`

**Interfaces:**
- Consumes: `POST /api/vision/capture` → `{saved, count, found}`; `GET /api/scan/stream`.
- Produces: `LEARN_TARGET = 24`, `MAX_TRIES = 48`, `EVERY_MS = 400`.

- [ ] **Step 1: Update the e2e tests.**
  - `test_learn_then_recognise_item`: the learn sheet shows an `img[alt="Kamerabild"]` and the text "Håll varan i rutan och vrid den långsamt – visa fram, bak och sidor". The toast is "Lärde in 1 bild av Banan" (timeout 30 s, since the fake camera repeats one picture).
  - Add `test_learn_hint_when_no_item`: with an empty scene, the learn sheet shows "Håll varan i rutan" after 5 tries, and ends with "Fick inga nya bilder av Banan".
  - Keep the screenshots.
- [ ] **Step 2:** `python3 -m pytest tests/e2e/test_kitchen_ui.py -q -k "learn"` → fails.
- [ ] **Step 3: Implement.**
  - `LearnSheet` renders the stream (`<img src={"/api/scan/stream?k=" + key} alt="Kamerabild">`, 4:3 like `.scan-preview`, fits 800×480 together with the bar). It counts consecutive `found === false` answers and shows the hint at ≥ 5, keeping the progress text "N av 24 bilder".
  - Rebuild the bundle.
- [ ] **Step 4:** the full suite passes: `python3 -m pytest -q` (including e2e and the 120 s stream test).
- [ ] **Step 5: Commit** `feat(kitchen): learn 24 pictures with the live outline in view`.

### Task 6: Wrap-up

- [ ] Update the project's `claude/kontext.md`: decisions (box/GrabCut/YuNet, -obj1, top 3, 24 pictures, 80 cap), status line, and known small issues. Update the old spec's §3, which says "Ingen objektdetektering", with a pointer to the new spec.
- [ ] Whole-branch review by a fresh reviewer. Fix the important findings.
- [ ] Rebase on `origin/main`, push `main` (as earlier etapper), and tell Charlie: `./deploy/update.sh`, then `scripts/camera_test.py --recognize`, then learn the items again.
