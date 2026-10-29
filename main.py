import asyncssh
import asyncio

from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from back.app.vm_manager import VMManager
from back.app.qmp_client import connect_qmp
from back.app.serial_bridge import serial_to_websocket, websocket_to_serial

from back.app.ssh_client import connect_ssh
from back.app.ssh_bridge import bridge_ssh


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_dir = Path(__file__).resolve().parent
    app.state.vm = VMManager(project_dir)

    try:
        yield
    finally:
        await app.state.vm.force_stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/vm/status")
async def vm_status(request: Request):
    vm = request.app.state.vm
    process_status = vm.status()

    if not process_status["process_running"]:
        return {
            **process_status,
            "qmp": None,
        }

    qmp = await connect_qmp("/tmp/debian-vm-qmp.sock")

    try:
        async with asyncio.timeout(5):
            guest_status = await qmp.execute("query-status")

        return {
            **process_status,
            "qmp": guest_status,
        }
    finally:
        await qmp.disconnect()

@app.post("/api/vm/start")
async def vm_start(request: Request):
    vm = request.app.state.vm
    status = await vm.start()
    return status

@app.post("/api/vm/reset")
async def vm_reset(request: Request):
    vm = request.app.state.vm
    if not vm.is_running():
        raise HTTPException(
            status_code=409, detail="Машина не запущена"
        )
    qmp = await connect_qmp('/tmp/debian-vm-qmp.sock')

    try:
        async with asyncio.timeout(5):
            await qmp.execute("system_reset")
            return {"reset_requested": True}
    finally:
        await qmp.disconnect()


@app.post("/api/vm/powerdown")
async def vm_powerdown(request: Request):
    vm = request.app.state.vm
    if not vm.is_running():
        raise HTTPException(
            status_code=409, detail="Машина не запущена"
        )
    qmp = await connect_qmp('/tmp/debian-vm-qmp.sock')

    try:
        async with asyncio.timeout(5):
            await qmp.execute("system_powerdown")
    finally:
        await qmp.disconnect()
    try:
        exit_code = await asyncio.wait_for(vm.wait(), timeout=67)
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="ВМ не выключилась за отведённое время"
        )
    return {
        "stopped": True,
        "exit_code": exit_code
    }


@app.post("/api/vm/force_shutdown")
async def vm_force_shutdown(request: Request):
    vm = request.app.state.vm
    if not vm.is_running():
        raise HTTPException(
            status_code=409, detail="Машина не запущена"
        )
    await vm.force_stop()
    return {"stopped": True}


@app.websocket("/api/vm/serial")
async def vm_serial(websocket: WebSocket):
    vm = websocket.app.state.vm

    await websocket.accept()

    if not vm.is_running():
        await websocket.close(
            code=1008,
            reason="Машина не запущена"
        )
        return

    try:
        async with asyncio.timeout(5):
            reader, writer = await asyncio.open_unix_connection(
                "/tmp/debian-vm-serial.sock"
            )
    except (OSError, TimeoutError):
        await websocket.close(
            code=1011,
            reason="Не удалось подключение к serial socket"
        )
        return

    tasks = [
        asyncio.create_task(serial_to_websocket(reader, websocket)),
        asyncio.create_task(websocket_to_serial(websocket, writer)),
    ]
    close_code = 1000
    close_reason = ""

    try:
        done, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except OSError:
        close_code = 1011
        close_reason = "Ошибка соединения с serial socket"
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        writer.close()
        try:
            with suppress(OSError):
                await writer.wait_closed()
        finally:
            if (
                websocket.client_state == WebSocketState.CONNECTED
                and websocket.application_state == WebSocketState.CONNECTED
            ):
                with suppress(WebSocketDisconnect):
                    await websocket.close(code=close_code, reason=close_reason)


@app.websocket("/api/vm/ssh")
async def vm_ssh(websocket: WebSocket):
    vm = websocket.app.state.vm

    await websocket.accept()

    if not vm.is_running():
        await websocket.close(
            code=1008,
            reason="Машина не запущена",
        )
        return

    close_code = 1000
    close_reason = ""

    try:
        connection = await connect_ssh()

        async with connection:
            async with asyncio.timeout(10):
                process = await connection.create_process(
                    term_type="xterm-256color",
                    term_size=(80, 24),
                    encoding=None,
                    stderr=asyncssh.STDOUT,
                )

            async with process:
                await bridge_ssh(process, websocket)

    except WebSocketDisconnect:
        pass

    except (OSError, asyncssh.Error, TimeoutError) as error:
        print("Ошибка SSH:", error)
        close_code = 1011
        close_reason = "Не удалось открыть или сохранить SSH-сеанс"

    finally:
        if (
            websocket.client_state == WebSocketState.CONNECTED
            and websocket.application_state == WebSocketState.CONNECTED
        ):
            with suppress(WebSocketDisconnect):
                await websocket.close(
                    code=close_code,
                    reason=close_reason,
                )