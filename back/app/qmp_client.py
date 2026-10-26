import asyncio

import qemu.qmp.protocol
from qemu.qmp import QMPClient, Message, EventListener
from .vm_manager import VMManager
from pathlib import Path

PATH = ""


async def connect_qmp(
        socket_path: str,
        timeout: float = 15,
) -> QMPClient:

    client = QMPClient("debian_vm")
    async with asyncio.timeout(timeout):
        while True:
            try:
                await client.connect(socket_path)
                return client
            except qemu.qmp.protocol.ConnectError:
                await asyncio.sleep(0.2)


async def watch_events(qmp: QMPClient):
    async for event in qmp.events:
        print("QMP event:", event)


async def main():
    pass
    # project_dir = Path(__file__).resolve().parents[2]
    # vm = VMManager(project_dir)
    # await vm.start()
    #
    # qmp = await connect_qmp('/tmp/debian-vm-qmp.sock')
    #
    # async with asyncio.timeout(5):
    #     status = await qmp.execute("query-status")
    #
    # print(status)
    #
    # events_task = asyncio.create_task(watch_events(qmp))


if __name__ == "__main__":
    asyncio.run(main())