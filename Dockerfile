# Build stage for frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.10-slim
WORKDIR /app

# Install system build dependencies (required for some python packages like building faiss/sqlite if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY api/ ./api
COPY rag/ ./rag
COPY utils/ ./utils
COPY evaluation/ ./evaluation

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directory and grant full read/write permissions for non-root runtime environments
RUN mkdir -p /app/data && chmod -R 777 /app/data

# Expose port and run server
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
