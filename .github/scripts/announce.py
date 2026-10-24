"""TUNEFALL 업데이트 공지를 디스코드 웹훅으로 보내요.

- version.txt 에서 지금 버전을 읽고
- 패치노트.txt 에서 그 버전 내용만 뽑아서 (홈페이지·게임과 같은 규칙)
- '업데이트 알림' 역할만 호출하면서 공지 채널에 올려요.

웹훅 주소(DISCORD_ANNOUNCE_WEBHOOK)와 역할 ID(DISCORD_ANNOUNCE_ROLE_ID)는
GitHub Secrets 에서 받아와요. 웹훅 주소가 없으면 보낼 내용만 화면에 보여줘요(시험용).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOMEPAGE_URL = "https://hyunmu-rhythm.github.io/tunefall/"
EMBED_COLOR = 0x6FD3FF
MAX_DESCRIPTION = 4000  # 디스코드 제한(4096)보다 조금 여유 있게


def read_text(path: str) -> str:
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def parse_patch_notes(text: str) -> list:
    """패치노트.txt 양식: [ v1.2.0 ] 2026-10-11 / - 분류 / · 항목 / ==== 구분선"""
    versions = []
    cur = None
    group = None
    for raw in text.replace("\r", "").split("\n"):
        t = raw.strip()
        if not t:
            continue
        if re.fullmatch(r"=+", t):  # 구분선: 다음 버전으로
            cur, group = None, None
            continue
        if cur is None:  # 구분선 다음 첫 줄은 버전 제목
            m = re.match(r"^\[\s*v?([\w.]+)\s*\]\s*(\S*)", t)
            if m:
                cur = {"version": m.group(1), "date": m.group(2), "groups": []}
                versions.append(cur)
            continue
        if t.startswith("·"):  # 세부 항목
            if group is None:
                group = {"title": "", "items": []}
                cur["groups"].append(group)
            group["items"].append(t.lstrip("·").strip())
        elif t.startswith("-"):  # 분류
            group = {"title": t.lstrip("-").strip(), "items": []}
            cur["groups"].append(group)
        elif group is not None and group["items"]:  # 앞 항목에 이어지는 줄
            group["items"][-1] += " " + t
        elif group is not None:
            group["title"] += " " + t
    return versions


def build_description(v: dict) -> str:
    parts = []
    for g in v["groups"]:
        lines = []
        if g["title"]:
            lines.append(f"**{g['title']}**")
        lines += [f"• {item}" for item in g["items"]]
        parts.append("\n".join(lines))
    text = "\n\n".join(parts) or "자세한 내용은 홈페이지에서 확인해주세요."
    if len(text) > MAX_DESCRIPTION:
        text = text[:MAX_DESCRIPTION].rsplit("\n", 1)[0] + "\n…(전체 내용은 홈페이지에서 볼 수 있어요)"
    return text


def main():
    version = read_text("version.txt").strip().lstrip("v")
    versions = parse_patch_notes(read_text("패치노트.txt"))
    if not versions:
        sys.exit("패치노트.txt 에서 버전 내용을 찾지 못했어요.")

    note = next((v for v in versions if v["version"] == version), None)
    if note is None:
        print(f"경고: 패치노트.txt 에 v{version} 내용이 없어서 가장 최신 내용을 보내요.")
        note = versions[0]

    role_id = os.environ.get("DISCORD_ANNOUNCE_ROLE_ID", "").strip()
    title = f"TUNEFALL v{note['version']} 업데이트"
    payload = {
        "username": "TUNEFALL",
        "content": (f"<@&{role_id}> " if role_id else "") + f"**{title}** 소식이에요!",
        "embeds": [{
            "title": title + (f"  ·  {note['date']}" if note["date"] else ""),
            "url": HOMEPAGE_URL + "#patchnotes",
            "description": build_description(note),
            "color": EMBED_COLOR,
            "footer": {"text": "게임을 켜면 자동으로 업데이트돼요"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        # '업데이트 알림' 역할만 울리게 해요 (@everyone 이나 다른 멘션은 울리지 않아요)
        "allowed_mentions": {"parse": [], "roles": [role_id] if role_id else []},
    }

    webhook = os.environ.get("DISCORD_ANNOUNCE_WEBHOOK", "").strip()
    if not webhook:
        print("웹훅 주소가 없어서 보내지 않았어요. 보낼 내용은 아래와 같아요:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "TUNEFALL-Announcer (https://github.com/hyunmu-rhythm/tunefall, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            print(f"공지 완료! (v{note['version']}, 응답 {res.status})")
    except urllib.error.HTTPError as e:
        sys.exit(f"공지 실패: HTTP {e.code} {e.read().decode('utf-8', 'ignore')}")


if __name__ == "__main__":
    main()
