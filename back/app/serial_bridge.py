import asyncio

from fastapi import WebSocket


async def serial_to_websocket(
    reader: asyncio.StreamReader,
    websocket: WebSocket,
):
    while True:
        data = await reader.read(4096)

        if not data:
            return

        await websocket.send_bytes(data)


async def websocket_to_serial(
    websocket: WebSocket,
    writer: asyncio.StreamWriter,
):
    while True:
        data = await websocket.receive_bytes()
        writer.write(data)
        await writer.drain()