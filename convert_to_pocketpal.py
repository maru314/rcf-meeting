"""
RCF ペルソナログ（配列形式）を PocketPal インポート形式に変換するスクリプト

使い方:
    python convert_to_pocketpal.py logs/エミ.json
    python convert_to_pocketpal.py logs/エミ.json --title "エミとの会議ログ"

出力: エミ_pocketpal.json（同ディレクトリに生成）
"""

import argparse
import json
import sys
import time
import random
from pathlib import Path

DEFAULT_COMPLETION_SETTINGS = {
    "version": 4,
    "include_thinking_in_context": True,
    "n_predict": -1,
    "temperature": 0.7,
    "top_k": 40,
    "top_p": 0.95,
    "min_p": 0.05,
    "xtc_threshold": 0.1,
    "xtc_probability": 0,
    "typical_p": 1,
    "penalty_last_n": 64,
    "penalty_repeat": 1,
    "penalty_freq": 0,
    "penalty_present": 0,
    "mirostat": 0,
    "mirostat_tau": 5,
    "mirostat_eta": 0.1,
    "seed": -1,
    "n_probs": 0,
    "jinja": True,
    "enable_thinking": False
}

def generate_id(length=16):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choices(chars, k=length))

def convert(input_path: Path, title: str = None, last: int = None) -> dict:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "messages" in data:
        print("[OK] Already PocketPal format. No conversion needed.")
        return data

    if not isinstance(data, list):
        print("[ERROR] Unknown format.")
        sys.exit(1)

    persona_name = input_path.stem
    session_title = title or f"{persona_name} ログ"
    session_id = generate_id()

    messages = []
    for entry in data:
        messages.append({
            "id": entry.get("id") or generate_id(),
            "author": entry.get("author", persona_name),
            "text": entry.get("text", ""),
            "type": entry.get("type", "text"),
            "createdAt": entry.get("createdAt", int(time.time() * 1000))
        })

    if last:
        messages = messages[-last:]

    return {
        "id": session_id,
        "title": session_title,
        "date": None,
        "messages": messages,
        "completionSettings": DEFAULT_COMPLETION_SETTINGS,
        "activePalId": None
    }

def main():
    parser = argparse.ArgumentParser(description="RCFペルソナログ → PocketPal形式変換")
    parser.add_argument("input", help="変換するJSONファイルのパス")
    parser.add_argument("--title", help="チャットタイトル（省略時はファイル名）")
    parser.add_argument("--last", type=int, default=None, help="末尾N件のメッセージのみ変換（省略時は全件）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)

    output_path = input_path.parent / f"{input_path.stem}_pocketpal.json"
    result = convert(input_path, args.title, last=args.last)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Conversion complete: {output_path}")
    print(f"   Message count: {len(result['messages'])}")

if __name__ == "__main__":
    main()
