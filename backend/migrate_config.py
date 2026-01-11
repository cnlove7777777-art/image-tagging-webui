from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Enum, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add the current directory to Python path
sys.path.append('.')

# Create engine
DATABASE_URL = "sqlite:///./data/db.sqlite3"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

try:
    # Check if the column already exists
    result = session.execute(text("PRAGMA table_info(tasks);")).fetchall()
    columns = [col[1] for col in result]
    
    if 'config' not in columns:
        # Add the config column
        session.execute(text("ALTER TABLE tasks ADD COLUMN config JSON DEFAULT '{}';"))
        print("Added 'config' column to tasks table")
    else:
        print("'config' column already exists in tasks table")
        
    if 'stats' not in columns:
        # Add the stats column (just in case it's also missing)
        session.execute(text("ALTER TABLE tasks ADD COLUMN stats JSON DEFAULT '{}';"))
        print("Added 'stats' column to tasks table")
    else:
        print("'stats' column already exists in tasks table")
        
    session.commit()
except Exception as e:
    print(f"Error: {e}")
    session.rollback()
finally:
    session.close()
    engine.dispose()
