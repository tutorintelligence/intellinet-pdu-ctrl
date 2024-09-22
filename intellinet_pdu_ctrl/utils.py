from typing import cast

from lxml import etree as et


def find_input_value_in_xml(et: et._Element, id: str) -> str:
    xpath = f"//*[@id='{id}']/@value | //*[@name='{id}']/@value"
    result = cast(list[str] | None, et.xpath(xpath))
    if not result:
        raise ValueError(f"Could not find value for id: {id}")
    return result[0]


def extract_text_from_child(e: et._Element, child_name: str) -> str:
    child = e.find(child_name)
    if child is None:
        raise ValueError(f"Could not find child: {child_name}")
    return str(child.text)
