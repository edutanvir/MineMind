FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY requirements-runtime.txt .
RUN pip install -r requirements-runtime.txt

COPY . .

# Build the DuckDB file from the Gold Parquet files; the build fails if any view is empty.
RUN python scripts/build_db.py

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
# Cloud Run provides $PORT (8080).
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0"]
