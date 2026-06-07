import subprocess, shutil, os
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class EncEntry:
    name: str
    desc: str = ""
    etype: str = "video"


class FFCap:

    def __init__(self, ff_path="ffmpeg"):
        self.ff = ff_path
        self.v_encs: dict[str, EncEntry] = {}
        self.a_encs: dict[str, EncEntry] = {}
        self.gpu_encs: dict[str, str] = {}
        self.ok = False

    def scan(self):
        try:
            self._do_scan()
            self.ok = True
            return True
        except Exception as e:
            print(f"[FFmpeg] 检测失败: {e}")
            return False

    def _do_scan(self):
        c_flag = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([self.ff, "-encoders"], capture_output=True,
                           text=True, creationflags=c_flag)
        for line in r.stdout.split("\n"):
            line = line.strip()
            if line.startswith(" V"):
                parts = line[7:].strip().split(None, 1)
                if parts:
                    self.v_encs[parts[0]] = EncEntry(parts[0], parts[1] if len(parts) > 1 else parts[0], "video")
            elif line.startswith(" A"):
                parts = line[7:].strip().split(None, 1)
                if parts:
                    self.a_encs[parts[0]] = EncEntry(parts[0], parts[1] if len(parts) > 1 else parts[0], "audio")

        gpu_map = {"nvenc": "nvidia", "amf": "amd", "qsv": "intel",
                   "videotoolbox": "apple", "vaapi": "linux"}
        for name in self.v_encs:
            for suf, gtype in gpu_map.items():
                if name.endswith("_" + suf):
                    self.gpu_encs[name] = gtype
                    break

    def has(self, name):
        if not self.ok:
            self.scan()
        return name in self.v_encs or name in self.a_encs

    def list_v(self, names):
        if not self.ok:
            self.scan()
        return [n for n in names if n in self.v_encs]

    def v_by_cat(self):
        if not self.ok:
            self.scan()
        cats = {
            "CPU 软件编码": ["libx264", "libx265", "libsvtav1"],
            "NVIDIA GPU": ["h264_nvenc", "hevc_nvenc", "av1_nvenc"],
            "AMD GPU": ["h264_amf", "hevc_amf"],
            "Intel GPU": ["h264_qsv", "hevc_qsv", "av1_qsv"],
        }
        res = {}
        for cat, names in cats.items():
            avail = self.list_v(names)
            if avail:
                res[cat] = avail
        return res




_ff_cap: Optional[FFCap] = None

def get_ffcap(ff_path="ffmpeg"):
    global _ff_cap
    if _ff_cap is None:
        _ff_cap = FFCap(ff_path)
        _ff_cap.scan()
    elif _ff_cap.ff != ff_path:
        _ff_cap.ff = ff_path
        _ff_cap.scan()
    return _ff_cap



