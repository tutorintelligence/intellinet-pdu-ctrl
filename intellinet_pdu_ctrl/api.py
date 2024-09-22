from dataclasses import asdict, dataclass
from enum import Enum
from typing import ClassVar, cast
from urllib.parse import urlunsplit

import requests
from lxml import etree as et
from typing_extensions import Self

from intellinet_pdu_ctrl.utils import extract_text_from_child, find_input_value_in_xml


@dataclass(frozen=True)
class ThresholdsConfig:
    warning_value_amps: float
    overload_value_amps: float
    warning_value_volts: int
    overload_value_volts: int
    warning_value_temp_under_celcius: int
    warning_value_temp_over_celcius: int
    warning_value_humidity_percent: int

    RAW_FIELD_NAMES: ClassVar[list[str]] = [
        "wrncur",
        "ovrcur",
        "wrnvol",
        "ovrvol",
        "wrntp1",
        "wrntp2",
        "wrnhum",
    ]

    @classmethod
    def from_xml(cls, e: et._Element) -> Self:
        return cls(
            warning_value_amps=float(find_input_value_in_xml(e, "wrncur")),
            overload_value_amps=float(find_input_value_in_xml(e, "ovrcur")),
            warning_value_volts=int(find_input_value_in_xml(e, "wrnvol")),
            overload_value_volts=int(find_input_value_in_xml(e, "ovrvol")),
            warning_value_temp_under_celcius=int(find_input_value_in_xml(e, "wrntp1")),
            warning_value_temp_over_celcius=int(find_input_value_in_xml(e, "wrntp2")),
            warning_value_humidity_percent=int(find_input_value_in_xml(e, "wrnhum")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "wrncur": str(self.warning_value_amps),
            "ovrcur": str(self.overload_value_amps),
            "wrnvol": str(self.warning_value_volts),
            "ovrvol": str(self.overload_value_volts),
            "wrntp1": str(self.warning_value_temp_under_celcius),
            "wrntp2": str(self.warning_value_temp_over_celcius),
            "wrnhum": str(self.warning_value_humidity_percent),
        }


@dataclass(frozen=True)
class IndividualOutletConfig:
    name: str
    turn_on_delay: int
    turn_off_delay: int


class OutletCommand(Enum):
    ON = 0
    OFF = 1
    POWER_CYCLE_OFF_ON = 2


@dataclass(frozen=True)
class AllOutletsConfig:
    outlet0: IndividualOutletConfig
    outlet1: IndividualOutletConfig
    outlet2: IndividualOutletConfig
    outlet3: IndividualOutletConfig
    outlet4: IndividualOutletConfig
    outlet5: IndividualOutletConfig
    outlet6: IndividualOutletConfig
    outlet7: IndividualOutletConfig

    @property
    def outlets(self) -> tuple[IndividualOutletConfig, ...]:
        return (
            self.outlet0,
            self.outlet1,
            self.outlet2,
            self.outlet3,
            self.outlet4,
            self.outlet5,
            self.outlet6,
            self.outlet7,
        )

    @classmethod
    def from_xml(cls, etree: et._Element) -> Self:
        # get the value of the value attribute in the input tag which is within a td tag
        xpath_input_field_values = ".//td/input/@value"
        # get every tr tag which has at least one td tag which has at least one input tag with a value attribute
        xpath_input_fields = ".//tr[td/input/@value]"

        config = {}
        for idx, outlet in enumerate(
            cast(list[et._Element], etree.xpath(xpath_input_fields))
        ):
            values = cast(list[str], outlet.xpath(xpath_input_field_values))
            config["outlet{}".format(idx)] = IndividualOutletConfig(
                name=values[0],
                turn_on_delay=int(values[1]),
                turn_off_delay=int(values[2]),
            )

        return cls(**config)


class OutletState(Enum):
    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class PDUStatus:
    current_amps: float
    degree_celcius: int
    humidity_percent: int
    status: str  # todo: make this an enum
    outlet_states: tuple[OutletState, ...]

    @classmethod
    def from_xml(cls, e: et._Element) -> Self:
        return cls(
            current_amps=float(extract_text_from_child(e, "cur0")),
            degree_celcius=int(extract_text_from_child(e, "tempCBan")),
            humidity_percent=int(extract_text_from_child(e, "humBan")),
            status=extract_text_from_child(e, "stat0"),
            outlet_states=tuple(
                OutletState(extract_text_from_child(e, "outletStat{}".format(i)))
                for i in range(0, 8)
            ),
        )


class PDUEndpoints(Enum):
    status = "status.xml"
    pdu = "info_PDU.htm"
    system = "info_system.htm"
    outlet = "control_outlet.htm"
    config_pdu = "config_PDU.htm"
    thresholds = "config_threshold.htm"
    users = "config_user.htm"
    network = "config_network.htm"


class IPU:

    """This class is represents a api wrapper for the Intellinet IP smart PDU API [163682].
        It provides all the functionality of the web interface it is based on.

    Class-Attributes:
        DEFAULT_CREDS (:obj:`tuple` of :obj:`str`): default username/password of pdu
        DEFAULT_ENDCODING (str): default encoding of pdu
        DEFAULT_SCHEMA (str): default schema of pdu
    """

    DEFAULT_SCHEMA: ClassVar[str] = "http"
    DEFAULT_ENDCODING: ClassVar[str] = "gb2312"
    DEFAULT_CREDS: ClassVar[tuple[str, str]] = ("tutor", "kalman")

    def __init__(
        self,
        host: str,
        auth: tuple[str, str] | None = None,
        charset: str | None = None,
        schema: str | None = None,
    ):
        """
        Args:
            host (str): IP addr of pdu/ipu
            auth (:obj:`tuple` of :obj:`str`, optional): (username, password). Defaults to DEFAULT_CREDS
            charset (str): charset used by the pdu. Defaults to DEFAULT_ENDCODING
            schema (str, optional): 'http' or 'https'. Defaults to DEFAULT_SCHEMA
        """
        self.host = host
        self.schema = schema or self.DEFAULT_SCHEMA
        self.charset = charset or self.DEFAULT_ENDCODING
        self.credentials = auth or self.DEFAULT_CREDS
        self.auth = requests.auth.HTTPBasicAuth(*self.credentials)

    def _get_request(
        self, page: PDUEndpoints, params: dict[str, str] | None = None
    ) -> et._Element:
        """Internal wrapper around requests get method and the pdus available endpoints.

        Args:
            page (str): endpoint / page that is requested
            params (dict, optional): get parametrs to be send along with request. Used for updating settings.

        Returns:
            :obj:`requests.models.Response`: The raw object returned by the requests lib.
        """
        url = urlunsplit([self.schema, self.host, page.value, None, None])
        resp = requests.get(url, auth=self.auth, params=params)

        raw_resp_content = resp.content.decode(self.charset)

        parser = et.HTML if "html" in raw_resp_content.lower() else et.XML

        return parser(raw_resp_content)  # type: ignore

    def _post_request(
        self, page: PDUEndpoints, data: dict[str, str]
    ) -> requests.Response:
        """Internal wrapper around requests post method and the pdus available endpoints.

        Args:
            page (str): See: self._get_request()
            data (dict): post data
        """
        url = urlunsplit([self.schema, self.host, page.value, None, None])

        headers = {"Content-type": "application/x-www-form-urlencoded"}
        return requests.post(url, auth=self.auth, data=data, headers=headers)

    # public api

    def get_status(self) -> PDUStatus:
        """gives you basic status/health of the device.
            Values: deg. C, outlet states [on/off], status [read: are there warnings?], humidity in perc, amps.
        Returns:
            dict: containing the aforementioned stats.
                  e.g. {'degree_celcius': '26', 'outlet_states': ['on', 'on', 'off', 'on', 'on', 'on', 'on', 'on'],
                        'stat': 'normal', 'humidity_percent': '27', 'current_amperes': '0.5'}
        """
        e = self._get_request(PDUEndpoints.status)
        return PDUStatus.from_xml(e)

    def set_config_pdu(self, outlet_configs: AllOutletsConfig) -> None:
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

        self._post_request(PDUEndpoints.config_pdu, data=settings)

    def get_config_pdu(self) -> AllOutletsConfig:
        etree = self._get_request(PDUEndpoints.config_pdu)

        return AllOutletsConfig.from_xml(etree)

    def get_config_threshold(self) -> ThresholdsConfig:
        etree = self._get_request(PDUEndpoints.thresholds)
        return ThresholdsConfig.from_xml(etree)

    def set_config_threshold(self, threshold_config: ThresholdsConfig) -> None:
        self._post_request(PDUEndpoints.thresholds, data=threshold_config.to_dict())

    def set_outlets_state(self, state: OutletCommand, *list_of_outlet_ids: int) -> None:
        outlet_states = {"outlet{}".format(k): str(1) for k in list_of_outlet_ids}
        outlet_states["op"] = str(state.value)
        outlet_states["submit"] = "Anwenden"
        self._get_request(PDUEndpoints.outlet, params=outlet_states)
