from typing import Optional
from dataclasses import dataclass
import asyncio
import logging

from .gateway import WebVPNGateway

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    token: str
    closed: bool = False


class Client:
    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 23388,
        rhost: str = "10.251.0.23",
        rport: int = 22,
        username: str,
        password: str,
        gateway: WebVPNGateway,
    ):
        self.host = host
        self.port = port
        self.rhost = rhost
        self.rport = rport

        self.username = username
        self.password = password

        self.gateway = gateway
        self.tcp_server: Optional[asyncio.Server] = None

    async def pull(self, conn: Connection):
        writer, token = conn.writer, conn.token

        while not conn.closed:
            data = await self.gateway.pull(token, 1000 * 1024)
            if data:
                writer.write(data)
            elif data is None:
                conn.closed = True

        await writer.drain()

        writer.close()
        await writer.wait_closed()

        logger.debug("pull done")

    async def push(self, conn: Connection):
        reader, token = conn.reader, conn.token

        while not conn.closed:
            data = await reader.read(1000 * 1024)
            if not data:
                conn.closed = True
                break
            conn.closed = not await self.gateway.push(token, data)

        logger.debug("push done")

    async def conn_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        logger.info(f"Connection established: {addr!r}")

        try:
            token = await self.gateway.open_connection(
                self.rhost, self.rport, self.username, self.password
            )
        except Exception as e:
            logger.error(f"Failed to open connection: {e}")
            writer.close()
            await writer.wait_closed()
            return

        conn = Connection(reader, writer, token)

        await asyncio.gather(
            self.pull(conn),
            self.push(conn),
        )

        await self.gateway.close(token)

        logger.info(f"Connection closed: {addr!r}")

    async def run(self):
        self.tcp_server = await asyncio.start_server(
            self.conn_handler, self.host, self.port,
        )
        logger.info(f"Listening on {self.host}:{self.port} -> {self.rhost}:{self.rport}")

        async with self.tcp_server:
            await self.tcp_server.serve_forever()
