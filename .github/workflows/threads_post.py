"""매일 posts.csv에서 오늘(한국시간) 날짜의 글을 찾아 Threads에 게시합니다.

환경변수
  THREADS_ACCESS_TOKEN  Threads 장기 액세스 토큰 (필수)
  THREADS_USER_ID       Threads 사용자 ID (필수)
  PRODUCT_LINK          구매 링크. 댓글의 {link} 자리에 들어갑니다 (선택)
  POST_DATE             특정 날짜 글을 올릴 때 YYYY-MM-DD (선택, 테스트용)
  DRY_RUN=1             실제 게시 없이 어떤 글이 올라갈지 출력만 (선택)
"""
import csv
import datetime
import os
import sys
import time
from zoneinfo import ZoneInfo

import requests

API = "https://graph.threads.net/v1.0"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts.csv")
MAX_LEN = 500


def publish(user_id, token, text, reply_to=None):
    data = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to:
        data["reply_to_id"] = reply_to
    r = requests.post(f"{API}/{user_id}/threads", data=data, timeout=30)
    if not r.ok:
        sys.exit(f"컨테이너 생성 실패: {r.status_code} {r.text}")
    creation_id = r.json()["id"]
    time.sleep(10)  # Threads 권장: 생성 후 잠시 대기 후 게시
    r = requests.post(
        f"{API}/{user_id}/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if not r.ok:
        sys.exit(f"게시 실패: {r.status_code} {r.text}")
    return r.json()["id"]


def main():
    today = os.environ.get("POST_DATE") or datetime.datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d")
    dry = os.environ.get("DRY_RUN") == "1"
    link = os.environ.get("PRODUCT_LINK", "").strip()

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["date"].strip() == today]
    if not rows:
        print(f"{today} 예정된 글이 없습니다. 종료.")
        return

    row = rows[0]
    text = row["text"].strip()
    reply = (row.get("reply") or "").strip()

    if text.startswith("["):
        print(f"{today} 글에 교체할 자리표시([...])가 남아 있어 건너뜁니다.")
        return
    # reply 칸은 '---' 한 줄로 나누면 여러 개의 이어지는 답글(연재)이 됩니다.
    parts = []
    for p in reply.replace("\r\n", "\n").split("\n---\n"):
        p = p.strip()
        if "{link}" in p:
            p = p.replace("{link}", link) if link else ""
        if p:
            parts.append(p)
    for t in [text] + parts:
        if len(t) > MAX_LEN:
            sys.exit(f"{today} 글 중 {MAX_LEN}자를 넘는 칸이 있습니다. posts.csv를 줄여주세요.")

    print(f"[{today}] 본문 {len(text)}자\n{text}\n")
    for i, p in enumerate(parts, 2):
        print(f"[이어지는 글 {i}/{len(parts) + 1}]\n{p}\n")
    if dry:
        print("DRY_RUN: 실제로 게시하지 않았습니다.")
        return

    token = os.environ["THREADS_ACCESS_TOKEN"]
    user_id = os.environ["THREADS_USER_ID"]
    prev_id = publish(user_id, token, text)
    print(f"본문 게시 완료: {prev_id}")
    for p in parts:
        time.sleep(30)
        prev_id = publish(user_id, token, p, reply_to=prev_id)
        print(f"이어지는 글 게시 완료: {prev_id}")


if __name__ == "__main__":
    main()
