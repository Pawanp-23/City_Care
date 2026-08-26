"""Run the built CityCare frontend and API together for local demonstrations.

This is intentionally separate from the production API module: deployment can
still serve the React build from a CDN or web server, while a local reviewer
gets one URL to open.
"""

from pathlib import Path
import os

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.apis.api import app

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if not frontend_dist.is_dir():
    raise RuntimeError("Frontend build not found. Run `pnpm run build` in frontend first.")

# Keep immutable build assets on their normal URL while the catch-all below
# returns index.html for React routes such as /login and /doctor.
app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="citycare-assets")


@app.get("/{frontend_path:path}", include_in_schema=False)
async def citycare_frontend(frontend_path: str):
    """Serve a real file when present, otherwise let React Router handle it."""
    requested = (frontend_dist / frontend_path).resolve()
    if requested.is_relative_to(frontend_dist) and requested.is_file():
        return FileResponse(requested)
    return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("CITYCARE_PORT", "8002")),
        server_header=False,
    )
