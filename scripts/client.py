"""One submission per job. Resume uses only GET requests."""
import argparse
import base64
import json
import hashlib
import hmac
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit

import accounts
import requests
from media_names import media_kind

HOSTS = {"main": "https://api.gaoxin.net.cn", "sh": "https://api-sh.gaoxin.net.cn"}
PENDING = {"created", "pending", "queued", "submitted", "processing", "running", "in_progress"}
DONE = {"completed", "succeeded", "success"}


def protocol(model):
    if model in ("MiniMax-H3", "FastH3-Omni"):
        return "h3"
    if re.fullmatch(r"(?:doubao-)?seedance[-.][a-z0-9.-]+", model, re.I):
        return "seedance"
    return None


def candidates(session, base):
    r = session.get(base + "/v1/models", timeout=(5, 25), allow_redirects=False)
    r.raise_for_status()
    items = []
    for row in r.json()["data"]:
        name = row["id"]
        adapter = protocol(name)
        if adapter or media_kind(name) == "video" or "video" in (row.get("output_modalities") or []):
            items.append({"model": name, "adapter": adapter})
    return items


def payload(job):
    name = job["model"]
    kind = protocol(name)
    if not kind:
        raise ValueError("unmapped_model")
    prompt = job["prompt"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt_required")
    seconds = int(job.get("seconds", 5))
    if seconds < 1:
        raise ValueError("invalid_duration")
    ratio = job.get("ratio", "16:9")
    body = {"model": name, "prompt": prompt}
    frame = job.get("first_frame")
    if name == "FastH3-Omni":
        if not frame:
            raise ValueError("first_frame_required")
        data = Path(frame).read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif data.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            raise ValueError("expected_png_or_jpeg")
        body.update(first_frame="data:" + mime + ";base64," + base64.b64encode(data).decode(), workflow_type="i2v")
    elif frame:
        raise ValueError("first_frame_not_configured_for_this_adapter")
    if kind == "h3":
        body.update(seconds=str(seconds), resolution=job.get("resolution", "768P"), ratio=ratio, prompt_polish=False)
        return "/videos", body
    body.update(seconds=seconds, metadata={"ratio": ratio, "resolution": job.get("resolution", "720p")})
    return "/v1/videos", body


def write(path, obj):
    tmp = path.with_name(uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def output(job):
    directory = Path(job.get("output_dir", "outputs/video")).resolve()
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    path = Path(job["output_path"]) if job.get("output_path") else directory / job.get("filename", "视频-" + stamp + ".mp4")
    path = path.resolve()
    if path.suffix.lower() != ".mp4":
        raise ValueError("expected_mp4_output")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path = path.with_stem(path.stem + "-" + stamp)
    return path


def finish(session, record, state, reply=None):
    if state.get("status") == "saved" and Path(state["path"]).is_file():
        return state
    host = HOSTS[state["gateway"]]
    collection = "/videos" if protocol(state["model"]) == "h3" else "/v1/videos"
    endpoint = host + collection + "/" + quote(state["id"], safe="")
    deadline = time.monotonic() + 1800
    while True:
        if reply is None:
            r = session.get(endpoint, timeout=(10, 60), allow_redirects=False)
            r.raise_for_status()
            reply = r.json()
        status = str(reply.get("status", "")).lower()
        if status in DONE:
            break
        if status not in PENDING and status:
            state.update(status="stopped", upstream_status=status)
            write(record, state)
            return state
        if time.monotonic() >= deadline:
            return state
        time.sleep(5)
        reply = None
    content = reply.get("content")
    url = reply.get("video_url") or (content.get("video_url") if isinstance(content, dict) else None)
    with requests.Session() as storage:
        storage.trust_env = False
        if url:
            if urlsplit(url).scheme != "https":
                raise ValueError("invalid_download_url")
            r = storage.get(url, stream=True, timeout=(10, 150), allow_redirects=False)
        else:
            r = session.get(endpoint + "/content", stream=True, timeout=(10, 150), allow_redirects=False)
        if r.is_redirect:
            location = r.headers.get("Location", "")
            r.close()
            if urlsplit(location).scheme != "https":
                raise ValueError("invalid_download_redirect")
            r = storage.get(location, stream=True, timeout=(10, 150), allow_redirects=False)
        with r:
            if r.status_code != 200:
                raise ValueError("download_http_" + str(r.status_code))
            path = Path(state["path"])
            tmp = record.parent / (uuid.uuid4().hex + ".mp4")
            try:
                with tmp.open("xb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                with tmp.open("rb") as f:
                    if f.read(12)[4:8] != b"ftyp":
                        raise ValueError("invalid_mp4")
                if shutil.which("ffprobe"):
                    check = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_type","-of","csv=p=0",str(tmp)],capture_output=True,timeout=60)
                    if check.returncode or b"video" not in check.stdout:
                        raise ValueError("missing_video_stream")
                while True:
                    try:
                        os.link(tmp, path)
                        break
                    except FileExistsError:
                        path = path.with_stem(path.stem + "-" + uuid.uuid4().hex[:8])
                state.update(status="saved", path=str(path), bytes=tmp.stat().st_size)
                write(record, state)
            finally:
                tmp.unlink(missing_ok=True)
    return state


def run(a):
    if a.command == "profiles":
        found, notices = accounts.discover()
        found.update(byok={"label":"本次直接提供 Key","source":"stdin"})
        if os.getenv("GAOXIN_API_KEY"):
            found["environment"] = {"label":"GAOXIN_API_KEY","source":"environment"}
        return {"profiles":found,"notices":notices}
    state = {}
    job = {}
    if a.command == "resume":
        record = Path(a.record)
        state = json.loads(record.read_text(encoding="utf-8"))
    elif a.command == "generate":
        job = json.loads(Path(a.job).read_text(encoding="utf-8-sig"))
    requested = getattr(a, "profile", None)
    recorded = state.get("profile", "environment") if state else job.get("profile")
    if requested and recorded and requested != recorded:
        raise ValueError("conflicting_credential_source")
    ref = recorded or requested or "environment"
    key = os.getenv("GAOXIN_API_KEY") if ref == "environment" else accounts.resolve(ref)
    if not key:
        raise ValueError("choose_credential_source")
    fingerprint = hashlib.sha256(("videogen-task-key:" + key).encode()).hexdigest() if ref == "byok" else None
    if state.get("byok_fingerprint") and not hmac.compare_digest(state["byok_fingerprint"], fingerprint or ""):
        raise ValueError("resume_requires_original_byok")
    with requests.Session() as session:
        session.trust_env = False
        session.headers["Authorization"] = "Bearer " + key
        if a.command == "models":
            return {"models": candidates(session, HOSTS[a.gateway])}
        if a.command == "resume":
            if not state.get("id"):
                raise ValueError("no_task_id_check_gateway_before_resubmission")
            return finish(session, record, state)
        base = HOSTS[job["gateway"]]
        route, body = payload(job)
        if job["model"] not in [x["model"] for x in candidates(session, base)]:
            raise ValueError("selected_model_unavailable")
        path = output(job)
        task = path.parent / ".video-tasks" / uuid.uuid4().hex
        task.mkdir(parents=True)
        record = task / "record.json"
        state = dict(status="result_unknown", profile=ref, gateway=job["gateway"], model=job["model"], path=str(path), record=str(record))
        if fingerprint:
            state["byok_fingerprint"] = fingerprint
        write(record,state)
        print(json.dumps({"record": str(record)},ensure_ascii=True),flush=True)
        r = session.post(base + route, json=body, timeout=(10, 600), allow_redirects=False)
        if 400 <= r.status_code < 500:
            state.update(status="rejected",http_status=r.status_code)
            write(record,state)
            return state
        r.raise_for_status()
        reply = r.json()
        task_id = reply.get("id") or reply.get("task_id")
        if not isinstance(task_id,str) or not task_id:
            raise ValueError("missing_task_id_result_unknown")
        state.update(id=task_id,status="submitted")
        write(record,state)
        return finish(session, record, state, reply)


def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="command",required=True)
    subs.add_parser("profiles")
    subs.add_parser("models").add_argument("--gateway",choices=HOSTS,default="main")
    subs.add_parser("generate").add_argument("--job",required=True)
    subs.add_parser("resume").add_argument("--record",required=True)
    for name in ("models", "generate", "resume"):
        subs.choices[name].add_argument("--profile")
    try:
        result = run(p.parse_args())
    except Exception as exc:
        result = {"status":"failed","error":str(exc) if type(exc) is ValueError and re.fullmatch("[a-zA-Z0-9_]+",str(exc)) else type(exc).__name__}
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            result["http_status"] = exc.response.status_code
    print(json.dumps(result,ensure_ascii=True))
    return 0 if result.get("status")=="saved" or "models" in result or "profiles" in result else 1


if __name__=="__main__":
    raise SystemExit(main())
