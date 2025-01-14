from enum import Enum
from types import TracebackType
from typing import Any, ClassVar, Type

import aiohttp
from lxml import etree as et

from intellinet_pdu_ctrl.types import (
    AllOutletsConfig,
    NetworkConfiguration,
    OutletCommand,
    PDUStatus,
    SystemConfiguration,
    ThresholdsConfig,
    UserVerifyResult,
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
        session: aiohttp.ClientSession,
        auth: aiohttp.BasicAuth | None = None,
    ):
        self.session = session
        self.auth = auth

        assert (
            self.session.auth is not None or self.auth is not None
        ), "must have auth set"

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
        async with self.session.get(page.value, params=params, auth=self.auth) as resp:
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
            auth=self.auth,
        )

    async def get_status(self) -> PDUStatus:
        return PDUStatus.from_xml(await self._get_request(PDUEndpoints.status))

    async def set_outlets_config(self, outlet_configs: AllOutletsConfig) -> None:
        settings = dict[str, Any]()
        for o, v in enumerate(outlet_configs.outlets):
            settings[f"otlt{o}"] = v.name
            settings[f"ofdly{o}"] = v.turn_off_delay
            settings[f"ondly{o}"] = v.turn_on_delay

        await self._post_request(PDUEndpoints.config_pdu, data=settings)

    async def get_outlets_config(self) -> AllOutletsConfig:
        return AllOutletsConfig.from_xml(
            await self._get_request(PDUEndpoints.config_pdu)
        )

    async def get_thresholds_config(self) -> ThresholdsConfig:
        return ThresholdsConfig.from_xml(
            await self._get_request(PDUEndpoints.thresholds)
        )

    async def set_thresholds_config(self, threshold_config: ThresholdsConfig) -> None:
        await self._post_request(
            PDUEndpoints.thresholds, data=threshold_config.to_dict()
        )

    async def set_outlets(self, state: OutletCommand, *list_of_outlet_ids: int) -> None:
        outlet_states = {f"outlet{k}": str(1) for k in list_of_outlet_ids}
        outlet_states["op"] = str(state.value)
        outlet_states["submit"] = "Anwenden"

        await self._get_request(PDUEndpoints.outlet, params=outlet_states)

    async def set_credentials(self, new_credentials: aiohttp.BasicAuth) -> None:
        current_credentials = self.session.auth
        assert current_credentials is not None, "session must have auth set"

        await self._post_request(
            PDUEndpoints.users,
            data=dict(
                oldnm=current_credentials.login,
                oldpas=current_credentials.password,
                newnm=new_credentials.login,
                newpas=new_credentials.password,
                confirm=new_credentials.password,
            ),
        )

        status = await self.get_status()

        assert (
            status.user_verify_result == UserVerifyResult.CREDENTIALS_CHANGED
        ), f"Credentials were not changed {status.user_verify_result=}"

        self.session._default_auth = new_credentials

    async def get_network_configuration(self) -> NetworkConfiguration:
        return NetworkConfiguration.from_xml(
            await self._get_request(PDUEndpoints.network)
        )

    async def set_network_configuration(
        self, network_config: NetworkConfiguration
    ) -> None:
        await self._post_request(PDUEndpoints.network, data=network_config.to_dict())

    async def get_system_configuration(self) -> SystemConfiguration:
        return SystemConfiguration.from_xml(
            await self._get_request(PDUEndpoints.system)
        )

    async def set_system_configuration(
        self, system_config: SystemConfiguration
    ) -> None:
        await self._post_request(PDUEndpoints.system, data=system_config.to_dict())
