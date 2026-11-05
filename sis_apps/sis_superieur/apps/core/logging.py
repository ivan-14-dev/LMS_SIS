"""Core utilities et middleware - SIS Supérieur."""

import json
import logging


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
        for field in (
            "request_id",
            "tenant_id",
            "user_id",
            "actor_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "app_label",
            "model",
            "object_id",
            "action",
        ):
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)
