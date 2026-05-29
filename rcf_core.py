"""
RCF会議システム — 共通コアライブラリ
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import fitz

CONFIG_FILE = Path(__file__).parent / "config.json"
LOGS_DIR = Path(__file__).parent / "logs"


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_personas(config: dict) -> list[dict]:
    raw = config["personas"]
    base_dir = Path(CONFIG_FILE).parent
    personas = []
    for p in raw:
        if "system_prompt_file" in p:
            file_path = base_dir / p["system_prompt_file"]
            with open(file_path, "r", encoding="utf-8") as f:
                p["system_prompt"] = "/no_think\n" + f.read().strip()
        elif "system_prompt" not in p:
            raise ValueError(f"ペルソナ '{p['name']}' に system_prompt_file または system_prompt がありません")
        personas.append(p)
    return personas


def ask_llm(system_prompt: str, messages: list[dict], config: dict, retries: int = 3) -> str:
    backend = config.get("backend", "ollama")

    if backend == "lmstudio":
        return _ask_lmstudio(system_prompt, messages, config, retries)
    else:
        # default: ollama
        return _ask_ollama(system_prompt, messages, config, retries)


def _ask_ollama(system_prompt: str, messages: list[dict], config: dict, retries: int = 3) -> str:
    payload = {
        "model": config["model"],
        "system": system_prompt,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": config.get("num_ctx", 32768)},
    }
    url = config.get("ollama_url", "http://localhost:11434") + "/api/chat"
    timeout = config.get("timeout", 120)
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except requests.exceptions.ReadTimeout:
            if attempt < retries - 1:
                print(f"  [リトライ] {attempt + 1}/{retries}...", end=" ", flush=True)
                time.sleep(2)
                print("OK")
            else:
                raise
        except requests.exceptions.RequestException as e:
            raise


def _ask_lmstudio(system_prompt: str, messages: list[dict], config: dict, retries: int = 3) -> str:
    body_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": config["model"],
        "messages": body_messages,
        "stream": False,
    }
    url = config.get("lmstudio_url", "http://localhost:1234") + "/v1/chat/completions"
    timeout = config.get("timeout", 120)
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.exceptions.ReadTimeout:
            if attempt < retries - 1:
                print(f"  [リトライ] {attempt + 1}/{retries}...", end=" ", flush=True)
                time.sleep(2)
                print("OK")
            else:
                raise
        except requests.exceptions.RequestException as e:
            raise


def summarize_round(persona_responses: list[dict], config: dict) -> str:
    """各ペルソナの発言を要約してまとめる。合意点ではなく視点の違い・未解決の論点に集中。"""
    summary_prompt = (
        "以下の発言を要約してください。\n\n"
        "【重要】合意点には1行で終わり、残りはすべて「視点の相違」「対立点」「未解決の論点」に充ててください。\n"
        "合意を過剰に強調せず、議論を発酵させるための「次の問い」が見えるようにしてください。\n\n"
    )
    for entry in persona_responses:
        summary_prompt += f"[{entry['name']}]: {entry['content']}\n\n"

    summary_prompt += "\n要約:"
    return ask_llm(
        "あなたは議論を要約するアシスタントです。合意点ではなく、視点の違い・対立・未解決の論点を中心に要約してください。",
        [{"role": "user", "content": summary_prompt}],
        config,
    )


def score_meeting_state(summary: str, config: dict) -> dict:
    """要約から会議状態をスコアリング（0-5）"""
    prompt = (
        "以下の会議要約を分析して、JSON形式のみで返せ。\n"
        '{"共感度": 0-5, "抽象度": 0-5, "発散度": 0-5, "対立度": 0-5}\n'
        "数値のみ、説明不要。\n\n要約:\n" + summary
    )
    result = ask_llm("", [{"role": "user", "content": prompt}], config)
    try:
        match = re.search(r'\{.*\}', result, re.DOTALL)
        return json.loads(match.group()) if match else {}
    except Exception:
        return {}


def suggest_next_questions(summary: str, config: dict, question_type: str = "") -> list[str]:
    """要約を受け取って次の議論の問い候補を3つ返す。"""
    # 問いタイプからヒントを読み込む
    hint = ""
    if question_type:
        yaml_path = Path(__file__).parent / "questions" / "example" / f"{question_type}.yaml"
        if yaml_path.exists():
            import yaml as pyyaml
            with open(yaml_path, encoding="utf-8") as f:
                qt = pyyaml.safe_load(f)
                hint = qt.get("prompt_hint", "")

    prompt = (
        "以下の議論の要約を受けて、次の問いの候補を3つ生成してください。\n"
        "それぞれの問いは短い一文で、改行区切りで返してください。\n\n"
        f"【要約】\n{summary}\n\n"
        f"{f'問いの方向性: {hint}' if hint else ''}"
        "次の問いの候補:\n"
    )
    resp = ask_llm(
        "あなたは議論を促進するファシリテーターです。次の問いを3つ提案してください。",
        [{"role": "user", "content": prompt}],
        config,
    )
    # 改行で分割して空行をフィルタ
    questions = [q.strip() for q in resp.strip().split("\n") if q.strip()]
    return questions[:3]


def extract_pdf_text(pdf_path: str, config: dict) -> str:
    """PDFからテキストを抽出。"""
    max_len = config.get("max_pdf_length", 3000)
    try:
        doc = fitz.open(pdf_path)
        text_parts = [page.get_text() for page in doc]
        doc.close()
        full_text = "\n".join(text_parts)
        if len(full_text) > max_len:
            return full_text[:max_len]
        return full_text
    except (UnicodeDecodeError, Exception):
        return ""


def build_history(
    rounds: list[dict],
    persona_name: str,
    persona_system_prompt: str,
    maru_input: str,
    config: dict = {},
    pdf_text: str = "",
    captain_name: str = "マル",
    is_auto: bool = False,
) -> tuple[str, list[dict]]:
    """
    前ラウンド議事からシステムプロンプトと会話履歴を構築する。

    Returns:
        (system_prompt, history)
    """
    common = config.get("common_system_prompt", "")
    system = f"{common}\n\n{persona_system_prompt}" if common else persona_system_prompt

    # 会話履歴
    history: list[dict] = []

    # PDFテキストあり → 会話履歴の先頭に追加
    if pdf_text:
        history.append({"role": "user", "content": f"【議題の背景資料】\n{pdf_text}"})
        history.append({"role": "assistant", "content": "資料を確認しました。議論を始めましょう。"})

    prev_round = rounds[-2] if len(rounds) >= 2 else None
    for r in rounds[-2:]:
        is_prev = r is prev_round
        for resp_name, resp_content in r.get("responses", {}).items():
            if is_prev and (summary := r.get("summary")):
                # 前ラウンドの他メンバーは要約経由で
                history.append({
                    "role": "user",
                    "content": f"[{resp_name}]: (要約)\n{summary}",
                })
            elif resp_name == persona_name:
                history.append({"role": "assistant", "content": resp_content})
            else:
                history.append({"role": "user", "content": f"[{resp_name}]: {resp_content}"})

    if is_auto:
        history.append({"role": "user", "content": "次の発言をお願いします。"})
    elif maru_input.strip() in ("/skip", ""):
        history.append({"role": "user", "content": "次の発言をお願いします。"})
    else:
        history.append({"role": "user", "content": maru_input})

    return system, history


def _persona_author(name: str) -> str:
    """ペルソナ名を author 用 ID に変換。"""
    return name[0].lower() + name[1:]


def save_meeting_minutes(rounds: list[dict], topic: str, session_id: str, config: dict, logs_dir: Path) -> Path:
    """議事録を PocketPal 互換形式で保存。"""
    logs_dir.mkdir(exist_ok=True)
    now_iso = datetime.now().isoformat()
    captain_name = config.get("captain_name", "マル")

    messages: list[dict] = []
    for r in rounds:
        round_ms = int(time.time() * 1000)
        user_input = r.get("user_input") or r.get("input", "")
        if user_input:
            messages.append({
                "id": f"{session_id}_r{r['round']}_maru",
                "author": captain_name,
                "text": user_input,
                "type": "text",
                "createdAt": round_ms,
            })
        for name, content in r.get("responses", {}).items():
            messages.append({
                "id": f"{session_id}_r{r['round']}_{name}",
                "author": name,
                "text": content,
                "type": "text",
                "createdAt": round_ms,
            })

        # 要約も別メッセージとして記録
        if r.get("summary"):
            messages.append({
                "id": f"{session_id}_r{r['round']}_summary",
                "author": "議場",
                "text": r["summary"],
                "type": "text",
                "createdAt": round_ms,
            })

    filepath = logs_dir / f"meeting_{session_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "id": session_id,
            "title": topic,
            "date": now_iso,
            "messages": messages,
        }, f, ensure_ascii=False, indent=2)

    # ペルソナ別ログ（PocketPal 互換形式に統一）
    for r in rounds:
        for name, content in r.get("responses", {}).items():
            pfilepath = logs_dir / f"{name}.json"
            pmsgs: list[dict] = json.load(open(pfilepath, "r", encoding="utf-8")) if pfilepath.exists() else []
            ts = int(time.time() * 1000)
            msg_id = f"{session_id}_r{r['round']}_{name}"
            if not any(m.get("id") == msg_id for m in pmsgs):
                pmsgs.append({
                    "id": msg_id,
                    "author": name,
                    "text": content,
                    "type": "text",
                    "createdAt": ts,
                })
                with open(pfilepath, "w", encoding="utf-8") as f:
                    json.dump(pmsgs, f, ensure_ascii=False, indent=2)
    return filepath


