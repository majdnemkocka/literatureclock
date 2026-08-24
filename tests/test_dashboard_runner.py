import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.runner import ProcessRunner


class TestProcessRunner(unittest.TestCase):
    def test_run_command_captures_output_and_exit_code(self):
        async def _run():
            lines = []
            runner = ProcessRunner(
                command=[sys.executable, "-c", "import sys; print('Hello Textual'); sys.stderr.write('Warning log\\n'); sys.exit(0)"],
                on_line=lambda line, is_err: lines.append((line, is_err))
            )
            code = await runner.run_async()
            self.assertEqual(code, 0)
            self.assertFalse(runner.is_running)
            text_outputs = [l[0] for l in lines]
            self.assertTrue(any("Hello Textual" in l for l in text_outputs))
            self.assertTrue(any("Warning log" in l for l in text_outputs))

        asyncio.run(_run())

    def test_stop_running_process(self):
        async def _run():
            runner = ProcessRunner(
                command=[sys.executable, "-c", "import time; time.sleep(10)"],
            )
            task = asyncio.create_task(runner.run_async())
            await asyncio.sleep(0.2)
            self.assertTrue(runner.is_running)
            await runner.stop()
            code = await task
            self.assertFalse(runner.is_running)
            self.assertIsNotNone(code)

        asyncio.run(_run())
