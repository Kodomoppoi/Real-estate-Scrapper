import logging
from datetime import datetime
from typing import List, Optional


class StreamlitLogHandler(logging.Handler):
    """
    Custom thread-safe logging handler that collects log messages
    for streaming into the Streamlit UI console.
    """
    def __init__(self, max_records: int = 150):
        super().__init__()
        self.max_records = max_records
        self.log_messages: List[str] = []

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            # Filter out internal verbose requests
            if "HTTP Request:" in msg or "missing ScriptRunContext" in msg:
                return

            timestamp = datetime.now().strftime("%H:%M:%S")

            tag = "[INFO]"
            if "DuckDuckGo" in msg or "search" in msg.lower():
                tag = "[SEARCH]"
            elif "Crawl" in msg or "crawling" in msg.lower() or "http" in msg.lower():
                tag = "[CRAWL]"
            elif "LLM" in msg or "curat" in msg.lower() or "extract" in msg.lower():
                tag = "[LLM]"
            elif "saved" in msg.lower() or "conclu" in msg.lower() or "sucesso" in msg.lower() or "finalizada" in msg.lower():
                tag = "[DONE]"
            elif record.levelno >= logging.WARNING:
                tag = "[WARN]"

            formatted_entry = f"[{timestamp}] {tag:<8} {msg}"
            self.log_messages.append(formatted_entry)

            if len(self.log_messages) > self.max_records:
                self.log_messages.pop(0)

        except Exception:
            pass

    def get_logs_as_text(self) -> str:
        return "\n".join(self.log_messages)

    def clear(self):
        self.log_messages.clear()


_global_handler: Optional[StreamlitLogHandler] = None


def get_log_handler() -> StreamlitLogHandler:
    global _global_handler
    if _global_handler is None:
        _global_handler = StreamlitLogHandler()
        _global_handler.setFormatter(logging.Formatter("%(message)s"))
    return _global_handler


def attach_log_handler():
    """Attaches the log streamer to the core pipeline loggers."""
    handler = get_log_handler()
    target_loggers = [
        "",  # Root logger
        "src.search",
        "src.scraper",
        "src.extractor",
        "src.pipeline",
    ]
    for name in target_loggers:
        lgr = logging.getLogger(name)
        if handler not in lgr.handlers:
            lgr.addHandler(handler)
            lgr.setLevel(logging.INFO)
