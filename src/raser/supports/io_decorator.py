"""
Description:  io_decorator.py
@Date       : 2022
@Author     : Yuhang Tan
@version    : 1.0
"""

import io
from contextlib import redirect_stdout, redirect_stderr
from functools import wraps


def io_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                result = func(*args, **kwargs)
        except Exception:
            _show_captured(func.__name__, stdout_buffer, stderr_buffer, succeeded=False)
            raise
        _show_captured(func.__name__, stdout_buffer, stderr_buffer, succeeded=True)
        return result

    return wrapper


def _show_captured(name, stdout_buffer, stderr_buffer, *, succeeded):
    status = "executed successfully" if succeeded else "failed"
    print(f"Function '{name}' {status}.")
    stdout_output = stdout_buffer.getvalue()
    stderr_output = stderr_buffer.getvalue()
    if stdout_output:
        print("Standard Output:")
        print(stdout_output, end="")
    if stderr_output:
        print("Standard Error:")
        print(stderr_output, end="")
