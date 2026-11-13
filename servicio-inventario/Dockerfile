FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# La base SQLite vive en /data (montado como volumen para que no se pierda)
ENV DB_PATH=/data/inventario.db
RUN mkdir -p /data

EXPOSE 5002
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]
