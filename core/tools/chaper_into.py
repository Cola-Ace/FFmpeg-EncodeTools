from pathlib import Path
from utils import find_exe, run_ff, info, warn, get_vdur, uniq_out
from core.tools.chapters import make_meta

def inject_chap(v_path, times_ms, names, out_path=None, worker=None):
    vp = Path(v_path)
    if not out_path:
        out_path = uniq_out(vp.parent, vp.stem, "_chapter.mp4")
    else:
        out_path = Path(out_path)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".mp4")
        out_path.parent.mkdir(parents=True, exist_ok=True)

    if not times_ms or not names:
        warn("章节数据为空，取消任务")
        return False

    dur = get_vdur(vp) or 999999999
    meta_f = vp.parent / f"{vp.stem}_metadata.txt"
    make_meta(times_ms, names, meta_f, total_ms=dur)

    ff = find_exe("ffmpeg") or "ffmpeg"
    cmd = [ff, '-i', str(vp), '-i', str(meta_f),
           '-map_metadata', '1', '-map_chapters', '1',
           '-map', '0', '-c', 'copy', '-y', str(out_path)]

    log_cb = worker.log if worker else None
    ok = run_ff(cmd, "章节注入", 0, worker, log_cb=log_cb)
    if meta_f.exists():
        try:
            meta_f.unlink()
        except Exception:
            pass
    if ok:
        info(f"章节封装完成 -> {out_path}")
    return ok
