import asyncio
import sys

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based loop; Windows defaults
    # to ProactorEventLoop, which it explicitly rejects. No-op on Linux/Docker,
    # which is what this ships on.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
