from abc import ABCMeta, abstractmethod
from typing import Optional, Dict
import uuid
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


class InvalidToken(Exception):
    ...


class ConnectionClosedError(Exception):
    ...


class Connection(metaclass=ABCMeta):
    def __init__(self, closed: bool = False):
        self.closed = closed
        self.created_at = time.time()
        self.updated_at = time.time()

    @abstractmethod
    async def push(self, data: bytes):
        ...

    @abstractmethod
    async def pull(self, n: int) -> bytes:
        ...

    def update(self):
        self.updated_at = time.time()

    async def keep_alive(self) -> bool:
        self.update()
        return not self.closed

    @abstractmethod
    async def close(self):
        ...


class Gateway(metaclass=ABCMeta):
    def __init__(self, expire_time: float = -1):
        self.expire_time = expire_time

        self.connections: Dict[str, Connection] = {}

    @abstractmethod
    def open_connection(self, conn) -> Optional[str]:
        token = str(uuid.uuid4())
        self.connections[token] = conn
        return token

    async def push(self, token: str, data: bytes) -> bool:
        if token not in self.connections:
            raise InvalidToken()

        conn = self.connections[token]
        try:
            await conn.push(data)
        except ConnectionClosedError:
            await self.close(token)
            return False

        return True

    async def pull(self, token: str, n: int = 1024) -> Optional[bytes]:
        if token not in self.connections:
            raise InvalidToken()

        conn = self.connections[token]
        try:
            return await conn.pull(n)
        except ConnectionClosedError:
            await self.close(token)
            return None

    async def keep_alive(self, token: str):
        if token not in self.connections:
            raise InvalidToken()

        conn = self.connections[token]
        if not await conn.keep_alive():
            await self.close(token)
            return False
        else:
            return True

    async def close(self, token: str):
        if token in self.connections:
            await self.connections[token].close()
            del self.connections[token]

    async def clean(self):
        if self.expire_time <= 0:
            return

        while True:
            await asyncio.sleep(self.expire_time)

            try:
                now = time.time()
                logger.info("Clean expired connections.")
                for token, conn in list(self.connections.items()):
                    if now - conn.updated_at > self.expire_time:
                        logger.info(f"Connection {token} expired")

                        await self.close(token)
            except Exception as e:
                print("Clean Error:", e)
