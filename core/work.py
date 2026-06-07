import os
import json
import ctypes
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from threading import Lock
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject
from config import CFG_DIR

QUEUE_FILE = CFG_DIR / "task_queue.json"


class JobState(Enum):
    WAIT = "pending"
    RUN = "running"
    PAUSE = "paused"
    DONE = "done"
    FAIL = "failed"
    STOP = "cancelled"

    @property
    def icon(self):
        return ""

    @property
    def text(self):
        # 任务状态
        m = {"pending": "等待中", "running": "进行中", "paused": "已暂停", "done": "已完成", "failed": "失败", "cancelled": "已取消"}
        return m.get(self.value, self.value)


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    jtype: str = ""
    name: str = ""
    params: dict = field(default_factory=dict)
    state: JobState = JobState.WAIT
    pct: int = 0
    log: list = field(default_factory=list)
    err: str = ""
    made_at: str = field(default_factory=lambda: datetime.now().isoformat())
    done_at: str = ""

    def to_dict(self):
        return {"id": self.id, "task_type": self.jtype, "display_name": self.name,
                "params": self.params, "status": self.state.value, "created_at": self.made_at}

    @classmethod
    def from_dict(cls, d):
        try:
            st = JobState(d.get("status", "pending"))
        except ValueError:
            st = JobState.WAIT
        return cls(id=d.get("id", ""), jtype=d.get("task_type", ""),
                   name=d.get("display_name", ""), params=d.get("params", {}),
                   state=st, made_at=d.get("created_at", ""))

    @staticmethod
    def type_name(jtype):
        m = {"encode": "视频压制", "mux": "混流封装", "mux_ff": "混流封装", "fast_mux": "MP4快速封装",
             "clean": "字幕清洗", "chapter": "章节封装", "vs": "VapourSynth压制"}
        return m.get(jtype, jtype)


def suspend_process(pid):
    # 挂起任务
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
        if handle:
            ctypes.windll.ntdll.NtSuspendProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def resume_process(pid):
    # 恢复挂起的任务
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
        if handle:
            ctypes.windll.ntdll.NtResumeProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


class RunnerSig(QObject):
    log = Signal(str)
    done = Signal()
    err = Signal(str)
    prog = Signal(int, str)


class Runner(QThread):

    def __init__(self, jtype, params):
        super().__init__()
        self.jtype = jtype
        self.params = params
        self.sig = RunnerSig()
        self.paused = False
        self.cancelled = False
        self.processes = []

    @property
    def process(self):
        return self.processes[0] if self.processes else None

    @process.setter
    def process(self, proc):
        if proc is None:
            self.processes.clear()
        else:
            self.processes = [proc]

    @property
    def is_cancelled(self):
        return self.cancelled

    def pause(self):
        self.paused = True
        if os.name == "nt":
            for p in self.processes:
                suspend_process(p.pid)

    def goon(self):
        self.paused = False
        if os.name == "nt":
            for p in self.processes:
                resume_process(p.pid)

    def stop(self):
        self.cancelled = True
        self.paused = False
        if os.name == "nt":
            for p in self.processes:
                resume_process(p.pid)
        for p in self.processes:
            try:
                p.terminate()
            except Exception:
                pass

    def log(self, line, pct, status_desc=None):
        if pct >= 0:
            desc = status_desc if status_desc else line
            self.sig.prog.emit(pct, desc)
        self.sig.log.emit(line)

    def run(self):
        # 线程运行：分发执行不同任务
        if self.jtype in ["encode", "mux", "mux_ff", "fast_mux", "chapter", "vs"]:
            self.params['worker'] = self

        try:
            if self.jtype == "encode":
                from core.tools.encode_videos import encode
                encode(**self.params)
            elif self.jtype == "clean":
                from core.tools.subs_clean import clean_subs
                single = len(self.params['vid_list']) == 1
                total = len(self.params['vid_list'])
                for idx, p in enumerate(self.params['vid_list']):
                    if self.cancelled:
                        break
                    pct = int((idx / total) * 100)
                    self.log(f"正在清洗字幕 ({idx+1}/{total}): {p.name}", pct)
                    clean_subs(p, self.params['mode'], self.params['split_n'],
                               self.params['out_dir'], single)
                self.log("所有字幕清洗完成", 100)
            elif self.jtype == "mux":
                from core.tools.muxer import mux
                mux(**self.params)
            elif self.jtype == "fast_mux":
                from core.tools.muxer import mux
                mux(**self.params)
            elif self.jtype == "mux_ff":
                from core.tools.muxer import mux_ff
                mux_ff(**self.params)
            elif self.jtype == "chapter":
                from core.tools.chaper_into import inject_chap
                inject_chap(**self.params)
            elif self.jtype == "vs":
                from core.vapoursynth.vs_pipe import run_vs_cli, run_vs_ff
                scr = self.params["scr"]
                out = self.params["out"]
                enc = self.params["enc"]
                enc_p = self.params["enc_p"]
                mode = self.params["_mode"]
                if mode == "ffmpeg":
                    ok = run_vs_ff(scr, out, enc, enc_p, self)
                else:
                    ok = run_vs_cli(scr, out, enc, enc_p, self)
                if not ok:
                    raise Exception("VapourSynth压制管道执行失败")

            self.sig.log.emit("\n>>> 任务完成 <<<")
        except Exception as e:
            self.sig.err.emit(str(e))
        finally:
            self.sig.done.emit()


class QSig(QObject):
    added = Signal(str)
    started = Signal(str)
    prog = Signal(str, int)
    log = Signal(str, str)
    ended = Signal(str, bool)
    changed = Signal()
    all_done = Signal()


class JobQ:

    def __init__(self, max_run=1):
        self._q: list[Job] = []
        self._lk = Lock()
        self.max_run = max_run
        self._running: dict[str, Runner] = {}
        self._enabled = False
        self.sig = QSig()

    def add(self, job):
        with self._lk:
            self._q.append(job)
        self.sig.added.emit(job.id)
        self.sig.changed.emit()
        self._save()

    def remove(self, jid):
        stop_w = None
        changed = False
        with self._lk:
            for t in self._q:
                if t.id == jid and t.state == JobState.RUN:
                    stop_w = self._running.get(jid)
                    break
            
            before = len(self._q)
            self._q = [t for t in self._q if t.id != jid]
            if len(self._q) < before:
                changed = True
        
        if stop_w:
            stop_w.stop()
            
        if changed:
            self.sig.changed.emit()
            self._save()
            return True
            
        return False

    def move(self, jid, d):
        with self._lk:
            for i, t in enumerate(self._q):
                if t.id == jid:
                    ni = i + d
                    if 0 <= ni < len(self._q):
                        self._q[i], self._q[ni] = self._q[ni], self._q[i]
                    break
        self.sig.changed.emit()

    def clear_done(self):
        with self._lk:
            self._q = [t for t in self._q
                       if t.state in (JobState.WAIT, JobState.RUN, JobState.PAUSE)]
        self.sig.changed.emit()
        self._save()

    def all(self):
        with self._lk:
            return list(self._q)

    def get(self, jid):
        for t in self._q:
            if t.id == jid:
                return t
        return None

    def _next(self):
        job = None
        with self._lk:
            if not self._enabled:
                return
            if len(self._running) >= self.max_run:
                return
            for t in self._q:
                if t.state == JobState.WAIT:
                    t.state = JobState.RUN
                    job = t
                    break
        if job:
            self._go(job)
            self._save()

    def _go(self, job):
        r = Runner(job.jtype, dict(job.params))
        self._running[job.id] = r

        def on_log(msg, jid=job.id):
            job.log.append(msg)
            self.sig.log.emit(jid, msg)

        def on_prog(pct, _msg, jid=job.id):
            job.pct = pct if pct >= 0 else job.pct
            self.sig.prog.emit(jid, job.pct)

        def on_done(jid=job.id):
            w = self._running.pop(jid, None)
            ok = w and not getattr(w, "cancelled", False) and not getattr(w, "_err", False)
            self._finish(jid, ok)

        def on_err(err, jid=job.id):
            w = self._running.get(jid)
            if w:
                setattr(w, "_err", True)
            job.err = err
            self.sig.log.emit(jid, f"[错误] {err}")

        r.sig.log.connect(on_log)
        r.sig.prog.connect(on_prog)
        r.sig.done.connect(on_done)
        r.sig.err.connect(on_err)

        r.start()
        self.sig.started.emit(job.id)
        self.sig.changed.emit()

    def _finish(self, jid, ok):
        with self._lk:
            for t in self._q:
                if t.id == jid:
                    t.state = JobState.DONE if ok else JobState.FAIL
                    t.done_at = datetime.now().isoformat()
                    break
        self.sig.ended.emit(jid, ok)
        self.sig.changed.emit()
        self._save()
        self._next()

        with self._lk:
            is_all_finished = len(self._running) == 0 and not any(t.state == JobState.WAIT for t in self._q)
        if is_all_finished and self._enabled:
            self._enabled = False
            self.sig.all_done.emit()

    def start_queue(self):
        self._enabled = True
        self._next()

    def pause_all(self):
        with self._lk:
            for jid, r in list(self._running.items()):
                r.pause()
                for t in self._q:
                    if t.id == jid:
                        t.state = JobState.PAUSE
        self.sig.changed.emit()

    def goon_all(self):
        self._enabled = True
        with self._lk:
            for jid, r in list(self._running.items()):
                r.goon()
                for t in self._q:
                    if t.id == jid:
                        t.state = JobState.RUN
        self.sig.changed.emit()
        self._next()



    def set_max(self, n):
        self.max_run = max(1, min(n, 8))
        if self._enabled:
            self._next()



    def _save(self):
        try:
            items = [t.to_dict() for t in self._q
                     if t.state in (JobState.WAIT, JobState.PAUSE)]
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def load_q():
    if not QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return [Job.from_dict(d) for d in data]
    except Exception:
        return []



