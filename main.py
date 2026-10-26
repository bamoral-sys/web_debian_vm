import asyncio

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException

from back.app.vm_manager import VMManager
from back.app.qmp_client import connect_qmp


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_dir = Path(__file__).resolve().parent
    app.state.vm = VMManager(project_dir)

    try:
        yield
    finally:
        await app.state.vm.force_stop()

app = FastAPI(lifespan=lifespan)

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