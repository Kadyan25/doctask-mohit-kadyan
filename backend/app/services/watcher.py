import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings
from app.db.models import Document, Pile, Run
from app.db.session import SessionLocal
from app.services.document_parser import SUPPORTED_EXTENSIONS

logger = logging.getLogger("watcher")


class _NewDocumentHandler(FileSystemEventHandler):
    """Runs in watchdog's own thread, not the asyncio loop — every callback
    bridges back to the loop via run_coroutine_threadsafe. Piles are watched
    as subfolders of WATCH_FOLDER_PATH named by pile id; dropping a file into
    {WATCH_FOLDER_PATH}/{pile_id}/ is the entire "stays alive" trigger, no
    API call required.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, graph):
        self._loop = loop
        self._graph = graph

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        asyncio.run_coroutine_threadsafe(self._handle_new_file(path), self._loop)

    async def _handle_new_file(self, path: Path):
        pile_id = path.parent.name
        # Give the writer a moment to finish before we read it.
        await asyncio.sleep(0.5)

        with SessionLocal() as db:
            pile = db.get(Pile, pile_id)
            if pile is None:
                logger.warning("watcher: %s dropped under unknown pile %s, ignoring", path.name, pile_id)
                return

            # Idempotent: a duplicate on_created for a path we've already
            # ingested must not create a second Document/run for it.
            already_ingested = (
                db.query(Document)
                .filter(Document.pile_id == pile_id, Document.raw_storage_path == str(path))
                .first()
            )
            if already_ingested is not None:
                return

            content = path.read_bytes()
            document = Document(
                pile_id=pile_id,
                filename=path.name,
                mime_type="application/octet-stream",
                raw_storage_path=str(path),
                content_hash=hashlib.sha256(content).hexdigest(),
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            new_document_id = str(document.id)

            thread_id = str(uuid.uuid4())
            run = Run(pile_id=pile_id, status="running", thread_id=thread_id)
            db.add(run)
            db.commit()
            run_id = str(run.id)

        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {"pile_id": pile_id, "run_id": run_id, "document_ids": [new_document_id]}
        try:
            await self._graph.ainvoke(initial_state, config=config)
            status = "completed"
        except Exception:
            logger.exception("watcher: incremental run failed for %s", path)
            status = "failed"

        with SessionLocal() as db:
            run_row = db.get(Run, run_id)
            if run_row is not None:
                run_row.status = status
                run_row.completed_at = datetime.now(timezone.utc)
                db.commit()


def start_watcher(loop: asyncio.AbstractEventLoop, graph) -> Observer:
    Path(settings.watch_folder_path).mkdir(parents=True, exist_ok=True)
    handler = _NewDocumentHandler(loop, graph)
    observer = Observer()
    observer.schedule(handler, settings.watch_folder_path, recursive=True)
    observer.start()
    return observer
