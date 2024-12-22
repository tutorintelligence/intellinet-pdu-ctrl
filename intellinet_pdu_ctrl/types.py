from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, cast

from lxml import etree as et
from typing_extensions import Self

from intellinet_pdu_ctrl.utils import extract_text_from_child, find_input_value_in_xml


class OutletCommand(Enum):
    ON = 0
    OFF = 1
    POWER_CYCLE_OFF_ON = 2


class OutletState(Enum):
    ON = "on"
    OFF = "off"


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


class UserVerifyResult(Enum):
    NA = 0
    CREDENTIALS_CHANGED = 1
    CREDENTIALS_ERRORED = 2


@dataclass(frozen=True)
class PDUStatus:
    current_amps: float
    degree_celcius: int
    humidity_percent: int
    status: str  # todo: make this an enum
    outlet_states: tuple[OutletState, ...]
    user_verify_result: UserVerifyResult

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
            user_verify_result=UserVerifyResult(
                int(extract_text_from_child(e, "userVerifyRes"))
            ),
        )


@dataclass(frozen=True)
class NetworkConfiguration:
    hostname: str
    ip_address: str
    subnet_mask: str
    gateway: str
    enable_dhcp: bool
    primary_dns_ip: str
    secondary_dns_ip: str

    @classmethod
    def from_xml(cls, e: et._Element) -> Self:
        dhcp_checkbox = cast(list[et._Element], e.xpath("//*[@id='dhcp']"))[0]
        enable_dhcp = "checked" in dhcp_checkbox.attrib

        return cls(
            hostname=find_input_value_in_xml(e, "host"),
            ip_address=find_input_value_in_xml(e, "ip"),
            subnet_mask=find_input_value_in_xml(e, "mask"),
            gateway=find_input_value_in_xml(e, "gate"),
            enable_dhcp=enable_dhcp,
            primary_dns_ip=find_input_value_in_xml(e, "dns1"),
            secondary_dns_ip=find_input_value_in_xml(e, "dns2"),
        )

    def to_dict(self) -> dict[str, str]:
        data = {
            "host": self.hostname,
            "ip": self.ip_address,
            "mask": self.subnet_mask,
            "gate": self.gateway,
            "dns1": self.primary_dns_ip,
            "dns2": self.secondary_dns_ip,
        }

        if self.enable_dhcp:
            data["dhcp"] = "on"

        return data


@dataclass(frozen=True)
class SystemConfiguration:
    product_model: str
    firmware_version: str
    mac_address: str
    system_name: str
    administrator: str
    system_location: str

    @classmethod
    def from_xml(cls, e: et._Element) -> Self:
        product_model = cast(
            list[str],
            e.xpath(
                "//td[strong[normalize-space(text())='Product model']]/following-sibling::td[1]/text()"
            ),
        )[0].strip()
        firmware_version = cast(
            list[str],
            e.xpath(
                "//td[strong[normalize-space(text())='Firmware version']]/following-sibling::td[1]/text()"
            ),
        )[0].strip()

        return cls(
            product_model=product_model,
            firmware_version=firmware_version,
            mac_address=find_input_value_in_xml(e, "mac"),
            system_name=find_input_value_in_xml(e, "sysnm"),
            administrator=find_input_value_in_xml(e, "admin"),
            system_location=find_input_value_in_xml(e, "loc"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "mac": self.mac_address,
            "sysnm": self.system_name,
            "admin": self.administrator,
            "loc": self.system_location,
        }
