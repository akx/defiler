# -- encoding: utf-8 --
from __future__ import with_statement
from functools import wraps
import sys
import time
import re

at_ptr_re = re.compile(" at 0x[0-9A-F]+")
builtin_method_re = re.compile(r"<built-in method (\S+) of (\S+) object>")
builtin_func_re = re.compile(r"<built-in function (\S+)>")


def fix_builtin(s):
    s = at_ptr_re.sub("", s)
    s = builtin_method_re.sub(lambda m: "%s@%s" % (m.group(2), m.group(1)), s)
    s = builtin_func_re.sub(lambda m: "@%s" % (m.group(1)), s)
    return s


wallclock = (time.clock if sys.platform == "win32" else time.time)

RETURN_EVENTS = ("return", "c_exception")

class Defiler(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.events = []

    def __enter__(self):
        sys.setprofile(self._trace)

    def __exit__(self, et, ev, tb):
        sys.setprofile(None)
        self._write()

    def _write(self):
        TIME_SCALE = 1000
        time_adjust = None

        with file(self.name + "_%d.dfl.json" % time.time(), "wb") as out_file:
            out_file.write("{\"t\": %d, \"tscale\": %d, \"e\":[" % (time.time(), TIME_SCALE))
            level = 0
            for i, (event, etime, filename, lineno, funcname) in enumerate(self.events):
                if i == 0 and event == "return":  # This is likely exiting from __enter__
                    continue
                
                if time_adjust is None:
                    time_adjust = -etime

                if filename:
                    funcname = "%s^%s^%s" % (filename, lineno, funcname)
                else:
                    funcname = fix_builtin(funcname)


                if event in RETURN_EVENTS:
                    level -= 1
                    if level <= 0:
                        break

                out_file.write(
                    '["%s",%f,%d,"%s"],\n' % (event, (etime + time_adjust) * TIME_SCALE * 1000, level, funcname.replace("\\", "/")))

                if event == "call":
                    level += 1

            out_file.write("null]}")

    def _trace(self, frame, event, arg):
        if event == "c_call" or event == "c_return":
            event = event[2:]
            self.events.append((event, wallclock(), "", "", str(arg)))
        else:
            self.events.append((event, wallclock(), frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name))


def defile(name, **kwargs):
    def _defiler(fn):
        @wraps(fn)
        def _defiled(*args, **kwargs):
            with Defiler(name, **kwargs):
                return fn(*args, **kwargs)

        return _defiled

    return _defiler
