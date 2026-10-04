"""Hang doi san xuat Seedance 2.5 — Holetex x BytePlus.

Doc moi file queue/*.json (moi file = 1 tap phim), gui task len ModelArk
theo so luong dong thoi cho phep, giu phan con lai, polling trang thai,
tu tai video ve output/<tap>/ va in bang trang thai co task ID.

File them vao thu muc queue/ trong luc dang chay se tu duoc nhan.

Cach chay:
  uv run --no-project python hang_doi.py              # chay hang doi
  uv run --no-project python hang_doi.py --max 3      # gioi han dong thoi
  uv run --no-project python hang_doi.py --dry-run    # chi in payload, khong goi API
  uv run --no-project python hang_doi.py --test       # 1 task 4s 480p de test (rat it token)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / "ark" / ".env"
QUEUE_DIR = ROOT / "queue"
OUT_DIR = ROOT / "output"
STATE_FILE = OUT_DIR / "state.json"
USAGE_FILE = OUT_DIR / "usage.csv"
MODEL = "dreamina-seedance-2-5-260628"
POLL_SECONDS = 5
PRICE_PLAN = 6.40   # USD / 1M token, Resource Plan
PRICE_PAYG = 10.70  # USD / 1M token, tra le


def load_env() -> tuple[str, str]:
    key, base = "", "https://ark.ap-southeast.bytepluses.com/api/v3"
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("BYTEPLUS_MODELARK_API_KEY="):
                key = line.split("=", 1)[1].strip()
            elif line.startswith("BYTEPLUS_MODELARK_BASE_URL="):
                base = line.split("=", 1)[1].strip() or base
    key = os.environ.get("BYTEPLUS_MODELARK_API_KEY", key)
    if not key:
        sys.exit(f"Chua co API key. Mo {ENV_FILE} va dan key vao dong BYTEPLUS_MODELARK_API_KEY=")
    return key, base.rstrip("/")


class Api:
    def __init__(self, key: str, base: str):
        self.key, self.base = key, base

    def _req(self, method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            raise ApiError(e.code, msg) from None

    def create(self, payload: dict) -> dict:
        return self._req("POST", "/contents/generations/tasks", payload)

    def get(self, task_id: str) -> dict:
        return self._req("GET", f"/contents/generations/tasks/{task_id}")

    def image(self, payload: dict) -> dict:
        # Seedream Pro mat 60-150 giay moi anh -> cho toi 10 phut
        return self._req("POST", "/images/generations", payload, timeout=600)


class ApiError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(f"HTTP {code}: {msg[:300]}")
        self.code, self.msg = code, msg

    @property
    def is_limit(self) -> bool:
        m = self.msg.lower()
        return self.code == 429 or "concurren" in m or "ratelimit" in m or "rate limit" in m or "quota" in m and "exceed" in m


def image_ref(src: str) -> str:
    """URL giu nguyen; duong dan file trong may -> data URL base64 (khong can host anh)."""
    if src.startswith(("http://", "https://", "data:", "asset://")):
        return src
    import base64, mimetypes
    path = (ROOT / src) if not os.path.isabs(src) else Path(src)
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def video_ref(api: "Api | None", src: str) -> str:
    """'task:<id>' -> link video cua task do (song 24 gio)."""
    if src.startswith("task:") and api is not None:
        r = api.get(src[5:])
        u = (r.get("content") or {}).get("video_url")
        return u.get("url") if isinstance(u, dict) else u
    return src


API_FOR_REFS = None


def build_payload(ep: dict, sc: dict) -> dict:
    content = [{"type": "text", "text": sc["prompt"]}]
    for src in sc.get("images", []) or []:
        content.append({"type": "image_url", "image_url": {"url": image_ref(src)}, "role": "reference_image"})
    for src in sc.get("videos", []) or []:
        content.append({"type": "video_url", "video_url": {"url": video_ref(API_FOR_REFS, src)}, "role": "reference_video"})
    p = {
        "model": ep.get("model", MODEL),
        "content": content,
        "ratio": sc.get("ratio", ep.get("ratio", "16:9")),
        "duration": int(sc.get("duration", ep.get("duration", 5))),
        "resolution": sc.get("resolution", ep.get("resolution", "480p")),
        "generate_audio": bool(sc.get("generate_audio", ep.get("generate_audio", True))),
        "watermark": False,
    }
    for k in ("draft", "omni_reference_task_type", "seed"):
        if k in sc:
            p[k] = sc[k]
    if sc.get("videos") and sc.get("omni_reference_task_type") in ("edit", "edit_video"):
        p.pop("ratio", None)
        p["duration"] = -1
    return p


def load_queue() -> list[tuple[dict, dict]]:
    rows = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            ep = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # file dang duoc luu do, lan sau doc lai
        ep.setdefault("episode", f.stem)
        for sc in ep.get("scenes", []):
            rows.append((ep, sc))
    return rows


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(st: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)


def log_usage(key: str, info: dict) -> None:
    new = not USAGE_FILE.exists()
    with open(USAGE_FILE, "a", encoding="utf-8") as f:
        if new:
            f.write("time,scene,task_id,resolution,duration,total_tokens\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S},{key},{info.get('task_id')},"
                f"{info.get('resolution')},{info.get('duration')},{info.get('tokens')}\n")


def render(st: dict, rows: list, started: float, limit: int) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    el = int(time.time() - started)
    print(f"  SEEDANCE 2.5 · HANG DOI SAN XUAT      dong ho {el // 60:02d}:{el % 60:02d}      dong thoi toi da: {limit}\n")
    print(f"  {'CANH':<22}{'TASK ID':<28}{'TRANG THAI':<13}{'TOKEN':>10}  FILE")
    print("  " + "-" * 92)
    done = tok = 0
    for ep, sc in rows:
        k = f"{ep['episode']}/{sc['id']}"
        s = st.get(k, {})
        status = s.get("status", "waiting")
        if status == "succeeded":
            done += 1
        tok += s.get("tokens") or 0
        f = s.get("file", "")
        print(f"  {k:<22}{s.get('task_id', '-'):<28}{status:<13}{(s.get('tokens') or ''):>10}  {f}")
        if s.get("error"):
            print(f"      LOI: {s['error'][:300]}")
    print("  " + "-" * 92)
    print(f"  Xong {done}/{len(rows)} canh · tong token {tok:,} · goi ~{tok / 1e6 * PRICE_PLAN:.2f} USD"
          f" · tra le ~{tok / 1e6 * PRICE_PAYG:.2f} USD")


def run(api: Api | None, limit: int, dry: bool) -> None:
    st = load_state()
    # canh loi lan truoc -> cho gui lai
    st = {k: v for k, v in st.items() if v.get("status") not in ("failed", "dry-run")}
    started = time.time()
    while True:
        rows = load_queue()
        if not rows:
            print("Thu muc queue/ trong."); return
        active = [k for k, v in st.items() if v.get("status") in ("queued", "running", "submitted")]
        # gui task moi khi con slot
        for ep, sc in rows:
            k = f"{ep['episode']}/{sc['id']}"
            if k in st or len(active) >= limit:
                continue
            try:
                payload = build_payload(ep, sc)
            except FileNotFoundError as e:
                st[k] = {"status": "failed", "error": f"Thieu file anh: {e.filename}"}
                continue
            if dry:
                shown = json.loads(json.dumps(payload))
                for c in shown["content"]:
                    for f in ("image_url", "video_url"):
                        if f in c and c[f]["url"].startswith("data:"):
                            c[f]["url"] = c[f]["url"][:40] + "...(base64)"
                print(f"\n[{k}] payload:\n" + json.dumps(shown, ensure_ascii=False, indent=2))
                st[k] = {"status": "dry-run"}
                continue
            try:
                r = api.create(payload)
                st[k] = {"task_id": r.get("id"), "status": "submitted", "resolution": payload["resolution"],
                         "duration": payload["duration"], "t0": time.time()}
                active.append(k)
            except ApiError as e:
                if e.is_limit:
                    limit = max(1, len(active))  # gioi han that cua tai khoan
                    break
                st[k] = {"status": "failed", "error": str(e)}
            save_state(st)
        if dry:
            return
        # polling
        for k in list(active):
            s = st[k]
            try:
                r = api.get(s["task_id"])
            except ApiError as e:
                s["error"] = str(e); continue
            s["status"] = r.get("status", s["status"])
            if s["status"] == "succeeded":
                s["tokens"] = (r.get("usage") or {}).get("total_tokens")
                url = (r.get("content") or {}).get("video_url")
                if isinstance(url, dict):
                    url = url.get("url")
                ep_name, scene = k.split("/", 1)
                dest = OUT_DIR / ep_name / f"{scene}.mp4"
                try:
                    download(url, dest)
                    s["file"] = str(dest.relative_to(ROOT))
                except Exception as e:  # noqa: BLE001
                    s["file"] = f"LOI TAI: {e}"
                s["video_url"] = url
                s["secs"] = int(time.time() - s.get("t0", time.time()))
                log_usage(k, s)
            elif s["status"] in ("failed", "expired", "cancelled"):
                s["error"] = json.dumps(r.get("error"), ensure_ascii=False)
            save_state(st)
        render(st, rows, started, limit)
        pending = [1 for ep, sc in rows if f"{ep['episode']}/{sc['id']}" not in st]
        still = [k for k, v in st.items() if v.get("status") in ("queued", "running", "submitted")]
        if not pending and not still:
            print("\n  Xong ca hang doi. Them file vao queue/ roi chay lai neu can.")
            return
        time.sleep(POLL_SECONDS)


def make_images(api: "Api") -> None:
    """Sinh anh tham chieu bang Seedream tu nhan-vat/prompt-anh.json -> nhan-vat/<ten>.png"""
    spec = json.loads((ROOT / "nhan-vat" / "prompt-anh.json").read_text(encoding="utf-8"))
    out = ROOT / "nhan-vat"
    out.mkdir(parents=True, exist_ok=True)
    for it in spec["images"]:
        dest = out / f"{it['name']}.png"
        if dest.exists():
            print(f"  da co {dest.name}, bo qua"); continue
        print(f"  dang sinh {dest.name} (Seedream mat 1-3 phut moi anh, cu de yen) ...", flush=True)
        body = {"model": spec.get("model", "dola-seedream-5-0-pro-260628"), "prompt": it["prompt"],
                "size": it.get("size", spec.get("size", "2048x1152")), "response_format": "url", "watermark": False}
        try:
            r = api.image(body)
        except Exception as e:  # noqa: BLE001
            print(f"  LOI {dest.name}: {e}"); continue
        url = r["data"][0]["url"]
        download(url, dest)
        print(f"  xong {dest.name}  (usage: {r.get('usage')})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=3, help="so task dong thoi toi da")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true", help="chay cac file trong test/")
    ap.add_argument("--anh", action="store_true", help="sinh anh tham chieu tu nhan-vat/prompt-anh.json")
    a = ap.parse_args()
    if a.anh:
        make_images(Api(*load_env())); return
    if a.test:
        global QUEUE_DIR, STATE_FILE
        global OUT_DIR, USAGE_FILE
        QUEUE_DIR = ROOT / "_rieng-tu" / "test"
        OUT_DIR = ROOT / "_rieng-tu" / "test-output"
        STATE_FILE = ROOT / "_rieng-tu" / "state-test.json"
        USAGE_FILE = OUT_DIR / "usage.csv"
    api = None if a.dry_run else Api(*load_env())
    global API_FOR_REFS
    API_FOR_REFS = api
    run(api, a.max, a.dry_run)


if __name__ == "__main__":
    main()
