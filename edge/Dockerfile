FROM nvcr.io/nvidia/pytorch:25.10-py3


# Avoid Python buffering, .pyc files and pip cache.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    ULTRALYTICS_SETTINGS_DIR=/tmp/ultralytics


WORKDIR /opt/poultry-edge


# Runtime libraries required by OpenCV/Ultralytics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*


# Copy only the package definition first to improve Docker layer caching.
COPY pyproject.toml ./


# Install the Python dependencies without replacing the PyTorch/CUDA
# versions already provided by the NVIDIA base image.
RUN python -m pip install --upgrade pip \
    && python -m pip install \
        "mlflow>=3.0,<4.0" \
        "PyYAML>=6.0,<7.0" \
        "ultralytics>=8.3,<9.0"


# Copy and install the Edge application.
COPY src ./src

RUN python -m pip install --no-deps .


# Create the container paths referenced by edge.yaml.
RUN mkdir -p \
    /app/data/images \
    /app/data/outputs \
    /app/models \
    /opt/poultry-edge/config


# Run the command defined in [project.scripts] in pyproject.toml.
CMD ["poultry-edge"]