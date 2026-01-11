from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class TaskStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class TaskStage(str, enum.Enum):
    INITIAL = "initial"
    UNPACKING = "unpacking"
    DE_DUPLICATION = "de_duplication"
    PREVIEW_GENERATION = "preview_generation"
    FOCUS_DETECTION = "focus_detection"
    CROPPING = "cropping"
    TAGGING = "tagging"
    PACKAGING = "packaging"
    FINISHED = "finished"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    stage = Column(Enum(TaskStage), default=TaskStage.INITIAL)
    progress = Column(Integer, default=0)
    message = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    focus_model = Column(String)
    tag_model = Column(String)
    api_key = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    config = Column(JSON, default=dict)
    stats = Column(JSON, default=dict)
    upload_path = Column(String)
    export_path = Column(String)

    images = relationship("Image", back_populates="task")
    logs = relationship("Log", back_populates="task")
