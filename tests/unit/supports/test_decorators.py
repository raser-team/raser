from types import SimpleNamespace

from raser.supports.io_decorator import io_decorator
from raser.supports.memory_decorator import memory_decorator


def test_io_decorator_reports_captured_stdout_and_stderr(capsys):
    def target():
        print("hello")

    io_decorator(target)()

    captured = capsys.readouterr()
    assert "Function 'target' executed successfully." in captured.out
    assert "Standard Output:" in captured.out
    assert "hello" in captured.out


def test_io_decorator_reports_exceptions_without_raising(capsys):
    def target():
        raise RuntimeError("boom")

    io_decorator(target)()

    assert "Function 'target' failed with an exception: boom" in capsys.readouterr().out


def test_memory_decorator_returns_wrapped_result_and_reports_usage(monkeypatch, capsys):
    class FakeProcess:
        def __init__(self):
            self.calls = 0

        def memory_info(self):
            self.calls += 1
            return SimpleNamespace(
                rss=self.calls * 1024**2,
                vms=(self.calls + 10) * 1024**2,
            )

    process = FakeProcess()
    monkeypatch.setattr(
        "raser.supports.memory_decorator.psutil.Process", lambda: process
    )

    @memory_decorator
    def target(value):
        return value * 2

    assert target(21) == 42

    captured = capsys.readouterr().out
    assert (
        "Memory usage before calling target: RSS = 1.00 MB, VMS = 11.00 MB" in captured
    )
    assert (
        "Memory usage after calling target: RSS = 2.00 MB, VMS = 12.00 MB" in captured
    )
    assert "Memory increase: RSS = 1.00 MB, VMS = 1.00 MB" in captured
