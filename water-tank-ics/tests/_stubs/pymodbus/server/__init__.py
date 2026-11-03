"""Minimal fake of pymodbus.server.StartAsyncTcpServer (never actually run in tests)."""


async def StartAsyncTcpServer(context=None, address=None, **kwargs):  # noqa: N802
    return None
