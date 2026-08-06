"""Local Windows dev entrypoint. `uvicorn app.main:app` (used in Docker/Linux,
see Dockerfile) creates its event loop via `asyncio.run()` before app.main is
even imported, which is too late to override the loop policy from inside
main.py on Windows. This script sets the policy first, then hands off to
uvicorn programmatically."""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
