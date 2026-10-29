import asyncio

from fastapi import WebSocket


async def ssh_to_websocket(process, websocket: WebSocket):
    while True:
        data = await process.stdout.read(4096)

        if not data:
            return

        await websocket.send_bytes(data)


async def websocket_to_ssh(websocket: WebSocket, process):
    while True:
        data = await websocket.receive_bytes()
        process.stdin.write(data)
        await process.stdin.drain()


async def bridge_ssh(process, websocket: WebSocket):
    tasks = [
        asyncio.create_task(ssh_to_websocket(process, websocket)),
        asyncio.create_task(websocket_to_ssh(websocket, process)),
    ]

    try:
        done, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)