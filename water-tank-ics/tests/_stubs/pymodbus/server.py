"""Fake server entry point; not invoked by the wiring smoke test."""


async def StartAsyncTcpServer(context=None, address=None):  # noqa: N802
    raise RuntimeError("fake StartAsyncTcpServer should not run in tests")
