import unittest

from src.core.background import BackgroundTask, TaskResult


class BackgroundTaskTests(unittest.TestCase):
    def _run(self, work):
        finished = []
        progress = []
        task = BackgroundTask(work)
        task.signals.progress.connect(progress.append)
        task.signals.finished.connect(finished.append)
        task.run()
        self.assertEqual(len(finished), 1)
        self.assertIsInstance(finished[0], TaskResult)
        return finished[0], progress

    def test_success_forwards_value_and_progress(self) -> None:
        result, progress = self._run(lambda emit: (emit(25), emit(100), "done")[-1])

        self.assertTrue(result.ok)
        self.assertEqual(result.value, "done")
        self.assertEqual(progress, [25, 100])

    def test_worker_exception_becomes_failed_result(self) -> None:
        def fail(_emit):
            raise RuntimeError("network down")

        result, progress = self._run(fail)

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "network down")
        self.assertEqual(progress, [])

    def test_empty_worker_exception_is_still_a_failure(self) -> None:
        def fail(_emit):
            raise RuntimeError()

        result, _ = self._run(fail)

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "")


if __name__ == "__main__":
    unittest.main()
