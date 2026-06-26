from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .task import Base


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_MOJIBAKE_REPLACEMENTS = {
    "鍘婚噸": "去重",
    "淇濈暀": "保留",
    "涓㈠純": "丢弃",
    "鍗犳瘮": "占比",
    "宸蹭繚瀛橀€夋嫨": "已保存选择",
    "淇濆瓨澶辫触": "保存失败",
    "棰勮": "预览",
    "瑙ｅ帇": "解压",
    "鎵撳寘": "打包",
    "鎻愮ず璇�": "提示词",
    "瑁佸垏": "裁切",
}


def repair_mojibake_message(value) -> str:
    text = str(value or "")
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    level = Column(Enum(LogLevel), default=LogLevel.INFO)
    message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="logs")

    def __init__(self, **kwargs):
        if "message" in kwargs:
            kwargs["message"] = repair_mojibake_message(kwargs.get("message"))
        super().__init__(**kwargs)
