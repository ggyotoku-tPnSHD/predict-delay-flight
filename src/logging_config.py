import logging
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"

def setup_logging(name="pipeline"):
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / f"{name}.log"),
            logging.StreamHandler(),
        ]
    )
    return logging.getLogger(name)
