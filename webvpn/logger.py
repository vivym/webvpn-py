import logging
from pathlib import Path


def setup_logger(verbose: bool = False, is_server: bool = False):
    logger = logging.getLogger("webvpn")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    config_dir = Path.home() / ".config" / "webvpn-py"
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
    log_filename = "server.log" if is_server else "client.log"
    ch = logging.FileHandler(config_dir / log_filename)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
