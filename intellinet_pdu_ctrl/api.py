from enum import Enum
from types import TracebackType
from typing import Any, ClassVar, Type

import aiohttp
from lxml import etree as et

from intellinet_pdu_ctrl.types import (
    AllOutletsConfig,
    OutletCommand,
    PDUStatus,
    ThresholdsConfig,
)


class PDUEndpoints(Enum):
    status = "/status.xml"
    pdu = "/info_PDU.htm"
    system = "/info_system.htm"
    outlet = "/control_outlet.htm"
    config_pdu = "/config_PDU.htm"
    thresholds = "/config_threshold.htm"
    users = "/config_user.htm"
    network = "/config_network.htm"


class IPU:
    DEFAULT_CREDS: ClassVar[aiohttp.BasicAuth] = aiohttp.BasicAuth("admin", "admin")

    def __init__(
        self,
        url: str,
        auth: aiohttp.BasicAuth | None = None,
    ):
        self.url = url
        self.auth = auth or self.DEFAULT_CREDS
        self.session = aiohttp.ClientSession(base_url=self.url, auth=self.auth)

    async def __aenter__(self) -> "IPU":
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.session:
            await self.session.close()

    async def _get_request(
        self, page: PDUEndpoints, params: dict[str, str] | None = None
    ) -> et._Element:
        async with self.session.get(page.value, params=params) as resp:
            raw_resp_content = await resp.text()

        parser = et.HTML if "html" in raw_resp_content.lower() else et.XML
        return parser(raw_resp_content)  # type: ignore

    async def _post_request(
        self, page: PDUEndpoints, data: dict[str, Any]
    ) -> aiohttp.ClientResponse:
        return await self.session.post(
            page.value,
            data=data,
            headers={"Content-type": "application/x-www-form-urlencoded"},
        )

    async def get_status(self) -> PDUStatus:
        e = await self._get_request(PDUEndpoints.status)
        return PDUStatus.from_xml(e)

    async def set_outlets_config(self, outlet_configs: AllOutletsConfig) -> None:
        settings = dict[str, Any]()
        for o, v in enumerate(outlet_configs.outlets):
            settings[f"otlt{o}"] = v.name
            settings[f"ofdly{o}"] = v.turn_off_delay
            settings[f"ondly{o}"] = v.turn_on_delay

        await self._post_request(PDUEndpoints.config_pdu, data=settings)

    async def get_outlets_config(self) -> AllOutletsConfig:
        etree = await self._get_request(PDUEndpoints.config_pdu)

        return AllOutletsConfig.from_xml(etree)

    async def get_thresholds_config(self) -> ThresholdsConfig:
        etree = await self._get_request(PDUEndpoints.thresholds)
        return ThresholdsConfig.from_xml(etree)

    async def set_thresholds_config(self, threshold_config: ThresholdsConfig) -> None:
        await self._post_request(
            PDUEndpoints.thresholds, data=threshold_config.to_dict()
        )

    async def set_outlets(self, state: OutletCommand, *list_of_outlet_ids: int) -> None:
        outlet_states = {f"outlet{k}": str(1) for k in list_of_outlet_ids}
        outlet_states["op"] = str(state.value)
        outlet_states["submit"] = "Anwenden"

        await self._get_request(PDUEndpoints.outlet, params=outlet_states)
