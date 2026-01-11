import logging
from app.core.config import settings
from app.core.db_log_handler import DatabaseLogHandler
from app.db.database import SessionLocal

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
logger.propagate = False  # 防止重复日志

# Clear existing handlers if any
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Create database handler
db_handler = DatabaseLogHandler(SessionLocal)
db_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
db_handler.setFormatter(formatter)
logger.addHandler(db_handler)

# Also add db handler to root logger to catch all logs
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
root_logger.addHandler(db_handler)
