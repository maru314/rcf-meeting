"""
RCF会議システム — Streamlit UI版
meeting.pyのOllama呼び出しロジックを流用。
設定は config.json から読み込む。
"""

from datetime import datetime
from pathlib import Path

import streamlit as st

import rcf_core
from rcf_core import load_config, load_personas, ask_llm
from rcf_core import summarize_round, suggest_next_questions, extract_pdf_text, save_meeting_minutes

DOCS_DIR = Path(__file__).parent / "documents"


# ---------------------------------------------------------------------------
# Streamlit初期化
# ---------------------------------------------------------------------------

if "rounds" not in st.session_state:
    st.session_state["rounds"] = []
if "topic" not in st.session_state:
    st.session_state["topic"] = ""
if "pdf_text" not in st.session_state:
    st.session_state["pdf_text"] = ""
if "status" not in st.session_state:
    st.session_state["status"] = "waiting"
if "current_input" not in st.session_state:
    st.session_state["current_input"] = ""
if "captain_name" not in st.session_state:
    st.session_state["captain_name"] = "マル"
if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
if "suggested_questions" not in st.session_state:
    st.session_state["suggested_questions"] = []
if "suggested_input" not in st.session_state:
    st.session_state["suggested_input"] = ""
if "last_summary" not in st.session_state:
    st.session_state["last_summary"] = ""
if "question_type" not in st.session_state:
    st.session_state["question_type"] = ""

# ---------------------------------------------------------------------------
# サイドバー — 設定
# ---------------------------------------------------------------------------

config = load_config()

with st.sidebar:
    st.header("設定")

    captain_name = st.text_input("艦長名", value=st.session_state["captain_name"])
    st.session_state["captain_name"] = captain_name

    if "topic" not in st.session_state or not st.session_state["topic"]:
        new_topic = st.text_input("会議テーマ", placeholder="例: MBTI記事の感想")
        if new_topic:
            st.session_state["topic"] = new_topic
            st.session_state["rounds"] = []
            st.session_state["status"] = "waiting"
            st.rerun()
    else:
        st.text_input("会議テーマ", value=st.session_state["topic"], disabled=True)

    pdf_path = st.text_input("PDFパス（任意）", placeholder="documents/xxx.pdf", key="pdf_path_input")
    if pdf_path and st.button("PDF読み込み"):
        text = extract_pdf_text(pdf_path, config)
        if text:
            st.session_state["pdf_text"] = text
            st.success(f"読み込み完了（{len(text)}文字）")
        else:
            st.error("PDF読み込みに失敗しました")

    # ログ出力ON/OFF
    logging_enabled = st.toggle(
        "ログ出力",
        value=config.get("logging", True),
        key="logging_toggle",
    )
    st.session_state["logging"] = logging_enabled

    # 会議状態スコア表示（要約がある時だけ）
    if st.session_state.get("last_summary"):
        scores = rcf_core.score_meeting_state(
            st.session_state["last_summary"], config
        )
        if scores:
            st.markdown("**会議状態**")
            for k, v in scores.items():
                try:
                    score_val = int(v)
                except (ValueError, TypeError):
                    score_val = 0
                st.progress(score_val / 5, text=f"{k} {'█' * score_val}{'░' * (5 - score_val)}")

    # 問いタイプ選択
    question_types = {
        "": "自動",
        "deep_dive": "深掘り型",
        "conflict_probe": "対立生成型",
        "reality_anchor": "現実接続型",
        "external_loop": "外循環型",
        "role_split": "役割分化型",
        "fermentation": "発酵型",
    }
    selected_type = st.selectbox(
        "問いタイプ",
        options=list(question_types.keys()),
        format_func=lambda x: question_types[x],
    )
    st.session_state["question_type"] = selected_type

    if st.button("🗑 会議をクリア", type="primary"):
        st.session_state["rounds"] = []
        st.session_state["topic"] = ""
        st.session_state["pdf_text"] = ""
        st.session_state["status"] = "waiting"
        st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.rerun()

# ---------------------------------------------------------------------------
# メイン — 会話履歴表示
# ---------------------------------------------------------------------------

topic = st.session_state.get("topic", "")
if not topic:
    st.info("左サイドバーから会議テーマを入力してください。")
    st.stop()

st.header(f"{topic} — 議事録")

for r in st.session_state["rounds"]:
    with st.container():
        st.markdown(f"### ラウンド {r['round']}")
        st.divider()

        # マルの発言（右寄せ）
        with st.chat_message("user"):
            captain = st.session_state.get("captain_name", "マル")
            icon = st.session_state.get("captain_icon", "🔴")
            st.markdown(f"**{icon} {captain}**\n\n{r['user_input']}")

        # ペルソナ発言（左寄せ、色分け）
        for name, content in r["responses"].items():
            style = st.session_state.get("persona_styles", {}).get(name, {"color": "#999", "icon": "👤"})
            with st.chat_message("assistant"):
                st.markdown(f"**{style['icon']} {name}**")
                st.markdown(content)

        # 要約
        if r.get("summary"):
            with st.container():
                st.warning(f"**📝 要約**\n\n{r['summary']}")

# ---------------------------------------------------------------------------
# 次の問い候補（ボタン）
# ---------------------------------------------------------------------------

if st.session_state.get("suggested_questions"):
    st.markdown("**💡 次の問いの候補**")
    for idx, q in enumerate(st.session_state["suggested_questions"]):
        if st.button(q, key=f"suggested_q_btn_{idx}"):
            st.session_state["suggested_input"] = q
            st.rerun()
    st.divider()

# ---------------------------------------------------------------------------
# 下部 — 入力欄
# ---------------------------------------------------------------------------

if st.session_state["status"] == "processing":
    st.info("⏳ ペルソナに発言を依頼中...")

# ボタン選択で入力欄に反映
if st.session_state.get("suggested_input"):
    st.session_state["current_input"] = st.session_state["suggested_input"]
    st.session_state["suggested_input"] = ""

col_input, col_send = st.columns([5, 1])

with col_input:
    user_input = st.text_input(
        f"{st.session_state.get('captain_name', 'マル')}の発言",
        key="current_input",
        placeholder="メッセージを入力...",
        disabled=False,
    )

with col_send:
    send_clicked = st.button("送信", disabled=not user_input.strip())

# ---------------------------------------------------------------------------
# メインロジック
# ---------------------------------------------------------------------------

if send_clicked and user_input.strip():
    st.session_state["status"] = "processing"
    st.rerun()

# --- 処理実行 ---
if st.session_state["status"] == "processing":
    personas = load_personas(config)
    st.session_state["persona_styles"] = {
        p["name"]: {"color": p.get("color", "#999"), "icon": p.get("icon", "👤")}
        for p in config["personas"]
    }
    st.session_state["captain_icon"] = config.get("captain_icon", "🔴")
    st.session_state["captain_color"] = config.get("captain_color", "#e94560")
    round_num = len(st.session_state["rounds"]) + 1
    input_text = st.session_state.get("current_input", "")

    # 次ラウンド（入力なし）
    if not input_text.strip():
        input_text = ""

    # マルの発言を記録（/skip は記録しない）
    if input_text.strip():
        st.session_state["rounds"].append({
            "round": round_num,
            "user_input": input_text,
            "responses": {},
            "summary": "",
        })

    # 各ペルソナに発言を依頼
    responses = {}
    for persona in personas:
        name = persona["name"]

        system, history = rcf_core.build_history(
            rounds=st.session_state["rounds"],
            persona_name=name,
            persona_system_prompt=persona["system_prompt"],
            maru_input=input_text,
            config=config,
            pdf_text=st.session_state.get("pdf_text", ""),
            captain_name=st.session_state.get("captain_name", "マル"),
        )

        with st.spinner(f"⏳ {name} 発言中..."):
            try:
                response = ask_llm(system, history, config)
            except Exception as e:
                response = f"[エラー: {e}]"

        responses[name] = response

    # 要約
    persona_entries = [{"name": n, "content": c} for n, c in responses.items()]
    with st.spinner("💭 議場が要約中..."):
        summary = summarize_round(persona_entries, config)

    # 最終ラウンドを更新
    if st.session_state["rounds"]:
        st.session_state["rounds"][-1]["responses"] = responses
        st.session_state["rounds"][-1]["summary"] = summary

    # 要約をセッションに保存（スコアリング用）
    st.session_state["last_summary"] = summary

    # ログ出力
    if st.session_state.get("logging", True):
        save_meeting_minutes(
            st.session_state["rounds"],
            st.session_state["topic"],
            st.session_state["session_id"],
            config,
            Path(__file__).parent / "logs",
        )

    # 次の問い候補（設定ONのとき）
    if config.get("suggest_questions", False):
        last_summary = st.session_state["rounds"][-1].get("summary", "") if st.session_state["rounds"] else ""
        with st.spinner("💭 次の問いを提案中..."):
            questions = suggest_next_questions(last_summary, config, st.session_state.get("question_type", ""))
        st.session_state["suggested_questions"] = questions
        st.session_state["suggested_input"] = ""

    st.session_state["status"] = "waiting"
    st.rerun()
