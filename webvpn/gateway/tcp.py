from typing import Optional
import asyncio
import time

from .gateway import Gateway, Connection, ConnectionClosedError


class TCPConnection(Connection):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        super().__init__(closed=False)

        self.reader = reader
        self.writer = writer

    async def push(self, data: bytes):
        self.update()
        if self.closed:
            raise ConnectionClosedError()
        self.writer.write(data)

    async def pull(self, n: int) -> bytes:
        self.update()
        if self.closed:
            raise ConnectionClosedError()

        data = await self.reader.read(n)
        if not data:
            self.closed = True
        return data

    async def close(self):
        self.closed = True
        if not self.writer.is_closing():
            await self.writer.drain()
            self.writer.close()
        await self.writer.wait_closed()


class TCPGateway(Gateway):
    async def open_connection(self, host: str, port: int) -> Optional[str]:
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=5)
        except ConnectionRefusedError:
            return None
        except asyncio.TimeoutError:
            return None

        conn = TCPConnection(reader, writer)
        return super().open_connection(conn)


if __name__ == "__main__":
    gateway = TCPGateway()
    asyncio.run(gateway.open_connection("localhost", 23311))
