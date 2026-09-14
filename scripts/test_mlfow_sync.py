from pathlib import Path

from poultry_edge.config import ModelConfig
from poultry_edge.model_loader import synchronize_model


# Define the model expected by this farm and the local directory
# where synchronized model versions are stored.
model_config = ModelConfig(
    registered_name="egg_detector",
    alias="farm_01_production",
    local_root_directory=Path("../models_mock"),
)

# Synchronize the model assigned to the farm-specific production alias.
# If MLflow is temporarily unavailable, allow the previously synchronized
# local model to be used as a fallback.
local_model = synchronize_model(
    model_config=model_config,
    tracking_uri="http://127.0.0.1:5000",
    registry_uri="http://127.0.0.1:5000",
    allow_local_fallback=True,
)

# Display the metadata of the model version available locally
# after the synchronization process.
print()
print("MODEL SYNCHRONIZED")
print("------------------")
print(f"Name: {local_model.registered_name}")
print(f"Version: {local_model.version}")
print(f"Alias: {local_model.alias}")
print(f"Path: {local_model.model_path}")
print(f"Synchronized at: {local_model.synchronized_at}")