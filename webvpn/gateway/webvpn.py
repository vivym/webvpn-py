from typing import Optional
import asyncio
import logging

import aiohttp

from webvpn.login import buaa_webvpn_login, get_cookie_jar_path
from .gateway import Gateway, Connection, ConnectionClosedError

logger = logging.getLogger(__name__)

TEST_MODE = False

if TEST_MODE:
    TOKEN_URL = "http://127.0.0.1:8000/token"
    PUSH_URL = "http://127.0.0.1:8000/push"
    PULL_URL = "http://127.0.0.1:8000/pull"
    KEEP_ALIVE_URL = "http://127.0.0.1:8000/keep-alive"
else:
    BASE_URL = "https://d.buaa.edu.cn"
    TOKEN_URL = BASE_URL + "/http-23381/77726476706e69737468656265737421a1a70fce72612600305add/token"
    PUSH_URL = BASE_URL + "/http-23381/77726476706e69737468656265737421a1a70fce72612600305add/push"
    PULL_URL = BASE_URL + "/http-23381/77726476706e69737468656265737421a1a70fce72612600305add/pull"
    KEEP_ALIVE_URL = BASE_URL + "/http-23381/77726476706e69737468656265737421a1a70fce72612600305add/keep-alive"

RETRY_DELAY = [10, 20, 30, 100, 200, 1000, 2000, 3000, 4000, 5000]    # ms


class WebVPNConnection(Connection):
    def __init__(self, username: str, password: str, host: str, port: str):
        super().__init__(closed=False)

        self.username = username
        self.password = password
        self.host = host
        self.port = port

        timeout = aiohttp.ClientTimeout(total=0)
        self.cookie_jar = aiohttp.CookieJar()
        self.cookie_jar.load(get_cookie_jar_path())
        self.session = aiohttp.ClientSession(timeout=timeout, cookie_jar=self.cookie_jar)
        self.timeout = aiohttp.ClientTimeout(total=5)

        self.token: Optional[str] = None

    async def login(self) -> bool:
        if not await buaa_webvpn_login(self.username, self.password):
            return False

        self.cookie_jar.load(get_cookie_jar_path())
        logger.debug("Cookie loaded.")

        return True

    async def get_token(self):
        params = {
            "username": self.username,
            "host": self.host,
            "port": self.port,
        }

        retry_count = 0
        while retry_count < 5:
            try:
                async with self.session.get(
                    TOKEN_URL, params=params, timeout=self.timeout, allow_redirects=False
                ) as rsp:
                    if rsp.status == 302:   # redirect
                        await self.login()
                    elif rsp.status == 200:
                        data = await rsp.json()
                        if data["code"] == 0:
                            self.token = data["data"]["token"]
                            logger.info(f"Token: {self.token}")
                            return
                        else:
                            logger.error(data["message"])
                            break
            except asyncio.TimeoutError:
                ...

            await asyncio.sleep(1)
            retry_count += 1

        raise RuntimeError("Failed to get token")

    async def push(self, data: bytes):
        self.update()

        if self.closed:
            raise ConnectionClosedError()

        params = {"token": self.token}

        retry_count = 0
        done = False
        while retry_count < 10:
            try:
                async with self.session.post(
                    PUSH_URL, params=params, data=data,
                    timeout=self.timeout, allow_redirects=False
                ) as rsp:
                    if rsp.status == 302:   # redirect
                        logger.info("Redirect to login.")
                        await self.login()
                    elif rsp.status == 200:
                        data = await rsp.json()
                        if data["code"] == 0:
                            logger.debug(f"Push successfully. {len(data)} bytes.")
                            done = True
                        break
            except asyncio.TimeoutError:
                ...

            await asyncio.sleep(RETRY_DELAY[retry_count] / 1000)
            retry_count += 1

        if not done:
            self.closed = True
            logger.info("Connection closed. (push)")
            raise ConnectionClosedError()

    async def pull(self, n: int) -> bytes:
        self.update()

        if self.closed:
            raise ConnectionClosedError()

        params = {"token": self.token, "n": n}

        retry_count = 0
        done = False
        while retry_count < 10:
            try:
                async with self.session.get(
                    PULL_URL, params=params, timeout=self.timeout, allow_redirects=False
                ) as rsp:
                    if rsp.status == 302:   # redirect
                        logger.info("Redirect to login.")
                        await self.login()
                    elif rsp.status == 200:
                        data = await rsp.read()
                        done = True
                        logger.debug(f"Pull successfully. {len(data)} bytes.")
                        break
                    elif rsp.status == 400:
                        logger.error("invalid token.")
                        break
                    elif rsp.status == 503:
                        logger.error("Connection closed. (503)")
                        break
            except asyncio.TimeoutError:
                ...

            await asyncio.sleep(RETRY_DELAY[retry_count] / 1000)
            retry_count += 1

        if not done:
            self.closed = True
            logger.info("Connection closed. (pull)")
            raise ConnectionClosedError()

        return data

    async def keep_alive(self) -> bool:
        if self.closed:
            return False

        params = {"token": self.token}

        retry_count = 0
        while retry_count < 5:
            try:
                async with self.session.get(
                    KEEP_ALIVE_URL, params=params, timeout=self.timeout, allow_redirects=False
                ) as rsp:
                    if rsp.status == 302:   # redirect
                        logger.info("Redirect to login.")
                        await self.login()
                    elif rsp.status == 200:
                        data = await rsp.json()
                        logger.debug("Keep alive successfully.")
                        if data["code"] != 0:
                            logger.info("Failed to keep alive.")
                            self.closed = True
                        break
            except asyncio.TimeoutError:
                ...

            await asyncio.sleep(1)
            retry_count += 1

        return super().keep_alive()

    async def close(self):
        self.closed = True
        await self.session.close()


class WebVPNGateway(Gateway):
    async def open_connection(
        self, host: str, port: int, username: str, password: str
    ) -> Optional[str]:
        conn = WebVPNConnection(username, password, host, port)

        if not TEST_MODE:
            if not await conn.login():
                await conn.close()
                raise RuntimeError("Failed to login")
        await conn.get_token()

        return super().open_connection(conn)
