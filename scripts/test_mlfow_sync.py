from pathlib import Path

from poultry_edge.config import ModelConfig
from poultry_edge.model_loader import synchronize_model


model_config = ModelConfig(
    registered_name="egg_counter_farm_01",
    alias="production",
    local_root_directory=Path("../models_mock"),
)

local_model = synchronize_model(
    model_config=model_config,
    tracking_uri="http://127.0.0.1:5000",
    registry_uri="http://127.0.0.1:5000",
    allow_local_fallback=True,
)

print()
print("MODEL SYNCHRONIZED")
print("------------------")
print(f"Name: {local_model.registered_name}")
print(f"Version: {local_model.version}")
print(f"Alias: {local_model.alias}")
print(f"Path: {local_model.model_path}")
print(f"Synchronized at: {local_model.synchronized_at}")