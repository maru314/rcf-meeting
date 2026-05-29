"""
RCF会議システム — CLI版
"""

import uuid
import requests

from pathlib import Path
from rcf_core import load_config, load_personas, ask_llm
from rcf_core import summarize_round, extract_pdf_text, build_history, save_meeting_minutes

LOGS_DIR = Path(__file__).parent / "logs"

def run_meeting():
    config = load_config()
    personas = load_personas(config)

    print("=" * 60)
    print("  RCF会議システム")
    print("=" * 60)
    print(f"モデル: {config['model']}")
    print(f"ペルソナ: {', '.join(p['name'] for p in personas)}")
    print()

    # PDFファイル入力
    pdf_text = ""
    pdf_path = input("PDFファイルのパスを入力（スキップはEnter）: ").strip()
    if pdf_path:
        pdf_text = extract_pdf_text(pdf_path, config)
        if pdf_text:
            print(f"PDFを抽出しました（{len(pdf_text)}文字）")

    # トピック入力
    topic = input("議論したいトピックを入力してください: ").strip()
    if not topic:
        print("トピックが入力されませんでした。終了します。")
        return
    print(f"\nトピック: {topic}")
    print()

    session_id = str(uuid.uuid4())[:8]
    round_num = 0
    all_rounds: list[dict] = []
    captain = config.get("captain_name", "マル")

    try:
        while True:
            round_num += 1
            print(f"--- ラウンド {round_num} ---")

            maru_input = input(f"\n[{captain}] ラウンド{round_num}の発言を入力 (/next, /end): ").strip()

            if maru_input.lower() == "/end":
                print("議事録を生成して会議を終了します...")
                save_meeting_minutes(all_rounds, topic, session_id, config, LOGS_DIR)
                break

            if maru_input.lower() == "/next":
                auto_rounds = config.get("auto_rounds", 0)
                if auto_rounds > 0:
                    print(f"自動ラウンド {auto_rounds}回 を実行します...")
                    for _ in range(auto_rounds):
                        round_num += 1
                        print(f"\n--- ラウンド {round_num}（自動）---")
                        persona_responses: list[dict] = []

                        for persona in personas:
                            name = persona["name"]
                            system_prompt, history = build_history(
                                rounds=all_rounds,
                                persona_name=name,
                                persona_system_prompt=persona["system_prompt"],
                                maru_input="",
                                config=config,
                                pdf_text=pdf_text,
                                captain_name=captain,
                                is_auto=True,
                            )

                            print(f"[{name}] 発言中...", end=" ", flush=True)
                            try:
                                response = ask_llm(system_prompt, history, config)
                            except requests.exceptions.RequestException as e:
                                print(f"エラー: {e}")
                                response = "[エラー: Ollamaに接続できませんでした]"
                            print("完了")

                            persona_responses.append({"name": name, "content": response})

                        summary = summarize_round(persona_responses, config)
                        print()
                        print("--- 発言一覧 ---")
                        for entry in persona_responses:
                            print(f"\n[{entry['name']}]:")
                            print(entry["content"])
                        print()
                        print("--- 要約 ---")
                        print(summary)
                        print()

                        all_rounds.append({
                            "round": round_num,
                            "input": "/skip",
                            "responses": {r["name"]: r["content"] for r in persona_responses},
                            "summary": summary,
                        })
                        persona_responses = []
                else:
                    print("ラウンドをスキップします。")
                continue

            # 各ペルソナに発言を投げる
            persona_responses: list[dict] = []
            print()
            for persona in personas:
                name = persona["name"]

                system_prompt, history = build_history(
                    rounds=all_rounds,
                    persona_name=name,
                    persona_system_prompt=persona["system_prompt"],
                    maru_input=maru_input,
                    config=config,
                    pdf_text=pdf_text,
                    captain_name=captain,
                )

                print(f"[{name}] 発言中...", end=" ", flush=True)
                try:
                    response = ask_llm(system_prompt, history, config)
                except requests.exceptions.RequestException as e:
                    print(f"エラー: {e}")
                    response = "[エラー: Ollamaに接続できませんでした]"
                print("完了")

                persona_responses.append({"name": name, "content": response})

            # 要約
            summary = summarize_round(persona_responses, config)
            print()
            print("--- 発言一覧 ---")
            for entry in persona_responses:
                print(f"\n[{entry['name']}]:")
                print(entry["content"])
            print()
            print("--- 要約 ---")
            print(summary)
            print()

            all_rounds.append({
                "round": round_num,
                "input": maru_input,
                "responses": {r["name"]: r["content"] for r in persona_responses},
                "summary": summary,
            })
    except KeyboardInterrupt:
        print("\n\n中断されました。")
    except NameError as e:
        print(f"\nエラー: {e} — rcf_core.py の更新が必要です")
        raise
    finally:
        if all_rounds and config.get("logging", True):
            save_meeting_minutes(all_rounds, topic, session_id, config, LOGS_DIR)


if __name__ == "__main__":
    run_meeting()
