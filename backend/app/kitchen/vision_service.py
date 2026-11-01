"""Glue between the camera, the recognition logic and the database (spec §6).

One instance lives on `app.state.vision`. It is called from request handlers, from the scanner thread
(barcode hits) and from its own worker thread (automatic mode), so the embedder and the gallery are
used under one lock. Nothing here may raise into the scanner thread.
"""

import logging
import threading
import time
import uuid
from pathlib import Path

from app import clock
from app.db import connect
from app.kitchen import repo, vision

log = logging.getLogger(__name__)

CHECK_EVERY = 0.25  # seconds between automatic-mode checks
JPEG_QUALITY = 85
SOURCES = ("learn", "scan", "confirm")


class VisionUnavailable(Exception):
    pass


class VisionService:
    def __init__(self, data_dir: Path, db_path: Path, publish, loader=vision.load_embedder, clock_fn=time.monotonic):
        self.dir = Path(data_dir) / "vision"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._data_dir, self._db_path, self._publish = Path(data_dir), db_path, publish
        self._loader, self._clock = loader, clock_fn
        self._loaded = False
        self._embedder = None
        self.message: str | None = None
        self._lock = threading.RLock()  # embedder, gallery, watcher
        self._save_lock = threading.Lock()  # duplicate check + cap + insert happen as one step
        self._gallery = None
        self._signature = None
        self._version = 0  # bumped whenever learned pictures change
        self._session = 0
        self._barcode_thread: threading.Thread | None = None
        self.tokens = vision.TokenStore(clock=clock_fn)
        self._watcher = vision.Watcher(clock_fn)
        self._worker: threading.Thread | None = None
        self._seq = 0
        self.last: dict = {"seq": 0, "token": None, "decision": "none", "matches": []}

    # --- model -----------------------------------------------------------------------------------

    def _ensure(self):
        with self._lock:
            if not self._loaded:
                self._embedder, self.message = self._loader(self._data_dir)
                self._loaded = True
            return self._embedder

    @property
    def available(self) -> bool:
        return self._ensure() is not None

    def _require(self):
        emb = self._ensure()
        if emb is None:
            raise VisionUnavailable(self.message or vision.NOT_INSTALLED)
        return emb

    def _embed(self, frame):
        """(vector, jpeg bytes of the 224×224 picture) for a camera frame."""
        emb = self._require()
        img = vision.model_input(frame)
        with self._lock:
            vec = emb.embed(img)
        return vec, self._jpeg(img)

    @staticmethod
    def _jpeg(img) -> bytes:
        cv2 = vision._cv2()
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return buf.tobytes() if ok else b""

    # --- database ----------------------------------------------------------------------------------

    def _conn(self):
        return connect(self._db_path)

    def _model(self) -> str:
        return self._require().model_id

    def _refresh(self, conn) -> None:
        archived = tuple(conn.execute("SELECT COUNT(*), TOTAL(id) FROM item WHERE archived=1").fetchone())
        sig = (self._version, archived)
        with self._lock:
            if self._gallery is not None and sig == self._signature:
                return
            emb = self._require()
            rows = conn.execute(
                "SELECT m.item_id, m.embedding FROM item_image m JOIN item i ON i.id = m.item_id "
                "WHERE i.archived=0 AND m.model=?", (emb.model_id,)
            ).fetchall()
            gallery = vision.Gallery()
            vecs = ((r["item_id"], vision.from_blob(r["embedding"])) for r in rows)
            gallery.set((i, v) for i, v in vecs if len(v) == emb.dim)
            self._gallery, self._signature = gallery, sig

    def _matches(self, vec) -> list[tuple[int, float]]:
        conn = self._conn()
        try:
            self._refresh(conn)
        finally:
            conn.close()
        with self._lock:
            return self._gallery.match(vec)

    def _result(self, vec, jpeg, matches, *, code: str | None = None) -> dict:
        token = self.tokens.put((vec, jpeg), code=code)
        conn = self._conn()
        try:
            out = []
            for item_id, score in matches:
                try:
                    out.append({"item": repo.item_json(repo.fetch_item(conn, item_id)), "score": round(score, 3)})
                except repo.NotFound:
                    continue
        finally:
            conn.close()
        return {"token": token, "decision": vision.decide(matches), "matches": out}

    def _save(self, item_id: int, vec, jpeg: bytes, source: str) -> bool:
        """Store a learned picture unless it repeats one already learned. Raises repo.NotFound."""
        emb = self._require()
        removed_files: list[str] = []
        with self._save_lock:
            conn = self._conn()
            try:
                repo.fetch_item(conn, item_id)
                rows = conn.execute(
                    "SELECT id, embedding, source FROM item_image WHERE item_id=? AND model=? ORDER BY id",
                    (item_id, emb.model_id),
                ).fetchall()
                learned = [vision.from_blob(r["embedding"]) for r in rows]
                if any(len(v) == len(vec) and vision.cosine(v, vec) >= vision.DUPLICATE for v in learned):
                    return False
                excess = len(rows) + 1 - vision.MAX_PER_ITEM
                automatic = [r for r in rows if r["source"] != "learn"]
                if excess > 0 and source != "learn" and len(automatic) < excess:
                    return False  # the item is full of pictures from "Lär in"; keep those
                # Oldest automatic pictures go first; pictures from "Lär in" only when there are none.
                victims = sorted(rows, key=lambda r: (r["source"] == "learn", r["id"]))[:max(excess, 0)]
                name = f"{uuid.uuid4().hex}.jpg"
                path = self.dir / name
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO item_image (item_id, file, model, embedding, source, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (item_id, name, emb.model_id, vision.to_blob(vec), source, clock.to_iso(clock.utcnow())),
                        )
                        removed_files = self._delete_rows(conn, [r["id"] for r in victims])
                        path.write_bytes(jpeg)
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
            finally:
                conn.close()
            self._unlink(removed_files)
            self._version += 1
        self._publish("vision")
        return True

    def _delete_rows(self, conn, ids) -> list[str]:
        """Delete rows (inside the caller's transaction); returns their files to remove after commit."""
        files = []
        for image_id in ids:
            row = conn.execute("SELECT file FROM item_image WHERE id=?", (image_id,)).fetchone()
            if row is None:
                continue
            conn.execute("DELETE FROM item_image WHERE id=?", (image_id,))
            files.append(row["file"])
        return files

    def _unlink(self, files) -> None:
        for f in files:
            (self.dir / Path(f).name).unlink(missing_ok=True)

    # --- public API ------------------------------------------------------------------------------

    def status(self) -> dict:
        available = self.available
        count = 0
        if available:
            conn = self._conn()
            try:
                count = conn.execute("SELECT COUNT(*) FROM item_image WHERE model=?", (self._model(),)).fetchone()[0]
            finally:
                conn.close()
        return {"available": available, "message": None if available else self.message, "images": count}

    def identify(self, frame) -> dict:
        vec, jpeg = self._embed(frame)
        return {"seq": 0, **self._result(vec, jpeg, self._matches(vec))}

    def capture(self, item_id: int, frame) -> dict:
        vec, jpeg = self._embed(frame)
        saved = self._save(item_id, vec, jpeg, "learn")
        conn = self._conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM item_image WHERE item_id=? AND model=?", (item_id, self._model())).fetchone()[0]
        finally:
            conn.close()
        return {"saved": saved, "count": count}

    def confirm(self, token: str, item_id: int) -> bool:
        entry = self.tokens.get(token)
        if entry is None:
            return False
        return self._save(item_id, entry[0], entry[1], "confirm")

    def on_barcode(self, code: str, frame) -> None:
        """Scanner thread: a barcode was read. The picture is learned in the background."""
        try:
            self._watcher.barcode_seen()  # plain attribute writes: no lock, so the scanner never waits
            if frame is None or not self.available:
                return
            t = threading.Thread(target=self._learn_barcode, args=(code, frame), name="vision-barcode", daemon=True)
            self._barcode_thread = t
            t.start()
        except Exception:  # noqa: BLE001  - never raise into the scanner thread
            log.exception("Could not handle barcode %s", code)

    def _learn_barcode(self, code: str, frame) -> None:
        try:
            vec, jpeg = self._embed(frame)
            self._watcher.hold(vec)
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT b.item_id FROM barcode b JOIN item i ON i.id=b.item_id WHERE b.code=? AND i.archived=0", (code,)
                ).fetchone()
            finally:
                conn.close()
            if row:
                self._save(row["item_id"], vec, jpeg, "scan")
            else:
                self.tokens.put((vec, jpeg), code=code)
        except Exception:  # noqa: BLE001
            log.exception("Could not learn a picture for barcode %s", code)

    def on_linked(self, code: str, item_id: int) -> bool:
        entry = self.tokens.for_code(code)
        if entry is None:
            return False
        try:
            return self._save(item_id, entry[0], entry[1], "scan")
        except (repo.NotFound, VisionUnavailable):
            return False

    # --- automatic mode ----------------------------------------------------------------------------

    def start_session(self, scanner) -> None:
        """Start the automatic-mode worker for a scan session (no-op if recognition is unavailable)."""
        if not self.available:
            return
        with self._lock:
            self._session += 1
            self._watcher = vision.Watcher(self._clock)
            self._worker = threading.Thread(target=self._run, args=(scanner, self._session), name="vision", daemon=True)
            self._worker.start()

    def _run(self, scanner, session: int) -> None:
        try:
            while scanner.running and session == self._session:
                frame = scanner.latest_frame()
                if frame is not None:
                    with self._lock:
                        watcher = self._watcher
                    watcher.step(frame, lambda f: self._embed(f)[0], lambda vec: self._suggest(frame, vec))
                time.sleep(CHECK_EVERY)
        except Exception:  # noqa: BLE001  - automatic mode stops; scanning goes on
            log.exception("Automatic recognition stopped")

    def _suggest(self, frame, vec) -> bool:
        """Automatic mode: show a card only when the item is recognised with confidence."""
        matches = self._matches(vec)
        if vision.decide(matches) != "sure":
            return False
        result = self._result(vec, self._jpeg(vision.model_input(frame)), matches)
        if not result["matches"]:
            return False
        self._seq += 1
        self.last = {"seq": self._seq, **result}
        self._publish("vision")
        return True

    def wait_idle(self, timeout: float = 2.0) -> None:
        """Tests: wait for the worker (after the scanner stopped) and any barcode learning to finish."""
        for t in (self._worker, self._barcode_thread):
            if t is not None:
                t.join(timeout)

    # --- learned pictures ----------------------------------------------------------------------------

    def items(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT i.id, i.name, COUNT(m.id) AS n, MAX(m.id) AS newest FROM item_image m "
                "JOIN item i ON i.id = m.item_id WHERE i.archived=0 GROUP BY i.id ORDER BY i.name COLLATE NOCASE"
            ).fetchall()
            out = []
            for r in rows:
                cover = conn.execute("SELECT file FROM item_image WHERE id=?", (r["newest"],)).fetchone()["file"]
                out.append({"item_id": r["id"], "name": r["name"], "count": r["n"], "cover": f"/vision/{cover}"})
            return out
        finally:
            conn.close()

    def item_images(self, item_id: int) -> list[dict]:
        conn = self._conn()
        try:
            repo.fetch_item(conn, item_id)
            rows = conn.execute(
                "SELECT id, file, source, created_at FROM item_image WHERE item_id=? ORDER BY id DESC", (item_id,)
            ).fetchall()
            return [{"id": r["id"], "url": f"/vision/{r['file']}", "source": r["source"], "created_at": r["created_at"]} for r in rows]
        finally:
            conn.close()

    def delete_image(self, image_id: int) -> bool:
        with self._save_lock:
            conn = self._conn()
            try:
                with conn:
                    removed = self._delete_rows(conn, [image_id])
            finally:
                conn.close()
            self._unlink(removed)
            self._version += 1
        if removed:
            self._publish("vision")
        return bool(removed)

    def delete_item_images(self, item_id: int) -> int:
        with self._save_lock:
            conn = self._conn()
            try:
                repo.fetch_item(conn, item_id)
                with conn:
                    ids = [r["id"] for r in conn.execute("SELECT id FROM item_image WHERE item_id=?", (item_id,))]
                    removed = self._delete_rows(conn, ids)
            finally:
                conn.close()
            self._unlink(removed)
            self._version += 1
        self._publish("vision")
        return len(removed)
