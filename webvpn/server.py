from typing import Optional
import asyncio
import logging

from fastapi import FastAPI, Response, Depends, Request
import sentry_sdk

from .gateway import TCPGateway, InvalidToken
from .logger import setup_logger

setup_logger(is_server=True)
logger = logging.getLogger(__name__)

sentry_sdk.init(
    "https://e8a30444dfe04196bc925f1c36fffce0@o246548.ingest.sentry.io/6464341",
    traces_sample_rate=0.5,
)

app = FastAPI()
gateway = TCPGateway()

asyncio.create_task(gateway.clean())


@app.get("/token")
async def get_token(username: str, host: str, port: int):
    token = await gateway.open_connection(host, port, username)
    logger.info(f"new connection: {username}:{token} -> {host}:{port}")

    if token:
        return {
            "code": 0,
            "data": {"token": token},
        }
    else:
        return {
            "code": 1000,
            "message": "Connection refused (open_connection)",
        }


@app.get("/keep-alive")
async def keep_alive(token: str):
    try:
        if await gateway.keep_alive(token):
            logger.info(f"keep-alive: {gateway.get_username(token)}:{token}")
            return {"code": 0}
        else:
            return {"code": 2000, "message": "Connection closed (keep_alive)"}
    except InvalidToken:
        return Response(status_code=400)


@app.get(
    "/pull",
    response_class=Response,
    responses={
        200: {"content": {"application/octet-stream": {}}}
    },
)
async def pull(token: str, n: int = 1024):
    future = gateway.pull(token, n)

    data = b""
    try:
        data = await asyncio.wait_for(future, timeout=2)
    except asyncio.TimeoutError:
        ...
    except InvalidToken:
        return Response(status_code=400)

    if data is None:
        return Response(status_code=503)    # Connection closed

    if len(data) > 0:
        logger.info(f"pull {len(data)} bytes: {gateway.get_username(token)}:{token}")
    return Response(data, media_type="application/octet-stream")


async def parse_body(request: Request):
    return await request.body()


@app.post("/push")
async def push(token: str, data: bytes = Depends(parse_body)):
    try:
        if await gateway.push(token, data):
            logger.info(f"push {len(data)} bytes: {gateway.get_username(token)}:{token}")
            return {"code": 0}
        else:
            return {"code": 2000, "message": "Connection closed (push)"}
    except InvalidToken:
        return Response(status_code=400)
