"""Main entry point for English Tutor application."""

import uvicorn

from src.english_tutor.api.app import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
