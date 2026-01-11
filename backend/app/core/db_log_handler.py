import logging
from sqlalchemy.orm import Session
from app.models.log import Log, LogLevel
from app.core.config import settings

class DatabaseLogHandler(logging.Handler):
    """自定义日志处理器，将日志写入数据库"""
    
    def __init__(self, db_session_factory):
        super().__init__()
        self.db_session_factory = db_session_factory
    
    def emit(self, record):
        """处理日志记录，写入数据库"""
        try:
            # 创建数据库会话
            db = self.db_session_factory()
            
            # 获取日志级别
            level = self._get_log_level(record.levelno)
            
            # 解析task_id（如果有的话）
            task_id = None
            if hasattr(record, 'task_id'):
                task_id = record.task_id
            elif isinstance(record.args, tuple) and len(record.args) > 0:
                # 尝试从日志消息中提取task_id（例如："Dedup Task 123: ..."）
                message = self.format(record)
                import re
                match = re.search(r'Task\s+(\d+)', message)
                if match:
                    task_id = int(match.group(1))
            
            # 创建日志记录
            log = Log(
                task_id=task_id,
                level=level,
                message=self.format(record)
            )
            
            # 写入数据库
            db.add(log)
            db.commit()
        except Exception as e:
            # 如果写入数据库失败，不影响程序运行
            print(f"Failed to write log to database: {e}")
        finally:
            db.close()
    
    def _get_log_level(self, levelno):
        """将logging模块的级别转换为LogLevel枚举"""
        if levelno >= logging.CRITICAL:
            return LogLevel.CRITICAL
        elif levelno >= logging.ERROR:
            return LogLevel.ERROR
        elif levelno >= logging.WARNING:
            return LogLevel.WARNING
        elif levelno >= logging.INFO:
            return LogLevel.INFO
        else:
            return LogLevel.DEBUG