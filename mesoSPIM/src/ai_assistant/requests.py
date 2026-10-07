"""The operator's requests: what one typed message set going, over as many turns as it takes.

A typed message opens a request. A schedule it set and a wait it asked for come back as turns
of the same request, written by the machine, not typed: the turn guard takes the operator's
numbers from typed text only (D1). `wait` ends a turn and leaves one continuation pending; when
its condition holds, the tab starts the next turn of the request with the result (D2). A
checklist in a reply is the request's plan, kept and shown with it (D3). Stop microscope,
Cancel, Disconnect and Clear context end a request.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import re
import threading
import time

from . import config
from ..remote_control.config import ACQUIRING_STATES

_CHECKLIST = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+?)\s*$", re.MULTILINE)


class Request:
    """One request: its number, the operator's words, the turns and tokens it took, its plan,
    the operation it started last, and the wait it has pending."""

    def __init__(self, number, prompt, started):
        self.number = number
        self.prompt = prompt
        self.started = started
        self.turns = 0
        self.tokens = 0
        self.continuations = 0
        self.plan = []
        self.last_operation = None
        self.wait = None              # {"until", "max_s", "since"}
        self.ended = None             # why it ended, or None while it is open

    def brief(self, now):
        out = {"number": self.number, "prompt": self.prompt[:200], "turn": self.turns,
               "minutes": round((now - self.started) / 60, 1)}
        if self.plan:
            out["plan"] = self.plan
        if self.wait:
            out["waiting"] = {"until": self.wait["until"], "for_s": int(now - self.wait["since"])}
        return out


class Requests:
    """The requests of the session: the current one, and the one with a pending continuation (at
    most one). Thread-safe: the tools run on the worker's threads, the tab asks from its own."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.current = None
        self.waiting = None
        self._known = {}
        self._count = 0
        self._lock = threading.Lock()

    def typed(self, prompt):
        """A typed message: a new request."""
        with self._lock:
            self._count += 1
            self.current = Request(self._count, prompt, self.clock())
            self._known[self.current.number] = self.current
            return self.current

    def machine(self, number):
        """A turn the machine wrote, for request `number`: a fired schedule or a continuation."""
        with self._lock:
            request = self._known.get(number)
            if request is None:                       # a schedule from before Clear context
                self._count += 1
                request = self._known[self._count] = Request(self._count, "(scheduled)", self.clock())
            self.current = request
            return request

    def finish_turn(self, reply, tokens):
        """After a turn: count it, and take a checklist in the reply as the plan."""
        with self._lock:
            request = self.current
            if request is None:
                return
            request.turns += 1
            request.tokens += tokens
            steps = [f"[{'x' if mark.strip() else ' '}] {text}" for mark, text in _CHECKLIST.findall(reply or "")]
            if steps:
                request.plan = steps[:config.PLAN_STEPS_MAX]

    def started(self, operation):
        """The operation the current request started last, for wait(until="done")."""
        if self.current is not None and operation:
            self.current.last_operation = operation

    def wait(self, until, max_s=None):
        """Leave a continuation pending for the current request. Returns what to tell the model."""
        with self._lock:
            request = self.current
            if request is None or request.ended:
                raise ValueError("there is no request to continue")
            if self.waiting is not None and self.waiting is not request:
                raise ValueError(f"request {self.waiting.number} is already waiting; one wait at a time")
            if request.continuations >= config.CONTINUATIONS_MAX:
                raise ValueError(f"this request has continued {request.continuations} times; tell the operator "
                                 "where it stands and let them say whether to go on")
            until = _until(until)
            if until == "done" and request.last_operation is None:
                return None                            # nothing started: nothing to wait for
            limit = float(max_s or config.WAIT_MAX_S)
            if isinstance(until, float):
                limit = min(limit, until) if max_s else until
            request.wait = {"until": until, "max_s": min(limit, config.WAIT_MAX_S), "since": self.clock()}
            self.waiting = request
            return request.wait

    def is_waiting(self):
        """True while the current request's turn has asked to wait: it must end now."""
        return self.current is not None and self.current.wait is not None

    def due(self, read):
        """The continuation that has come due, as (request, what happened), or None. `read` is the
        dispatcher's read (get_snapshot), from the caller's thread."""
        with self._lock:
            request = self.waiting
            if request is None:
                return None
            wait = request.wait
            waited = self.clock() - wait["since"]
            until = wait["until"]
            if isinstance(until, float):
                met = waited >= until
            else:
                try:
                    met = _condition(until, request.last_operation, read("get_snapshot", {}) or {})
                except Exception:
                    met = False
            if not met and waited < wait["max_s"]:
                return None
            result = (f"waited {int(waited)} s until {until if not isinstance(until, float) else 'the time'}: "
                      + ("met" if met else f"not met after the limit of {int(wait['max_s'])} s"))
            request.wait, self.waiting = None, None
            request.continuations += 1
            return request, result

    def end(self, reason):
        """End the open requests (Stop microscope, Cancel, Disconnect, Clear context)."""
        with self._lock:
            for request in (self.current, self.waiting):
                if request is not None and request.ended is None:
                    request.ended, request.wait = reason, None
            self.waiting = None

    def open(self):
        """The request the window shows: the waiting one, else the current one while open."""
        request = self.waiting or self.current
        return request if request is not None and request.ended is None else None


def _until(until):
    if isinstance(until, (int, float)) and not isinstance(until, bool):
        seconds = float(until)
    elif isinstance(until, str) and until.strip().lower() in ("done", "idle"):
        return until.strip().lower()
    else:
        try:
            seconds = float(str(until).strip())
        except ValueError:
            raise ValueError(f"until is 'done', 'idle' or a number of seconds, not {until!r}") from None
    if seconds < config.SCHEDULE_MIN_SECONDS:
        raise ValueError(f"wait at least {config.SCHEDULE_MIN_SECONDS} s")
    return seconds


def _condition(until, operation, readout):
    """Whether the instrument is done ("done": the request's last operation finished or released,
    nothing acquiring, no time lapse) or idle ("idle": nothing running at all)."""
    state = readout.get("state")
    current = readout.get("operation") or {}
    running = current.get("status") in ("processing", "stopping")
    busy = state in ACQUIRING_STATES or bool((readout.get("time_lapse") or {}).get("active"))
    if until == "idle":
        return state == "idle" and not running and not busy
    ours = current.get("id") == operation
    return not busy and not (ours and running)
