import asyncio
import os

from aiohttp import BasicAuth, ClientSession

from intellinet_pdu_ctrl.api import IPU
from intellinet_pdu_ctrl.udp import IntellinetUDPClient


async def main() -> None:
    async with IPU(
        ClientSession(
            "http://192.168.194.23:50071",
            auth=BasicAuth(
                os.environ.get("PDU_USER", "admin"), os.environ.get("PDU_PASS", "admin")
            ),
        )
    ) as ipu:
        print(await ipu.get_system_configuration())
        print(await ipu.get_network_configuration())

    async with IntellinetUDPClient.connect(
        remote_addr=("192.168.194.20", 50072)
    ) as sock:
        for i in range(10000):
            print(f"[{i}] voltage: {await sock.get_voltage()}")


if __name__ == "__main__":
    asyncio.run(main())
