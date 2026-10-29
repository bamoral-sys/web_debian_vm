import asyncio
from pathlib import Path

import asyncssh


async def connect_ssh() -> asyncssh.SSHClientConnection:
    private_key = Path.home() / ".ssh" / "debian_vm_ed25519"
    known_hosts = Path.home() / ".ssh" / "known_hosts"

    async with asyncio.timeout(15):
        connection = await asyncssh.connect(
            host="127.0.0.1",
            port=2222,
            username="vmadmin",
            client_keys=[str(private_key)],
            known_hosts=str(known_hosts),
        )

    return connection