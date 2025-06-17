FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY pulsr/ ./pulsr/

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "pulsr.main:app", "--host", "0.0.0.0", "--port", "8000"]
