import logging
import sys
from typing import Any, Optional
import structlog
from asgi_correlation_id import correlation_id

from app.core.config import settings


def inject_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Extracts active correlation ID from contextvars and injects into structured log."""
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def setup_logging() -> None:
    """
    Configures structured logging across the application.
    Unifies standard Python logging (FastAPI, Uvicorn, SQLAlchemy) and structlog
    into a cohesive, machine-parseable pipeline with correlation ID tracing.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    is_json = (settings.ENVIRONMENT.lower() == "production") or settings.LOG_JSON_FORMAT

    # Common processors executed for both structlog and standard library logs
    common_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        inject_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
        ]
        + common_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Choose renderer based on environment (JSON in production, colored console in development)
    if is_json:
        final_renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        final_renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=common_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            final_renderer,
        ],
    )

    # Configure root standard logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Quiet overly chatty loggers
    for noisy_logger in ["uvicorn.access", "asyncpg"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Convenience accessor to obtain a bound structlog logger."""
    return structlog.get_logger(name)
