from dataclasses import asdict
from enum import Enum
from types import TracebackType
from typing import ClassVar, Type

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

    """This class is represents a api wrapper for the Intellinet IP smart PDU API [163682].
        It provides all the functionality of the web interface it is based on.

    Class-Attributes:
        DEFAULT_CREDS (:obj:`tuple` of :obj:`str`): default username/password of pdu
        DEFAULT_ENDCODING (str): default encoding of pdu
        DEFAULT_SCHEMA (str): default schema of pdu
    """

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
        """Internal wrapper around aiohttp get method and the pdus available endpoints.

        Args:
            page (str): endpoint / page that is requested
            params (dict, optional): get parameters to be sent along with request. Used for updating settings.

        Returns:
            :obj:`lxml.etree._Element`: The parsed XML/HTML element.
        """
        async with self.session.get(page.value, params=params) as resp:
            raw_resp_content = await resp.text()

        parser = et.HTML if "html" in raw_resp_content.lower() else et.XML
        return parser(raw_resp_content)  # type: ignore

    async def _post_request(
        self, page: PDUEndpoints, data: dict[str, str]
    ) -> aiohttp.ClientResponse:
        """Internal wrapper around aiohttp post method and the pdus available endpoints.

        Args:
            page (str): See: self._get_request()
            data (dict): post data
        """
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        return await self.session.post(page.value, data=data, headers=headers)

    async def get_status(self) -> PDUStatus:
        """gives you basic status/health of the device.
            Values: deg. C, outlet states [on/off], status [read: are there warnings?], humidity in perc, amps.
        Returns:
            dict: containing the aforementioned stats.
                  e.g. {'degree_celcius': '26', 'outlet_states': ['on', 'on', 'off', 'on', 'on', 'on', 'on', 'on'],
                        'stat': 'normal', 'humidity_percent': '27', 'current_amperes': '0.5'}
        """
        e = await self._get_request(PDUEndpoints.status)
        return PDUStatus.from_xml(e)

    async def set_config_pdu(self, outlet_configs: AllOutletsConfig) -> None:
        """Setter for self.pdu_config()

        Args:
            outlet_configs (dict): dict that is formatted like the output of self._get_config_pdu()
        """
        translation_table = {
            "turn_on_delay": "ondly",
            "turn_off_delay": "ofdly",
            "name": "otlt",
        }

        settings = {}
        for otl_nr, v in enumerate(outlet_configs.outlets):
            for _k, _v in asdict(v).items():
                new_key = f"{translation_table[_k]}{otl_nr}"
                settings[new_key] = _v

        await self._post_request(PDUEndpoints.config_pdu, data=settings)

    async def get_config_pdu(self) -> AllOutletsConfig:
        etree = await self._get_request(PDUEndpoints.config_pdu)

        return AllOutletsConfig.from_xml(etree)

    async def get_config_threshold(self) -> ThresholdsConfig:
        etree = await self._get_request(PDUEndpoints.thresholds)
        return ThresholdsConfig.from_xml(etree)

    async def set_config_threshold(self, threshold_config: ThresholdsConfig) -> None:
        await self._post_request(
            PDUEndpoints.thresholds, data=threshold_config.to_dict()
        )

    async def set_outlets_state(
        self, state: OutletCommand, *list_of_outlet_ids: int
    ) -> None:
        outlet_states = {"outlet{}".format(k): str(1) for k in list_of_outlet_ids}
        outlet_states["op"] = str(state.value)
        outlet_states["submit"] = "Anwenden"
        await self._get_request(PDUEndpoints.outlet, params=outlet_states)
