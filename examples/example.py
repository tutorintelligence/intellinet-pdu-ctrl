import asyncio
import os

from aiohttp import BasicAuth

from intellinet_pdu_ctrl.api import IPU


async def main() -> None:
    async with IPU(
        "http://192.168.194.23:50071",
        auth=BasicAuth(
            os.environ.get("PDU_USER", "admin"), os.environ.get("PDU_PASS", "admin")
        ),
    ) as ipu:
        print(await ipu.get_status())


if __name__ == "__main__":
    asyncio.run(main())
