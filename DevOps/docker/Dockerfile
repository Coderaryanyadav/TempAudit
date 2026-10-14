# TempAudit / FinAuditPro - application container
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FINAUDIT_DB_PATH=/data/finauditpro.db \
    PYTHONPATH=/app

WORKDIR /app

# Install only the runtime dependencies declared by the existing project.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY run.py ./run.py
RUN mkdir -p /data /app/backend/backups /app/backend/uploaded_files \
    /app/backend/reports_generated /app/backend/logs

EXPOSE 8000
VOLUME ["/data"]

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
