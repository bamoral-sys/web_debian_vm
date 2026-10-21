import asyncio
from time import sleep

from qemu.qmp import QMPClient, Message, EventListener
from vm_manager import VMManager
from pathlib import Path

PATH = ""

async def main():
    myvm = VMManager(Path('/mnt/c/Users/motor/PycharmProjects/web_debian_vm'))
    await myvm.start()

    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/debian-vm-qmp.sock')

    print(qmp.greeting.QMP.capabilities)
    print(qmp.await_greeting)
    res = await qmp.execute("query-status")

    print(res)
    print(qmp.await_greeting)

asyncio.run(main())