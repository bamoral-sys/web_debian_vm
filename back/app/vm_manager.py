import asyncio
import tempfile
from pathlib import Path


class VMManager:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir.resolve()

        self.disk_path = self.project_dir / "images" / "vm.qcow2"
        self.seed_path = self.project_dir / "images" / "seed.img"

        self.log_dir = self.project_dir / "back" / "logs"
        self.log_path = self.log_dir / "qemu.log"

        self.process: asyncio.subprocess.Process | None = None

        self.qmp_socket: Path | None = None
        self.serial_socket: Path | None = None

        self._lock = asyncio.Lock()
        self._runtime: tempfile.TemporaryDirectory | None = None

    def is_running(self) -> bool:
        return (
            self.process is not None
            and self.process.returncode is None
        )

    def status(self) -> dict:
        return {
            "process_running": self.is_running(),
            "pid": self.process.pid if self.is_running() else None,
            "exit_code": (
                self.process.returncode
                if self.process is not None
                else None
            )
        }

    def _validate(self) -> str:
        for path in (self.disk_path, self.seed_path):
            if not path.is_file():
                raise FileNotFoundError(f"Не найден файл: {path}")


    async def start(self) -> dict:
        async with self._lock:
            if self.is_running():
                return {
                    **self.status(),
                    "already_running": True,
                }

            self._validate()
            self.log_dir.mkdir(parents=True, exist_ok=True)

            self._cleanup_runtime()

            self._runtime = tempfile.TemporaryDirectory(
                prefix="debian-vm-",
                dir="/tmp",
            )

            runtime_dir = Path(self._runtime.name)
            self.qmp_socket = runtime_dir / "qmp.sock"
            self.serial_socket = runtime_dir / "serial.sock"

            try:
                with self.log_path.open("ab", buffering=0) as log:
                    self.process = await asyncio.create_subprocess_exec(
                        "bash",
                        "boot.sh",
                        str(self.qmp_socket),
                        str(self.serial_socket),
                        cwd=self.project_dir / "scripts",
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=log,
                        stderr=asyncio.subprocess.STDOUT,
                    )

                await self._wait_for_sockets()

            except BaseException:
                await self._terminate_process()
                self._cleanup_runtime()
                raise

            return {
                **self.status(),
                "already_running": False,
            }

    async def _wait_for_sockets(self, timeout: float = 10):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            if not self.is_running():
                raise RuntimeError(
                    "QEMU завершился при запуске. ")

            if (self.qmp_socket is not None
                and self.serial_socket is not None
                and self.qmp_socket.is_socket()
                and self.serial_socket.is_socket()):
                return

        raise TimeoutError(
            "QEMU не создал сокеты за отведённое время. ")

    async def wait(self) -> int:
        if self.process is None:
            raise RuntimeError("QEMU ещё не запускался")

        return await self.process.wait()

    async def _terminate_process(self):
        process = self.process

        if process is None or process.returncode is not None:
            return

        try:
            process.terminate()
        except ProcessLookupError:
            pass

        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass

            await process.wait()

    def _cleanup_runtime(self):
        if self._runtime is not None:
            self._runtime.cleanup()
            self._runtime = None

        self.qmp_socket = None
        self.serial_socket = None

    async def force_stop(self) -> None:
        async with self._lock:
            await self._terminate_process()
            self._cleanup_runtime()