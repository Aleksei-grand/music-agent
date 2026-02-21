# MyFlowMusic (MFM) Docker Image - GrandEmotions / VOLNAI
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy project
COPY . .

# Create directories
RUN mkdir -p storage vault logs

# Expose port for Web UI
EXPOSE 8080

# Default command
CMD ["python", "agent.py", "web", "--host", "0.0.0.0"]
