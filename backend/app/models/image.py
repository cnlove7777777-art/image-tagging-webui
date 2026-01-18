from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, Float
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from .task import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    orig_name = Column(String)
    orig_path = Column(String)
    preview_path = Column(String)
    crop_path = Column(String)
    prompt_txt_path = Column(String)
    md5 = Column(String)
    phash = Column(String)
    sharpness = Column(Float)
    width = Column(Integer)
    height = Column(Integer)
    selected = Column(Boolean, default=True)
    meta_json = Column(MutableDict.as_mutable(JSON), default=dict)

    task = relationship("Task", back_populates="images")
