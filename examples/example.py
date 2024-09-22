import asyncio
import os

from aiohttp import BasicAuth

from intellinet_pdu_ctrl.api import IPU
from intellinet_pdu_ctrl.types import OutletCommand


async def main() -> None:
    async with IPU(
        "http://192.168.194.23:50071",
        auth=BasicAuth(
            os.environ.get("PDU_USER", "admin"), os.environ.get("PDU_PASS", "admin")
        ),
    ) as ipu:
        await ipu.set_outlets(OutletCommand.ON, 0)


if __name__ == "__main__":
    asyncio.run(main())
