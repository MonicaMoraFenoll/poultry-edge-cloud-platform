FROM nvcr.io/nvidia/pytorch:25.10-py3

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-pro.txt .
COPY pyproject.toml .
COPY src ./src

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -r requirements.txt && \
    python3 -m pip install .

CMD ["poultry-edge"]