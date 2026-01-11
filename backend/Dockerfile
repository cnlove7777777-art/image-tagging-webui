FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data/tasks /app/data/db

# Expose port
EXPOSE 8081

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
