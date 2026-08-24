import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


class ProcessRunner:
    """
    Asynchronous process runner that executes commands, streams stdout and stderr
    line-by-line via callbacks, and allows clean cancellation.
    """

    def __init__(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        on_line: Optional[Callable[[str, bool], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.command = command
        self.cwd = cwd or Path.cwd()
        self.env = env
        self.on_line = on_line
        self.on_status_change = on_status_change
        
        self.process: Optional[asyncio.subprocess.Process] = None
        self.is_running = False
        self.exit_code: Optional[int] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self._stopped_manually = False

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        if self.end_time is not None:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    async def run_async(self) -> int:
        self.is_running = True
        self._stopped_manually = False
        self.start_time = time.time()
        self.end_time = None
        self.exit_code = None

        if self.on_status_change:
            self.on_status_change("running")

        # Merge environment
        merged_env = os.environ.copy()
        # Ensure unbuffered python output
        merged_env["PYTHONUNBUFFERED"] = "1"
        if self.env:
            merged_env.update(self.env)

        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                cwd=str(self.cwd),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _stream_reader(stream, is_err: bool):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if self.on_line:
                        self.on_line(decoded, is_err)

            await asyncio.gather(
                _stream_reader(self.process.stdout, False),
                _stream_reader(self.process.stderr, True),
            )

            self.exit_code = await self.process.wait()
        except asyncio.CancelledError:
            await self.stop()
            self.exit_code = -1
        except Exception as e:
            if self.on_line:
                self.on_line(f"Végrehajtási hiba: {str(e)}", True)
            self.exit_code = 1
        finally:
            self.end_time = time.time()
            self.is_running = False
            status = "completed" if self.exit_code == 0 else ("stopped" if self._stopped_manually else "failed")
            if self.on_status_change:
                self.on_status_change(status)

        return self.exit_code or 0

    async def stop(self) -> None:
        if self.process and self.is_running:
            self._stopped_manually = True
            try:
                self.process.terminate()
                # Wait up to 1.5 seconds for graceful shutdown
                for _ in range(15):
                    if self.process.returncode is not None:
                        break
                    await asyncio.sleep(0.1)
                if self.process.returncode is None:
                    self.process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            self.is_running = False
