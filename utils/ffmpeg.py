import os, re, subprocess, shutil, json, time
from pathlib import Path
from config import SET_FILE

def warn(msg):
    print(f"\033[91m{msg}\033[0m")

def info(msg):
    print(f"\033[92m{msg}\033[0m")

def load_cfg():
    cfg = {}
    if SET_FILE.exists():
        try:
            with open(SET_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            pass
            
    defaults = {
        # 以下为默认配置，可以根据需要修改
        "ffmpeg_path": ".\\EncodeTools\\ffmpeg.exe",
        "ffprobe_path": ".\\EncodeTools\\ffprobe.exe",
        "mp4box_path": "",
        "vspipe_path": ".\\EncodeTools\\Vapoursynth\\vspipe.exe",
        "x265_path": ".\\EncodeTools\\x265.exe",
        "x264_path": "",
        "v_enc": "libx264",
        "v_crf": 11.0,
        "a_enabled": False,
        "a_ok": False,
        "vs_mode": "x265 CLI",
        "vs_preset": "slow",
        "vs_crf": 18.0,
        "vs_extra_args": "",
        "vs_output": "",
        "a_enc": "aac",
        "adv_ok": False,
        "v_pre": "medium",
        "a_sr": "保持原始采样率"
    }
    for k, v in defaults.items():
        if k not in cfg:
            cfg[k] = v
    return cfg

def save_cfg(cfg):
    with open(SET_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def set_cfg(key, val):
    cfg = load_cfg()
    cfg[key] = val
    save_cfg(cfg)

def bind_cfg(widget, key, default_val):
    # 前台更改输入，后台实时更新配置
    from qfluentwidgets import ComboBox, SpinBox, DoubleSpinBox, CheckBox
    cfg = load_cfg()
    val = cfg.get(key, default_val)

    if isinstance(widget, ComboBox):
        idx = widget.findText(str(val))
        if idx >= 0:
            widget.setCurrentIndex(idx)
        else:
            widget.setCurrentText(str(default_val))
            set_cfg(key, default_val)
        widget.currentTextChanged.connect(lambda t: set_cfg(key, t))
    elif isinstance(widget, DoubleSpinBox):
        widget.setValue(float(val))
        widget.valueChanged.connect(lambda v: set_cfg(key, v))
    elif isinstance(widget, SpinBox):
        widget.setValue(int(val))
        widget.valueChanged.connect(lambda v: set_cfg(key, v))
    elif isinstance(widget, CheckBox):
        widget.setChecked(bool(val))
        widget.toggled.connect(lambda c: set_cfg(key, c))

def _resolve_path(path_str):
    # 解析相对或绝对路径
    if not path_str:
        return None
    if path_str.startswith(".\\") or path_str.startswith("./"):
        p = Path(os.getcwd()) / path_str
        if p.is_file():
            return str(p.resolve())
    else:
        if Path(path_str).is_file():
            return path_str
    return None

def find_exe(name):
    # 查找FFmpeg环境
    cfg = load_cfg()
    path = cfg.get(f"{name}_path", "").strip()
    res = _resolve_path(path)
    if res:
        return res
        
    if name == "ffprobe":
        ffmpeg_path = _resolve_path(cfg.get("ffmpeg_path", "").strip()) or shutil.which("ffmpeg")
        if ffmpeg_path:
            p = Path(ffmpeg_path).parent / "ffprobe.exe"
            if p.is_file():
                return str(p.resolve())
    elif name in ["x264", "x265"]:
        vspipe_path = _resolve_path(cfg.get("vspipe_path", "").strip()) or shutil.which("vspipe")
        if vspipe_path:
            p = Path(vspipe_path).parent / f"{name}.exe"
            if p.is_file():
                return str(p.resolve())

    return shutil.which(name)

def uniq_out(out_dir, base_name, ext):
    # 防重复机制，确保输出文件名唯一
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    while True:
        name = f"{base_name}_output{ext}" if n == 0 else f"{base_name}_output~{n}{ext}"
        p = out_dir / name
        if not p.exists():
            return p
        n += 1

def fmt_dur(sec):
    h, m, s = int(sec // 3600), int((sec % 3600) // 60), int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def read_txt(path):
    # 广编码读取文本文件
    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'ansi']:
        try:
            with open(path, 'r', encoding=enc) as f:
                content = f.read()
                return content, content.splitlines(keepends=True)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码：{path}")

def get_vinfo(vpath, save_json=False):
    # 调用 ffprobe 获取视频信息
    if not isinstance(vpath, Path):
        vpath = Path(vpath)
    if not vpath.is_file():
        return {'dur_ms': None, 'cspace': None, 'crange': None}

    fp = find_exe("ffprobe") or "ffprobe"
    try:
        c_flag = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        cmd = [fp, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(vpath)]
        data = json.loads(subprocess.run(cmd, capture_output=True, encoding='utf-8',
                                         check=True, creationflags=c_flag).stdout)
        dur_ms = int(float(data.get('format', {}).get('duration', 0)) * 1000)
        cspace = crange = None
        for s in data.get('streams', []):
            if s.get('codec_type') == 'video':
                cspace = s.get('color_space')
                crange = s.get('color_range')
                break
        if cspace and cspace.lower() == 'unknown':
            cspace = None
        if crange and crange.lower() == 'unknown':
            crange = None
        res = {'dur_ms': dur_ms, 'cspace': cspace, 'crange': crange}
        if save_json:
            from config import CFG_DIR
            jp = CFG_DIR / f"{vpath.stem}.json"
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            res['raw_json'] = str(jp)
        return res
    except Exception as e:
        warn(f"无法获取视频信息：{e}")
        return {'dur_ms': None, 'cspace': None, 'crange': None, 'raw_json': None}

def get_vdur(vpath):
    return get_vinfo(vpath).get('dur_ms')

def run_ff(cmd_list, desc, dur_ms=0, worker=None, log_cb=None, status_prefix=""):
    # 执行 FFmpeg 命令，返回进度结果
    info(f"\n正在{desc}：")
    c_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, creationflags=c_flags,
                                encoding='utf-8', errors='replace')
        if worker:
            worker.process = proc

        t_pat = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        start_time = time.time()
        for line in proc.stdout:
            if worker and worker.is_cancelled:
                break
            line = line.strip()
            if not line:
                continue
            pct = -1
            status_desc = None
            if dur_ms > 0:
                m = t_pat.search(line)
                if m:
                    h, mi, s = m.groups()
                    cur = (int(h) * 3600 + int(mi) * 60 + float(s)) * 1000
                    pct = min(100, int((cur / dur_ms) * 100))
                    
                    fps_match = re.search(r"fps=\s*([\d\.]+)", line)
                    speed_match = re.search(r"speed=\s*([\d\.]+)x", line)
                    fps_val = fps_match.group(1) if fps_match else None
                    speed_val = speed_match.group(1) if speed_match else None
                    
                    elapsed = time.time() - start_time
                    eta_str = ""
                    if pct > 0:
                        total_est = elapsed / (pct / 100.0)
                        eta_sec = max(0, int(total_est - elapsed))
                        h_eta = eta_sec // 3600
                        m_eta = (eta_sec % 3600) // 60
                        s_eta = eta_sec % 60
                        if h_eta > 0:
                            eta_str = f"{h_eta:02d}:{m_eta:02d}:{s_eta:02d}"
                        else:
                            eta_str = f"{m_eta:02d}:{s_eta:02d}"
                    
                    metrics = []
                    if fps_val:
                        metrics.append(f"帧率: {fps_val} fps")
                    if speed_val:
                        metrics.append(f"速度: {speed_val}x")
                    if eta_str:
                        metrics.append(f"剩余时间: {eta_str}")
                    
                    metric_str = " | ".join(metrics)
                    prefix = status_prefix if status_prefix else desc
                    if metric_str:
                        status_desc = f"{prefix} ({pct}%) [{metric_str}]"
                    else:
                        status_desc = f"{prefix} ({pct}%)"

            if log_cb:
                try:
                    log_cb(line, pct, status_desc)
                except TypeError:
                    log_cb(line, pct)
            else:
                print(line)

        proc.wait()
        if worker and worker.is_cancelled:
            return False
        return proc.returncode == 0
    except Exception as e:
        warn(f"FFmpeg 执行崩溃: {e}")
        return False
    finally:
        if worker:
            worker.process = None
