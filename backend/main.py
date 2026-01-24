"""Main entry point for English Tutor application."""

import uvicorn

from src.english_tutor.api.app import app  # noqa: F401

if __name__ == "__main__":
    # Configure uvicorn to use our logging configuration
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
            "src.english_tutor.services.content_sync": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": True,
            },
            "src.english_tutor.api.sync": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": True,
            },
        },
    }
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_config=log_config,
    )
