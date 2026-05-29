"""
議事録ビューア（HTML出力）

使い方:
    python view_meeting.py logs/meeting_20260515_211409.json
    python view_meeting.py logs/meeting_20260515_211409.json --format chat
    python view_meeting.py logs/meeting_20260515_211409.json --format transcript
    python view_meeting.py logs/meeting_20260515_211409.json --format script

--format デフォルト: chat（吹き出しカード）
  transcript: [名前] 形式の文字起こし風
  script:     名前 「発言」 形式の台本風
"""

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path


PERSONA_COLORS = {
    "エミ": "#4fc3f7",
    "チャッピー司令": "#ffb74d",
    "クロ姐さん": "#ce93d8",
    "ジュリー": "#81c784",
}


def convert_messages_to_rounds(messages: list, captain_name: str = "マル") -> list:
    """PocketPal互換のmessages配列を旧rounds形式に変換。"""
    rounds: dict[int, dict] = {}
    for m in messages:
        msg_id = m.get("id", "")
        parts = msg_id.split("_r")
        if len(parts) < 2:
            continue
        round_part = parts[-1].split("_", 1)
        try:
            round_num = int(round_part[0])
        except ValueError:
            continue
        name = round_part[1] if len(round_part) > 1 else "?"

        if round_num not in rounds:
            rounds[round_num] = {"round": round_num, "user_input": "", "responses": {}, "summary": ""}

        if name == "maru" or m.get("author") == captain_name:
            rounds[round_num]["user_input"] = m.get("text", "")
        elif name == "summary" or m.get("author") == "議場":
            rounds[round_num]["summary"] = m.get("text", "")
        else:
            rounds[round_num]["responses"][m.get("author", name)] = m.get("text", "")

    return [rounds[k] for k in sorted(rounds.keys())]


def normalize_data(data: dict) -> dict:
    """旧format(rounds)と新format(messages)を自動判定して統一。"""
    if "rounds" in data:
        return data
    messages = data.get("messages", [])
    if not messages:
        return data
    captain = data.get("captain_name", "マル")
    data["rounds"] = convert_messages_to_rounds(messages, captain)
    return data


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_content(text: str) -> str:
    """\n → <br>、行頭の* → <li>、** → 太字など。"""
    lines = text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("*   "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = stripped[4:]
            content = content.replace("**", "")
            html_lines.append(f"<li>{escape_html(content)}</li>")
            continue
        elif in_list and not stripped.startswith("*   "):
            html_lines.append("</ul>")
            in_list = False

        if stripped.startswith("### "):
            html_lines.append(f"<h3>{escape_html(stripped[4:])}</h3>")
            continue

        if "**" in stripped:
            parts = stripped.split("**")
            escaped = []
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    escaped.append(f"<strong>{escape_html(part)}</strong>")
                else:
                    escaped.append(escape_html(part))
            html_lines.append(f"<p>{''.join(escaped)}</p>")
            continue

        if stripped:
            html_lines.append(f"<p>{escape_html(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def make_base_html(topic: str, date_str: str, content_body: str, css: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>{escape_html(topic)} - 議事録</title>
<style>
{css}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>{escape_html(topic)}</h1>
  <div class="meta">{date_str}</div>
</header>
{content_body}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CSS styles per format
# ---------------------------------------------------------------------------

CHAT_CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Hiragino Sans", "Meiryo", "Noto Sans JP", sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 2rem;
    line-height: 1.7;
  }
  .container { max-width: 960px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #333;
  }
  header h1 { font-size: 1.6rem; color: #fff; margin-bottom: 0.5rem; }
  header .meta { font-size: 0.85rem; color: #888; }
  .round { margin-bottom: 2.5rem; }
  .round-header {
    font-size: 1.1rem;
    color: #aaa;
    margin-bottom: 1rem;
    padding-left: 0.5rem;
    border-left: 3px solid #555;
  }
  .maru-input {
    background: #16213e;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    border-left: 3px solid #e94560;
  }
  .maru-input .label {
    font-size: 0.8rem;
    color: #e94560;
    margin-bottom: 0.3rem;
  }
  .persona-card {
    background: #16213e;
    border-radius: 10px;
    margin-bottom: 0.8rem;
    overflow: hidden;
  }
  .persona-header {
    padding: 0.5rem 1rem;
    font-weight: bold;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .persona-header .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .persona-content {
    padding: 1rem 1.2rem;
    font-size: 0.92rem;
    color: #ccc;
  }
  .persona-content p { margin-bottom: 0.6rem; }
  .persona-content ul { margin: 0.5rem 0 0.5rem 1rem; }
  .persona-content li { margin-bottom: 0.3rem; }
  .persona-content strong { color: #fff; }
  .summary {
    background: #0f3460;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-top: 0.5rem;
    border-left: 3px solid #533483;
  }
  .summary .label {
    font-size: 0.8rem;
    color: #9575cd;
    margin-bottom: 0.3rem;
  }
  .summary p { margin-bottom: 0.5rem; font-size: 0.9rem; }
  .summary strong { color: #fff; }
"""

TRANSCRIPT_CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Hiragino Sans", "Meiryo", "Noto Sans JP", sans-serif;
    background: #111;
    color: #d0d0d0;
    padding: 2rem;
    line-height: 1.8;
  }
  .container { max-width: 800px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #333;
  }
  header h1 { font-size: 1.4rem; color: #fff; margin-bottom: 0.5rem; }
  header .meta { font-size: 0.85rem; color: #666; }
  .round { margin-bottom: 2.5rem; }
  .round-header {
    font-size: 1rem;
    color: #888;
    margin-bottom: 1rem;
    font-family: monospace;
  }
  .speaker { margin-bottom: 1.5rem; }
  .speaker-name {
    font-size: 0.9rem;
    font-weight: bold;
    margin-bottom: 0.3rem;
  }
  .speaker-content {
    font-size: 0.92rem;
    color: #bbb;
    padding-left: 1rem;
    border-left: 2px solid #333;
  }
  .speaker-content p { margin-bottom: 0.5rem; }
  .speaker-content ul { margin: 0.3rem 0 0.5rem 1rem; }
  .speaker-content li { margin-bottom: 0.2rem; }
  .speaker-content strong { color: #fff; }
  .summary {
    margin-top: 1rem;
    padding: 1rem;
    background: #1a1a1a;
    border-radius: 6px;
    border-left: 3px solid #555;
  }
  .summary .label { font-size: 0.8rem; color: #777; margin-bottom: 0.3rem; }
  .summary p { margin-bottom: 0.4rem; font-size: 0.88rem; color: #aaa; }
  .summary strong { color: #ddd; }
"""

SCRIPT_CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Hiragino Mincho ProN", "Yu Mincho", "Noto Serif JP", serif;
    background: #faf8f2;
    color: #2c2c2c;
    padding: 3rem;
    line-height: 2;
  }
  .container { max-width: 700px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #ccc;
  }
  header h1 { font-size: 1.5rem; color: #1a1a1a; margin-bottom: 0.5rem; }
  header .meta { font-size: 0.85rem; color: #999; }
  .round { margin-bottom: 2.5rem; }
  .round-header {
    font-size: 0.95rem;
    color: #888;
    margin-bottom: 1rem;
    font-family: "Hiragino Mincho ProN", serif;
  }
  .speaker { margin-bottom: 1.5rem; }
  .speaker-name {
    font-size: 1rem;
    font-weight: bold;
    color: #444;
    margin-bottom: 0.2rem;
  }
  .speaker-content {
    font-size: 0.95rem;
    color: #333;
    padding-left: 1.5rem;
  }
  .speaker-content p { margin-bottom: 0.5rem; }
  .speaker-content ul { margin: 0.3rem 0 0.5rem 1.5rem; }
  .speaker-content li { margin-bottom: 0.2rem; }
  .speaker-content strong { color: #111; }
  .summary {
    margin-top: 1rem;
    padding: 1rem 1.5rem;
    background: #f5f0e8;
    border-radius: 4px;
    border: 1px solid #ddd;
  }
  .summary .label { font-size: 0.8rem; color: #999; margin-bottom: 0.3rem; }
  .summary p { margin-bottom: 0.4rem; font-size: 0.9rem; color: #555; }
  .summary strong { color: #333; }
"""

# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_chat_body(data: dict) -> str:
    topic = data.get("topic") or data.get("title", "不明")
    created = data.get("created_at", "")
    rounds = data.get("rounds", [])
    dt = datetime.fromisoformat(created) if created else None
    date_str = dt.strftime("%Y/%m/%d %H:%M") if dt else created

    parts = []
    for r in rounds:
        round_num = r.get("round", "?")
        maru_input = r.get("user_input") or r.get("input", "")
        summary = r.get("summary", "")
        responses = r.get("responses", {})
        if isinstance(responses, list):
            items = [(resp.get("name", "?"), resp.get("content", "")) for resp in responses]
        else:
            items = list(responses.items())

        parts.append(f'<div class="round">')
        parts.append(f'  <div class="round-header">ラウンド {round_num}</div>')
        parts.append(f'  <div class="maru-input">')
        parts.append(f'    <div class="label">[マル]</div>')
        parts.append(f'    <div>{escape_html(maru_input)}</div>')
        parts.append(f'  </div>')

        for name, content in items:
            content = content.replace("\\n", "\n")
            color = PERSONA_COLORS.get(name, "#90a4ae")
            parts.append(f'  <div class="persona-card">')
            parts.append(f'    <div class="persona-header" style="background:{color}22; color:{color}">')
            parts.append(f'      <span class="dot" style="background:{color}"></span>')
            parts.append(f'      {escape_html(name)}')
            parts.append(f'    </div>')
            parts.append(f'    <div class="persona-content">')
            parts.append(f'      {render_content(content)}')
            parts.append(f'    </div>')
            parts.append(f'  </div>')

        if summary:
            parts.append(f'  <div class="summary">')
            parts.append(f'    <div class="label">[要約]</div>')
            parts.append(f'    {render_content(summary)}')
            parts.append(f'  </div>')

        parts.append(f'</div>')

    content_body = "\n".join(parts)
    return make_base_html(topic, date_str, content_body, CHAT_CSS)


def render_transcript_body(data: dict) -> str:
    topic = data.get("topic") or data.get("title", "不明")
    created = data.get("created_at", "")
    rounds = data.get("rounds", [])
    dt = datetime.fromisoformat(created) if created else None
    date_str = dt.strftime("%Y/%m/%d %H:%M") if dt else created

    parts = []
    for r in rounds:
        round_num = r.get("round", "?")
        maru_input = r.get("user_input") or r.get("input", "")
        summary = r.get("summary", "")
        responses = r.get("responses", {})
        if isinstance(responses, list):
            items = [(resp.get("name", "?"), resp.get("content", "")) for resp in responses]
        else:
            items = list(responses.items())

        parts.append(f'<div class="round">')
        parts.append(f'  <div class="round-header">--- ラウンド {round_num} ---</div>')

        # マル
        parts.append(f'  <div class="speaker">')
        parts.append(f'    <div class="speaker-name" style="color:#e94560">[マル]</div>')
        parts.append(f'    <div class="speaker-content"><p>{escape_html(maru_input)}</p></div>')
        parts.append(f'  </div>')

        # ペルソナ
        for name, content in items:
            content = content.replace("\\n", "\n")
            color = PERSONA_COLORS.get(name, "#90a4ae")
            parts.append(f'  <div class="speaker">')
            parts.append(f'    <div class="speaker-name" style="color:{color}">[{name}]</div>')
            parts.append(f'    <div class="speaker-content">')
            parts.append(f'      {render_content(content)}')
            parts.append(f'    </div>')
            parts.append(f'  </div>')

        if summary:
            parts.append(f'  <div class="summary">')
            parts.append(f'    <div class="label">[要約]</div>')
            parts.append(f'    {render_content(summary)}')
            parts.append(f'  </div>')

        parts.append(f'</div>')

    content_body = "\n".join(parts)
    return make_base_html(topic, date_str, content_body, TRANSCRIPT_CSS)


def clean_for_script(text: str) -> str:
    """script形式用にマークダウン記号を除去。"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        # リスト記号を除去
        if s.startswith("*   "):
            s = s[4:]
        # ** を除去（太字記号）
        s = s.replace("**", "")
        # 見出し記号を除去
        if s.startswith("### "):
            s = s[4:]
        if s.startswith("## "):
            s = s[3:]
        if s.startswith("# "):
            s = s[2:]
        cleaned.append(s)
    return "\n".join(cleaned)


def render_script_body(data: dict) -> str:
    topic = data.get("topic") or data.get("title", "不明")
    created = data.get("created_at", "")
    rounds = data.get("rounds", [])
    dt = datetime.fromisoformat(created) if created else None
    date_str = dt.strftime("%Y/%m/%d %H:%M") if dt else created

    parts = []
    for r in rounds:
        round_num = r.get("round", "?")
        maru_input = r.get("user_input") or r.get("input", "")
        summary = r.get("summary", "")
        responses = r.get("responses", {})
        if isinstance(responses, list):
            items = [(resp.get("name", "?"), resp.get("content", "")) for resp in responses]
        else:
            items = list(responses.items())

        parts.append(f'<div class="round">')
        parts.append(f'  <div class="round-header">第{round_num}ラウンド</div>')

        # マル
        parts.append(f'  <div class="speaker">')
        parts.append(f'    <div class="speaker-name">マル</div>')
        parts.append(f'    <div class="speaker-content"><p>「{escape_html(maru_input)}」</p></div>')
        parts.append(f'  </div>')

        # ペルソナ
        for name, content in items:
            color = PERSONA_COLORS.get(name, "#666")
            parts.append(f'  <div class="speaker">')
            parts.append(f'    <div class="speaker-name" style="color:{color}">{escape_html(name)}</div>')
            parts.append(f'    <div class="speaker-content">')
            # script形式：各行を「発言」で囲む（マークダウン記号を除去）
            cleaned = clean_for_script(content)
            for line in cleaned.split("\n"):
                s = line.strip()
                if s:
                    parts.append(f'      <p>「{escape_html(s)}」</p>')
                else:
                    parts.append(f'      <p><br></p>')
            parts.append(f'    </div>')
            parts.append(f'  </div>')

        if summary:
            parts.append(f'  <div class="summary">')
            parts.append(f'    <div class="label">[要約]</div>')
            parts.append(f'    {render_content(summary)}')
            parts.append(f'  </div>')

        parts.append(f'</div>')

    content_body = "\n".join(parts)
    return make_base_html(topic, date_str, content_body, SCRIPT_CSS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def view_meeting(filepath: Path, fmt: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    data = normalize_data(data)

    renderers = {
        "chat": render_chat_body,
        "transcript": render_transcript_body,
        "script": render_script_body,
    }

    render = renderers.get(fmt)
    if not render:
        print(f"不明なフォーマット: {fmt} (chat / transcript / script を指定してください)")
        sys.exit(1)

    html = render(data)

    html_path = filepath.with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"生成: {html_path}")
    webbrowser.open(f"file://{html_path.resolve()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="RCF会議議事録ビューア（HTML出力）")
    parser.add_argument("file", help="議事録JSONファイルのパス")
    parser.add_argument(
        "--format",
        choices=["chat", "transcript", "script"],
        default="chat",
        help="出力フォーマット（デフォルト: chat）",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ファイルが見つかりません: {filepath}")
        sys.exit(1)

    view_meeting(filepath, args.format)
