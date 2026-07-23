"""Core utilities et middleware."""
import logging
import json
import time
import uuid


class JsonFormatter(logging.Formatter):
    """Formatter JSON pour logs structurés."""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = record.tenant_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)
