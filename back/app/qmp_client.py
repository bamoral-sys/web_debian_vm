import asyncio
import time

import qemu.qmp.protocol
from qemu.qmp import QMPClient, Message, EventListener
from vm_manager import VMManager
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



async def main():
    myvm = VMManager(Path('/mnt/c/Users/motor/PycharmProjects/web_debian_vm'))
    await myvm.start()

    qmp = await connect_qmp('/tmp/debian-vm-qmp.sock')
    print(qmp.greeting.QMP)



asyncio.run(main())