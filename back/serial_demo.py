import asyncio
import sys


async def main():
    reader, writer = await asyncio.open_unix_connection(
        "/tmp/debian-vm-serial.sock"
    )

    try:
        # Имитируем Enter, чтобы вызвать реакцию консоли.
        writer.write(b"\r")
        await writer.drain()

        while True:
            data = await reader.read(4096)

            if not data:
                print("\nSerial-соединение закрыто")
                break

            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    finally:
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())