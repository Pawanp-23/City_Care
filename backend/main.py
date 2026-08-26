"""Development entry point for CityCare Clinic API."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("core.apis.api:app", host="0.0.0.0", port=8000, reload=True)

