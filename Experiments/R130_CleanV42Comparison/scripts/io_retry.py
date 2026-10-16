"""Supplementary Windows I/O retries; frozen computation and old evidence remain unchanged."""
import time
import common
def atomic(path,value):
    for attempt in range(100):
        try:return common.atomic(path,value)
        except PermissionError:
            if attempt==99:raise
            time.sleep(.05)
