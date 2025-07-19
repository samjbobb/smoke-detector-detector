FROM python:3.12-slim

# Install system dependencies for audio
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY main.py .

# Install dependencies
RUN uv sync

# Run the application
CMD ["uv", "run", "python", "main.py"]