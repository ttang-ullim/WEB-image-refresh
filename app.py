import math
import os
import random
import shutil
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from PIL import Image, ImageEnhance

app = Flask(__name__)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEMP_ROOT = Path(tempfile.gettempdir()) / "image_washer_web_jobs"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
MAX_LOG_LINES = 4000
APP_DISPLAY_NAME = "루멕스 이미지 리프레시"
VISITOR_ACTIVE_WINDOW_MINUTES = 5
VISITOR_RETENTION_DAYS = 30
OWNER_VISITOR_TOKEN = os.environ.get("LUMEX_OWNER_TOKEN", "lumex-refresh-owner")

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
VISITOR_TOTAL_VIEWS = 0
VISITOR_IP_LAST_SEEN: dict[str, datetime] = {}
VISITOR_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes", "y"}


def parse_int(
    value: Any,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        out = int(float(str(value)))
    except Exception:
        out = default
    if minimum is not None:
        out = max(minimum, out)
    if maximum is not None:
        out = min(maximum, out)
    return out


def parse_float(
    value: Any,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        out = float(str(value))
    except Exception:
        out = default
    if minimum is not None:
        out = max(minimum, out)
    if maximum is not None:
        out = min(maximum, out)
    return out


def sanitize_filename(filename: str, fallback: str) -> str:
    raw = (filename or "").replace("\\", "/")
    name = raw.split("/")[-1].strip()
    if not name:
        name = fallback
    return name.replace("\x00", "")


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTS


def cleanup_old_jobs(max_age_hours: int = 12) -> None:
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    remove_targets: list[tuple[str, str]] = []

    with JOBS_LOCK:
        for job_id, job in list(JOBS.items()):
            if job.get("status") not in {"completed", "failed"}:
                continue
            updated_at = job.get("updated_at")
            try:
                updated_dt = datetime.fromisoformat(updated_at)
            except Exception:
                updated_dt = datetime.now()
            if updated_dt < cutoff:
                remove_targets.append((job_id, job.get("job_dir", "")))
                JOBS.pop(job_id, None)

    for _, job_dir in remove_targets:
        if not job_dir:
            continue
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
        except Exception:
            pass


def append_log(job_id: str, message: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        logs = job.setdefault("logs", [])
        logs.append(message)
        if len(logs) > MAX_LOG_LINES:
            del logs[: len(logs) - MAX_LOG_LINES]
        job["updated_at"] = now_iso()


def update_job(job_id: str, **fields: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = now_iso()



def get_client_ip() -> str:
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"

    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip

    return (request.remote_addr or "unknown").strip() or "unknown"


def record_visit() -> None:
    global VISITOR_TOTAL_VIEWS

    client_ip = get_client_ip()
    now = datetime.now()
    retention_cutoff = now - timedelta(days=VISITOR_RETENTION_DAYS)

    with VISITOR_LOCK:
        VISITOR_TOTAL_VIEWS += 1
        VISITOR_IP_LAST_SEEN[client_ip] = now

        stale_keys = [
            ip for ip, seen_at in VISITOR_IP_LAST_SEEN.items() if seen_at < retention_cutoff
        ]
        for ip in stale_keys:
            VISITOR_IP_LAST_SEEN.pop(ip, None)


def get_visitor_stats() -> dict[str, int]:
    now = datetime.now()
    active_cutoff = now - timedelta(minutes=VISITOR_ACTIVE_WINDOW_MINUTES)

    with VISITOR_LOCK:
        unique_visitors = len(VISITOR_IP_LAST_SEEN)
        active_visitors = sum(
            1 for seen_at in VISITOR_IP_LAST_SEEN.values() if seen_at >= active_cutoff
        )
        total_views = VISITOR_TOTAL_VIEWS

    return {
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "active_visitors": active_visitors,
        "active_window_minutes": VISITOR_ACTIVE_WINDOW_MINUTES,
    }
def parse_hex_color(text: str) -> tuple[int, int, int]:
    s = (text or "").strip()
    if not s:
        s = "#000000"
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        s = "000000"
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return 0, 0, 0


def apply_border(
    img: Image.Image,
    border_thickness: int,
    border_color: str,
    border_opacity: int,
) -> Image.Image:
    if border_thickness <= 0:
        return img

    alpha = max(0, min(100, int(border_opacity)))
    alpha = int(255 * (alpha / 100.0))

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    bt = max(1, int(border_thickness))
    new_w = w + bt * 2
    new_h = h + bt * 2

    r, g, b = parse_hex_color(border_color)
    base = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    border_layer = Image.new("RGBA", (new_w, new_h), (r, g, b, alpha))
    inner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    border_layer.paste(inner, (bt, bt))
    base = Image.alpha_composite(base, border_layer)
    base.paste(img, (bt, bt), img)
    return base


def process_single_image(
    src_path: Path,
    dst_dir: Path,
    suffix: str,
    use_meta: bool,
    use_crop: bool,
    crop_max: int,
    resize_factor: float,
    angle: float,
    use_noise: bool,
    noise_pct: int,
    bright_factor: float,
    sat_factor: float,
    output_ext: str | None,
    use_border: bool,
    border_thickness: int,
    border_color: str,
    border_opacity: int,
) -> tuple[int, int, int, int]:
    img = Image.open(src_path)

    if use_meta:
        img = img.convert("RGB")
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")

    w, h = img.size

    if resize_factor != 1.0 and w > 1 and h > 1:
        new_w = max(1, int(round(w * resize_factor)))
        new_h = max(1, int(round(h * resize_factor)))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = img.size

    if angle != 0.0:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
        w, h = img.size

        theta = math.radians(abs(angle))
        pad = int(math.ceil(max(w, h) * math.sin(theta))) + 2

        if pad * 2 < w and pad * 2 < h:
            img = img.crop((pad, pad, w - pad, h - pad))
            w, h = img.size

    used_left = used_right = used_top = used_bottom = 0
    if use_crop and crop_max > 0 and w > 2 * crop_max and h > 2 * crop_max:
        left_crop = random.randint(0, crop_max)
        right_crop = random.randint(0, crop_max)
        top_crop = random.randint(0, crop_max)
        bottom_crop = random.randint(0, crop_max)

        if w > left_crop + right_crop + 1 and h > top_crop + bottom_crop + 1:
            img = img.crop((left_crop, top_crop, w - right_crop, h - bottom_crop))
            w, h = img.size
            used_left, used_right, used_top, used_bottom = (
                left_crop,
                right_crop,
                top_crop,
                bottom_crop,
            )

    if use_noise and noise_pct > 0:
        noise = Image.effect_noise(img.size, 64).convert("L")
        alpha_value = int(255 * (noise_pct / 100.0) * 0.6)
        alpha_value = max(1, min(255, alpha_value))
        alpha_layer = Image.new("L", img.size, alpha_value)
        noise_rgba = Image.merge("RGBA", (noise, noise, noise, alpha_layer))
        base_rgba = img.convert("RGBA")
        img = Image.alpha_composite(base_rgba, noise_rgba).convert("RGB")
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")

    if sat_factor != 1.0:
        img = ImageEnhance.Color(img).enhance(sat_factor)
    if bright_factor != 1.0:
        img = ImageEnhance.Brightness(img).enhance(bright_factor)

    if use_border and border_thickness > 0:
        img = apply_border(
            img,
            border_thickness=border_thickness,
            border_color=border_color,
            border_opacity=border_opacity,
        )

    basename = src_path.name
    name, orig_ext = os.path.splitext(basename)
    ext = output_ext if output_ext else (orig_ext or ".jpg")
    dst_name = f"{name}_{suffix}{ext}" if suffix else f"{name}{ext}"
    dst_path = dst_dir / dst_name

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    save_kwargs = {}
    if ext.lower() in {".jpg", ".jpeg"}:
        save_kwargs["quality"] = 95

    img.save(dst_path, **save_kwargs)
    return used_left, used_right, used_top, used_bottom


def run_job(job_id: str, input_paths: list[Path], settings: dict[str, Any]) -> None:
    try:
        update_job(job_id, status="running")
        append_log(job_id, "=== 이미지 세탁 시작 ===")
        append_log(
            job_id,
            f"원본 {len(input_paths)}장 × {settings['per_src']}장씩 = 총 {len(input_paths) * settings['per_src']}장",
        )

        job_dir = Path(settings["job_dir"])
        output_dir = Path(settings["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        out_idx = 0
        total = len(input_paths) * settings["per_src"]

        for src_path in input_paths:
            basename = src_path.name
            for copy_idx in range(settings["per_src"]):
                suffix = str(copy_idx + 1)

                if settings["use_resize"] and settings["resize_r"] > 0:
                    mn = 100 - settings["resize_r"]
                    mx = 100 + settings["resize_r"]
                    resize_factor = random.uniform(mn / 100.0, mx / 100.0)
                else:
                    resize_factor = 1.0

                if settings["use_rotate"] and settings["rotate_r"] > 0:
                    angle = random.uniform(-settings["rotate_r"], settings["rotate_r"])
                else:
                    angle = 0.0

                if settings["use_color"] and settings["bright_r"] > 0:
                    b_delta = random.uniform(
                        -settings["bright_r"] / 100.0, settings["bright_r"] / 100.0
                    )
                    bright_factor = 1.0 + b_delta
                else:
                    bright_factor = 1.0

                if settings["use_color"] and settings["sat_r"] > 0:
                    s_delta = random.uniform(
                        -settings["sat_r"] / 100.0, settings["sat_r"] / 100.0
                    )
                    sat_factor = 1.0 + s_delta
                else:
                    sat_factor = 1.0

                if settings["use_noise"] and settings["max_noise_pct"] > 0:
                    noise_pct = random.randint(0, settings["max_noise_pct"])
                else:
                    noise_pct = 0

                if settings["use_border"]:
                    if settings["use_border_random"]:
                        max_th = (
                            settings["border_thickness_val"]
                            if settings["border_thickness_val"] > 0
                            else 10
                        )
                        bt = random.randint(1, max_th)
                        bo = random.randint(10, 100)
                        bc = "#{:02X}{:02X}{:02X}".format(
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255),
                        )
                    else:
                        bt = max(0, settings["border_thickness_val"])
                        bo = settings["border_opacity_val"]
                        bc = settings["border_color"]
                else:
                    bt = 0
                    bo = 0
                    bc = settings["border_color"]

                try:
                    used_left, used_right, used_top, used_bottom = process_single_image(
                        src_path=src_path,
                        dst_dir=output_dir,
                        suffix=suffix,
                        use_meta=settings["use_meta"],
                        use_crop=settings["use_crop"],
                        crop_max=settings["crop_max"],
                        resize_factor=resize_factor,
                        angle=angle,
                        use_noise=settings["use_noise"],
                        noise_pct=noise_pct,
                        bright_factor=bright_factor,
                        sat_factor=sat_factor,
                        output_ext=settings["output_ext"],
                        use_border=settings["use_border"],
                        border_thickness=bt,
                        border_color=bc,
                        border_opacity=bo,
                    )
                    append_log(
                        job_id,
                        f"[{out_idx + 1}/{total}] {basename}({suffix}) 완료 "
                        f"(crop L{used_left}/R{used_right}/T{used_top}/B{used_bottom} px, "
                        f"resize {resize_factor:.3f}x, rot {angle:.2f}°, "
                        f"noise {noise_pct if settings['use_noise'] else 0}%, "
                        f"bright {bright_factor:.3f}, sat {sat_factor:.3f})",
                    )
                except Exception as exc:
                    append_log(
                        job_id,
                        f"[{out_idx + 1}/{total}] {basename}({suffix}) 처리 중 오류: {exc}",
                    )

                out_idx += 1
                update_job(job_id, done=out_idx)

        zip_path = job_dir / "washed_images.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for output_file in sorted(output_dir.glob("*")):
                if output_file.is_file():
                    zip_file.write(output_file, arcname=output_file.name)

        append_log(job_id, "=== 이미지 세탁 완료 ===")
        update_job(job_id, status="completed", zip_path=str(zip_path))
    except Exception as exc:
        append_log(job_id, f"작업이 중단되었습니다: {exc}")
        update_job(job_id, status="failed", error=str(exc))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/x-icon")


@app.route("/")
def index():
    record_visit()
    return render_template("index.html", app_name=APP_DISPLAY_NAME)


@app.route("/api/owner/visitors", methods=["GET"])
def owner_visitor_stats():
    token = (request.args.get("token") or request.headers.get("X-Owner-Token") or "").strip()
    if token != OWNER_VISITOR_TOKEN:
        return jsonify({"error": "권한이 없습니다."}), 403
    return jsonify(get_visitor_stats())


@app.route("/api/jobs", methods=["POST"])
def create_job():
    cleanup_old_jobs()

    uploaded_files = [f for f in request.files.getlist("images") if f and f.filename]
    valid_files = [f for f in uploaded_files if is_allowed_file(f.filename)]
    if not valid_files:
        return jsonify({"error": "이미지 파일을 최소 1개 이상 선택해 주세요."}), 400

    per_src = parse_int(request.form.get("per_src"), 1, minimum=1, maximum=1000)
    crop_max = parse_int(request.form.get("crop_max"), 3, minimum=0, maximum=500)
    resize_r = parse_int(request.form.get("resize_r"), 2, minimum=0, maximum=50)
    rotate_r = parse_float(request.form.get("rotate_r"), 1.0, minimum=0.0, maximum=15.0)
    max_noise_pct = parse_int(
        request.form.get("max_noise_pct"), 8, minimum=0, maximum=100
    )
    bright_r = parse_int(request.form.get("bright_r"), 8, minimum=0, maximum=100)
    sat_r = parse_int(request.form.get("sat_r"), 12, minimum=0, maximum=100)
    border_thickness_val = parse_int(
        request.form.get("border_thickness"), 8, minimum=0, maximum=300
    )
    border_opacity_val = parse_int(
        request.form.get("border_opacity"), 100, minimum=0, maximum=100
    )
    border_color = (request.form.get("border_color") or "#000000").strip()

    fmt = (request.form.get("output_format") or "원본 유지").strip()
    output_ext = None
    if fmt == "JPG":
        output_ext = ".jpg"
    elif fmt == "PNG":
        output_ext = ".png"
    elif fmt == "WEBP":
        output_ext = ".webp"

    job_id = uuid.uuid4().hex
    job_dir = TEMP_ROOT / job_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_paths: list[Path] = []
    for idx, file in enumerate(valid_files, start=1):
        origin_name = sanitize_filename(file.filename, f"image_{idx}.jpg")
        stem = Path(origin_name).stem or f"image_{idx}"
        suffix = Path(origin_name).suffix or ".jpg"
        if suffix.lower() not in ALLOWED_EXTS:
            continue

        candidate = f"{stem}{suffix}"
        counter = 1
        while (input_dir / candidate).exists():
            candidate = f"{stem}_{counter}{suffix}"
            counter += 1

        save_path = input_dir / candidate
        file.save(save_path)
        input_paths.append(save_path)

    if not input_paths:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "지원 형식의 이미지가 없습니다."}), 400

    total_outputs = len(input_paths) * per_src
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "total": total_outputs,
            "done": 0,
            "logs": [],
            "error": None,
            "zip_path": None,
            "job_dir": str(job_dir),
            "output_dir": str(output_dir),
        }

    settings = {
        "per_src": per_src,
        "use_meta": parse_bool(request.form.get("use_meta"), True),
        "use_crop": parse_bool(request.form.get("use_crop"), True),
        "crop_max": crop_max,
        "use_resize": parse_bool(request.form.get("use_resize"), True),
        "resize_r": resize_r,
        "use_rotate": parse_bool(request.form.get("use_rotate"), True),
        "rotate_r": rotate_r,
        "use_noise": parse_bool(request.form.get("use_noise"), False),
        "max_noise_pct": max_noise_pct,
        "use_color": parse_bool(request.form.get("use_color"), False),
        "bright_r": bright_r,
        "sat_r": sat_r,
        "output_ext": output_ext,
        "use_border": parse_bool(request.form.get("use_border"), False),
        "use_border_random": parse_bool(request.form.get("use_border_random"), False),
        "border_thickness_val": border_thickness_val,
        "border_opacity_val": border_opacity_val,
        "border_color": border_color,
        "job_dir": str(job_dir),
        "output_dir": str(output_dir),
    }

    worker = threading.Thread(
        target=run_job, args=(job_id, input_paths, settings), daemon=True
    )
    worker.start()
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    start_index = parse_int(request.args.get("from"), 0, minimum=0)
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "작업을 찾을 수 없습니다."}), 404

        logs = job.get("logs", [])
        if start_index > len(logs):
            start_index = len(logs)

        response = {
            "id": job["id"],
            "status": job["status"],
            "total": job["total"],
            "done": job["done"],
            "error": job.get("error"),
            "download_ready": job["status"] == "completed" and bool(job.get("zip_path")),
            "logs": logs[start_index:],
            "log_index": len(logs),
        }
    return jsonify(response)


@app.route("/api/jobs/<job_id>/download", methods=["GET"])
def download_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "작업을 찾을 수 없습니다."}), 404
        if job.get("status") != "completed":
            return jsonify({"error": "작업이 아직 완료되지 않았습니다."}), 409
        zip_path = job.get("zip_path")
        if not zip_path or not os.path.exists(zip_path):
            return jsonify({"error": "결과 파일을 찾을 수 없습니다."}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"image_washer_result_{job_id[:8]}.zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    app.run(debug=True)




