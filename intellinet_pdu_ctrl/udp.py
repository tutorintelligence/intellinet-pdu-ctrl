import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from typing_extensions import Self


class _SocketProtocol(asyncio.DatagramProtocol):
    def __init__(self, packets_queue_max_size: int) -> None:
        self._error: Exception | None = None
        self._packets = asyncio.Queue[tuple[bytes, tuple[str, int]] | None](
            packets_queue_max_size
        )

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        pass

    def connection_lost(self, exc: Exception | None) -> None:
        self._packets.put_nowait(None)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._packets.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        self._error = exc
        self._packets.put_nowait(None)

    async def recvfrom(self) -> tuple[bytes, tuple[str, int]] | None:
        return await self._packets.get()

    def raise_if_error(self) -> None:
        if self._error is None:
            return

        error = self._error
        self._error = None

        raise error


def ones_comp_add(a: int, b: int) -> int:
    c = a + b
    return (c & 0xFF) + (c >> 16)


def with_checksum(msg: bytes) -> bytes:
    checksum = 0
    for i in msg:
        checksum = ones_comp_add(checksum, i)
    return msg + bytes([checksum])


class IntellinetUDPClient:
    def __init__(
        self, transport: asyncio.DatagramTransport, protocol: _SocketProtocol
    ) -> None:
        self._transport = transport
        self._protocol = protocol

    @asynccontextmanager
    @staticmethod
    async def connect(
        local_addr: tuple[str, int] | None = None,
        remote_addr: tuple[str, int] | None = None,
        packets_queue_max_size: int = 0,
        reuse_port: bool | None = None,
    ) -> AsyncIterator["IntellinetUDPClient"]:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _SocketProtocol(packets_queue_max_size),
            local_addr=local_addr,
            remote_addr=remote_addr,
            reuse_port=reuse_port,
        )
        async with IntellinetUDPClient(transport, protocol) as sock:
            yield sock

    def close(self) -> None:
        """Close the socket."""

        self._transport.close()

    def _sendto(self, data: bytes, addr: tuple[str, int] | None = None) -> None:
        """Send given packet to given address ``addr``. Sends to
        ``remote_addr`` given to the constructor if ``addr`` is
        ``None``.

        Raises an error if a connection error has occurred.

        >>> sock.sendto(b'Hi!')

        """

        self._transport.sendto(data, addr)
        self._protocol.raise_if_error()

    async def _recvfrom(self) -> tuple[bytes, tuple[str, int]]:
        """Receive a UDP packet.

        Raises ClosedError on connection error, often by calling the
        close() method from another task. May raise other errors as
        well.

        >>> data, addr = sock.recvfrom()

        """

        packet = await self._protocol.recvfrom()
        self._protocol.raise_if_error()

        if packet is None:
            raise OSError("closed")

        return packet

    def getsockname(self) -> tuple[str, int]:
        """Get bound infomation.

        >>> local_address, local_port = sock.getsockname()

        """
        return self._transport.get_extra_info("sockname")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self.close()

    async def get_voltage(self) -> int:
        self._sendto(with_checksum(b"\xa7\x40\x06\x00"))
        data, addr = await self._recvfrom()
        assert len(data) == 13, len(data)
        assert data[0:4] == b"\xa7\x42\x06\x08", f"invalid response: {data.decode()}"
        assert data == with_checksum(data[:-1]), with_checksum(data[:-1])
        payload = data[4:12]
        voltage = payload[0]

        return voltage
