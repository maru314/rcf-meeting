"""
ログビューア
ShareGPT形式のJSONログを読みやすく表示する。
\ne を実際の改行に変換する。

使い方:
    python view_log.py logs/クロ姐さん.json
    python view_log.py logs/meeting_20260515_211409.json
"""

import json
import sys
from pathlib import Path

# Windowsのコンソール出力をUTF-8に
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROLE_COLORS = {
    "user": "[U]",
    "assistant": "[A]",
    "system": "[S]",
}


def _view_pocketpal_log(data: dict):
    """新PocketPal互換フォーマット（messages配列）をコンソール表示。"""
    topic = data.get("topic") or data.get("title", "不明")
    created = data.get("created_at", "")
    messages = data.get("messages", [])

    print(f"\n{'═' * 60}")
    print(f"  議事録")
    print(f"{'═' * 60}")
    print(f"  トピック: {topic}")
    print(f"  作成: {created}")
    print(f"  メッセージ数: {len(messages)}")

    for m in messages:
        author = m.get("author", "?")
        text = m.get("text", "")
        msg_id = m.get("id", "")

        # ラウンド情報をIDから抽出（session_r1_エミ → R1）
        round_label = ""
        parts = msg_id.split("_r")
        if len(parts) >= 2:
            try:
                round_num = int(parts[-1].split("_")[0])
                round_label = f" R{round_num}"
            except ValueError:
                pass

        print(f"\n{'─' * 60}")
        print(f"  [{author}]{round_label}")
        print(f"{'─' * 60}")
        print(text)


def view_log(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 旧フォーマット（rounds配列）の場合
    if "rounds" in data:
        _view_meeting_minutes(data)
        return

    # 新フォーマット（messages配列）の場合
    if "messages" in data:
        _view_pocketpal_log(data)
        return

    # ペルソナ別ログ形式
    for entry in data:
        # 新フォーマット（PocketPal互換）
        if "author" in entry:
            name = entry.get("author", "?")
            content = entry.get("text", "")
            content = content.replace("\\n", "\n")
            print(f"\n{'─' * 60}")
            print(f"  [{name}]")
            print(f"{'─' * 60}")
            print(content)
        # 旧フォーマット（ShareGPT）
        else:
            role = entry.get("role", "?")
            content = entry.get("content", "")
            content = content.replace("\\n", "\n")
            icon = ROLE_COLORS.get(role, "❓")
            print(f"\n{'─' * 60}")
            print(f"  {icon} [{role.upper()}]")
            print(f"{'─' * 60}")
            print(content)


def _view_meeting_minutes(data: dict):
    topic = data.get("topic") or data.get("title", "不明")
    created = data.get("created_at", "")
    rounds = data.get("rounds", [])

    print(f"\n{'═' * 60}")
    print(f"  議事録")
    print(f"{'═' * 60}")
    print(f"  トピック: {topic}")
    print(f"  作成: {created}")
    print(f"  ラウンド数: {len(rounds)}")

    for r in rounds:
        round_num = r.get("round", "?")
        maru_input = r.get("user_input") or r.get("input", "")
        summary = r.get("summary", "")
        responses = r.get("responses", {})
        if isinstance(responses, list):
            items = [(resp.get("name", "?"), resp.get("content", "")) for resp in responses]
        else:
            items = list(responses.items())

        print(f"\n{'─' * 60}")
        print(f"  🔄 ラウンド {round_num}")
        print(f"{'─' * 60}")
        print(f"  [マル]\n{maru_input}")

        for name, content in items:
            content = content.replace("\\n", "\n")
            print(f"\n  [{name}]\n{content}")

        if summary:
            print(f"\n  [要約]\n{summary}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"ファイルが見つかりません: {filepath}")
        sys.exit(1)

    view_log(filepath)
