import os

# Text-only meals go to the light model, photos go to the vision-capable model.
# Override per environment without code changes (e.g. to compare accuracy/cost).
MODEL_TEXT = os.getenv("MODEL_TEXT", "claude-haiku-5-5")
MODEL_VISION = os.getenv("MODEL_VISION", "claude-sonnet-5-5")

# Reasoning depth per route. Text splitting is easy -> low. Estimating portions
# from a photo benefits from a bit more thought -> medium.
EFFORT_TEXT = os.getenv("EFFORT_TEXT", "low")
EFFORT_VISION = os.getenv("EFFORT_VISION", "medium")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

# pg_trgm similarity needed to accept a master-table match.
MASTER_SIM_THRESHOLD = float(os.getenv("MASTER_SIM_THRESHOLD", "0.8"))
# When the model names a chain but nothing matches inside it, retry across all
# foods with a stricter bar (the model may have mislabeled the chain).
MASTER_SIM_THRESHOLD_NO_CHAIN = float(os.getenv("MASTER_SIM_THRESHOLD_NO_CHAIN", "0.9"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
MAX_IMAGE_EDGE = int(os.getenv("MAX_IMAGE_EDGE", "1280"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
