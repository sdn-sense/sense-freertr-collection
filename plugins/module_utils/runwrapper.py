# -*- coding: utf-8 -*-
"""wrapper to log runtimes.
Copyright: Contributors to the SENSE Project
GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

Title                   : sdn-sense/dellos9
Author                  : Justas Balcas
Email                   : juztas (at) gmail.com
@Copyright              : General Public License v3.0+
Date                    : 2023/11/05
"""
import inspect
import time

from ansible.utils.display import Display

display = Display()


def functionwrapper(func):
    """Function wrapper to print start/runtime/end"""
    def wrapper(*args, **kwargs):
        if display.verbosity > 5:
            display.vvvvvv(
                f"[WRAPPER][{time.time()}] Enter {func.__qualname__}, {func.__code__.co_filename}"
            )
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            total_time = end_time - start_time
            display.vvvvvv(
                f"[WRAPPER][{time.time()}] Function {func.__qualname__} {args} {kwargs} Took {total_time:.4f} seconds"
            )
            display.vvvvvv(f"[WRAPPER][{time.time()}] Leave {func.__qualname__}")
        else:
            result = func(*args, **kwargs)
        return result

    return wrapper


def classwrapper(cls):
    """Class wrapper to print all functions start/runtime/end"""
    for name, method in cls.__dict__.items():
        if callable(method) and name != "__init__":
            if inspect.isfunction(method):
                if inspect.signature(method).parameters.get('self'):
                    setattr(cls, name, functionwrapper(method))
            elif inspect.ismethod(method):
                if inspect.signature(method).parameters:
                    firstParam = next(iter(inspect.signature(method).parameters))
                    if firstParam == 'self':
                        setattr(cls, name, functionwrapper(method))
    return cls
