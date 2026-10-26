from qemu.qmp import QMPClient

from app.qmp_client import connect_qmp, watch_events
from app.vm_manager import VMManager
from pathlib import Path
import asyncio


async def query_status(qmp : QMPClient):
    status = await qmp.execute("query-status")

    return status


async def reset(qmp : QMPClient):
    status = await qmp.execute("system_reset")

    return status


async def shutdown(qmp : QMPClient, vm : VMManager) -> bool:
    await qmp.execute("system_powerdown")
    try:
        exit_code = await asyncio.wait_for(vm.wait(), timeout=60)
        print("QEMU завершился, код:", exit_code)
    except TimeoutError:
        print("за 60 секунд не получилось")
        return False
    return True


async def force_stop(vm : VMManager):
    await vm.force_stop()
    print("Процесс завершился")


async def main():
    project_dir = Path(__file__).resolve().parents[1]
    vm = VMManager(project_dir)
    await vm.start()
    qmp = await connect_qmp('/tmp/debian-vm-qmp.sock')
    events_task = asyncio.create_task(watch_events(qmp))

    try:
        while True:
            command = await asyncio.to_thread(
                input,"\nКоманда status/reset/shutdown/force/exit\n"
            )
            if command == 'status':
                status = await query_status(qmp)
                print(status)
            if command == 'reset':
                status = await reset(qmp)
                print(status)
            if command == 'shutdown':
                status = await shutdown(qmp, vm)
                if status:
                    break
            if command == 'force':
                await force_stop(vm)
                break
            if command == 'exit':
                await vm.force_stop()
                break
    finally:
        events_task.cancel()
        try:
            await events_task
        except asyncio.CancelledError:
            pass
        finally:
            await vm.force_stop()


if __name__ == "__main__":
    asyncio.run(main())