import logging
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LOGIN_URL_1 = r"https://sso.buaa.edu.cn/login?service=https%3A%2F%2Fd.buaa.edu.cn%2Flogin%3Fcas_login%3Dtrue"
LOGIN_URL_2 = r"https://sso.buaa.edu.cn/login"


def get_cookie_jar_path() -> Path:
    config_dir = Path.home() / ".config" / "webvpn-py"
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
    return config_dir / "buaa-webvpn.cookie"


async def buaa_webvpn_login(username: str, password: str) -> bool:
    timeout = aiohttp.ClientTimeout(total=5)
    cookie_jar = aiohttp.CookieJar()

    async with aiohttp.ClientSession(timeout=timeout, cookie_jar=cookie_jar) as session:
        # Get `execution`
        async with session.get(LOGIN_URL_1) as rsp:
            soup = BeautifulSoup(await rsp.text(), "html.parser")
            tag = soup.find("input", {"name": "execution"})
            assert tag is not None
            execution = tag["value"]

        data = {
            "username": username,
            "password": password,
            "submit": "登录",
            "type": "username_password",
            "execution": execution,
            "_eventId": "submit",
        }
        async with session.post(LOGIN_URL_2, data=data) as rsp:
            ok = rsp.status == 200

        if ok:
            cookie_jar.save(get_cookie_jar_path())
            logger.info(f"Successfully logged in: {username}")
        else:
            logger.error(f"Failed to login: {username}")

        return ok
