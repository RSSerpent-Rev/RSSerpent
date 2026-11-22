import sys

if sys.implementation.name != "cpython" or sys.version_info[:2] not in {(3, 14), (3, 15)}:
    message = "RSSerpent supports CPython 3.14 and 3.15."
    raise RuntimeError(message)
