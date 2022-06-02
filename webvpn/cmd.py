import asyncio
import logging
from pathlib import Path

import typer
import sentry_sdk
from aiorun import run

from .client import Client
from .config import settings, save_settings
from .gateway import WebVPNGateway
from .login import buaa_webvpn_login
from .logger import setup_logger

app = typer.Typer()


@app.command()
def login(
    username: str,
    password: str = typer.Option(..., prompt=True, hide_input=True)
):
    settings.USERNAME = username
    settings.PASSWORD = password
    save_settings()

    asyncio.run(buaa_webvpn_login(username, password))


@app.command()
def forward(
    host: str = settings.HOST,
    port: int = settings.PORT,
    rhost: str = settings.RHOST,
    rport: int = settings.RPORT,
):
    if not settings.USERNAME or not settings.PASSWORD:
        typer.echo(
            "Please login first by `webvpn login`"
        )
        return

    client = Client(
        host=host,
        port=port,
        rhost=rhost,
        rport=rport,
        username=settings.USERNAME,
        password=settings.PASSWORD,
        gateway=WebVPNGateway()
    )
    run(client.run(), stop_on_unhandled_errors=True)


@app.command()
def serve():
    logger = logging.getLogger(__name__)
    logger.info("Not implemented yet.")


@app.callback()
def main(verbose: bool = False):
    sentry_sdk.init(
        "https://6e41d074f65e4d5c85ac42611a08fe94@o246548.ingest.sentry.io/6464187",
        traces_sample_rate=0.5
    )
    setup_logger(verbose)


if __name__ == "__main__":
    app()
