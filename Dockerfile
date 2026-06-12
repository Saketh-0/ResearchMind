# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Install system build dependencies and compile python packages
FROM python:3.10-slim AS backend-builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Use a virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies in the virtual environment
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=1000 torch --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Stage 3: Production runner stage (clean and minimal)
FROM python:3.10-slim AS runner
WORKDIR /app

# Copy the pre-built virtual environment
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy backend source code
COPY api/ ./api
COPY rag/ ./rag
COPY utils/ ./utils
COPY evaluation/ ./evaluation

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directory and grant full read/write permissions
RUN mkdir -p /app/data && chmod -R 777 /app/data

# Expose port and run server
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
