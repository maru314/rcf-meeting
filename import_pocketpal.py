"""
PocketPal の会話エクスポート JSON を
RCF ペルソナログ（PocketPal 互換形式）へ追記するスクリプト

使い方:
    python import_pocketpal.py chat_xxx.json エミ
"""

import argparse
import json
import re
import time
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"


def strip_thoughts(text: str) -> str:
    """<think>...</think> タグを除去する"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def main():
    parser = argparse.ArgumentParser(
        description="PocketPal chat JSON を RCF ペルソナログへ追記"
    )
    parser.add_argument("json_file", help="インポート対象の PocketPal JSON ファイル")
    parser.add_argument(
        "persona_name", help="追記先のペルソナ名（logs/[名前].json）"
    )
    args = parser.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    if not messages:
        print("messages が空です。")
        return

    # author の種類をカウントして多い方を AI と判定
    author_counts: dict[str, int] = {}
    for m in messages:
        a = m.get("author", "")
        author_counts[a] = author_counts.get(a, 0) + 1

    if len(author_counts) < 2:
        print("author が1種類しか見つかりません。")
        return

    ai_author = max(author_counts, key=author_counts.get)
    print(f"  AI作者ID: {ai_author}")

    # 既存のペルソナログを読み込む
    persona_file = LOGS_DIR / f"{args.persona_name}.json"
    persona_file.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = (
        json.load(open(persona_file, "r", encoding="utf-8"))
        if persona_file.exists()
        else []
    )

    # 重複チェック用のタイムスタンプセット
    existing_ts = {m.get("createdAt") for m in existing if m.get("createdAt")}
    imported_count = 0

    for m in messages:
        # AI の発言のみ対象
        if m.get("author") != ai_author:
            continue

        ts = m.get("createdAt")
        if ts in existing_ts:
            continue

        text = strip_thoughts(m.get("text", ""))
        if not text:
            continue

        existing.append(
            {
                "id": f"imported_{ts}_{int(time.time() * 1000)}",
                "author": args.persona_name,
                "text": text,
                "type": "text",
                "createdAt": ts,
            }
        )
        existing_ts.add(ts)
        imported_count += 1

    with open(persona_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  {args.persona_name}.json に {imported_count} 件追記完了")


if __name__ == "__main__":
    main()