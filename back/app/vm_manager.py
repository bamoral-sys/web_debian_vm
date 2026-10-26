import asyncio
from pathlib import Path


class VMManager:
    def __init__(self, project_dir: Path):
        print("Корень проекта:", project_dir)
        print("Диск существует:", (project_dir / "images" / "vm.qcow2").is_file())
        self.project_dir = project_dir.resolve()

        self.disk_path = self.project_dir / "images" / "vm.qcow2"
        self.seed_path = self.project_dir / "images" / "seed.img"

        self.log_dir = self.project_dir / "back" / "logs"
        self.log_path = self.log_dir / "qemu.log"

        self.process: asyncio.subprocess.Process | None = None

        self._lock = asyncio.Lock()


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

    def _validate(self) -> None:
        for path in (self.disk_path, self.seed_path):
            if not path.is_file():
                raise FileNotFoundError(f"Не найден файл: {path}")


    async def start(self) -> dict:
        async with self._lock:
            if self.is_running():
                return {**self.status(), "already_running": True}

            self._validate()
            self.log_dir.mkdir(parents=True, exist_ok=True)

            with self.log_path.open("ab", buffering=0) as log:
                self.process = await asyncio.create_subprocess_exec(
                    "bash",
                    "scripts/boot.sh",
                    cwd=self.project_dir,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log,
                    stderr=asyncio.subprocess.STDOUT,
                )

            return {**self.status(), "already_running": False}

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

    async def force_stop(self) -> None:
        async with self._lock:
            await self._terminate_process()
