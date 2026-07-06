"""Enable `python -m genimg …` (used as a subprocess fallback by `genimg draw`)."""
from .cli import app

if __name__ == "__main__":
  app()
