import asyncio
import shutil
import time
import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings
from app.db.models import Document, Pile, Run
from app.db.session import SessionLocal
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.incremental_pipeline import build_incremental_graph
from app.services.watcher import start_watcher
from tests.conftest import CORPUS_DIR, cleanup_pile


@pytest.mark.asyncio
async def test_dropping_a_file_triggers_processing_without_an_api_call(tmp_path):
    """Movement 3's actual trigger, proven — not just the graph it eventually
    calls. No API call anywhere in this test: a file lands in the pile's
    watched folder, and a Document row plus a completed Run appear on their
    own."""
    watch_root = tmp_path / "watch_root"
    watch_root.mkdir()

    with SessionLocal() as db:
        pile = Pile(name=f"watcher-test-{uuid.uuid4().hex[:8]}")
        db.add(pile)
        db.commit()
        db.refresh(pile)
        pile_id = str(pile.id)
        pile_dir = watch_root / pile_id
        pile_dir.mkdir()
        pile.watch_folder_path = str(pile_dir)
        db.commit()

    original_watch_path = settings.watch_folder_path
    settings.watch_folder_path = str(watch_root)
    loop = asyncio.get_event_loop()

    try:
        async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
            await saver.setup()
            graph = build_incremental_graph(saver)
            observer = start_watcher(loop, graph)
            try:
                shutil.copy(CORPUS_DIR / "project_plan.md", pile_dir / "project_plan.md")

                deadline = time.monotonic() + 10
                document = None
                while time.monotonic() < deadline and document is None:
                    await asyncio.sleep(0.5)
                    with SessionLocal() as db:
                        document = db.query(Document).filter(Document.pile_id == pile_id).first()
                assert document is not None, "watcher never picked up the dropped file"

                deadline = time.monotonic() + 10
                run = None
                while time.monotonic() < deadline:
                    with SessionLocal() as db:
                        run = db.query(Run).filter(Run.pile_id == pile_id).first()
                    if run is not None and run.status == "completed":
                        break
                    await asyncio.sleep(0.5)

                assert run is not None
                assert run.status == "completed"
            finally:
                observer.stop()
                observer.join()
    finally:
        settings.watch_folder_path = original_watch_path
        cleanup_pile(pile_id)
