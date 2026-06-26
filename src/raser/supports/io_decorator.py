'''
Description:  io_decorator.py
@Date       : 2022
@Author     : Yuhang Tan
@version    : 1.0
'''

import io
from contextlib import redirect_stdout, redirect_stderr

def io_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            # Capture the standard output and error
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                func(*args, **kwargs)
            # Get the output
            stdout_output = stdout_buffer.getvalue()
            stderr_output = stderr_buffer.getvalue()

            print(f"Function '{func.__name__}' executed successfully.")
            print("Standard Output:")
            print(stdout_output)

            if stderr_output:
                print("Standard Error:")
                print(stderr_output)

        except Exception as e:
            print(f"Function '{func.__name__}' failed with an exception:", e)

    return wrapper
