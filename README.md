# RCF（Remote Cognitive Fleet）

RCFは、認知主権と再接続可能性を重視し、AIが間違わないことよりも「間違いを咀嚼できる構造」を目指す実験体系です。

## セットアップ
1. `config.example.json` を `config.json` にコピーして編集
2. `personas/example/` を参考に `personas/` にプロンプトを作成
3. `pip install -r requirements.txt`
4. `ollama pull qwen3.5:9b`
5. `streamlit run app.py`

## バックエンド切り替え（Ollama / LM Studio）

`config.json` の `backend` フィールドで切り替えられます。

### Ollama（デフォルト）
```json
{
  "backend": "ollama",
  "ollama_url": "http://localhost:11434"
}
```

### LM Studio
LM Studio を起動してモデルをロードし、Local Server を開始してください。
```json
{
  "backend": "lmstudio",
  "lmstudio_url": "http://localhost:1234"
}
```

## 使い方
- GUIモード: `streamlit run app.py`
- CLIモード: `python meeting.py`
- ログ表示: `python view_meeting.py logs/xxx.json`
- PocketPalインポート: `python import_pocketpal.py chat_xxx.json ペルソナ名`
- ペルソナログ変換: `python convert_to_pocketpal.py logs/ペルソナ名.json --last 20`

## RCFの思想

AIをツールではなくチームとして運用する設計。
艦長は「問いの設計者」として会議の場を作り、ペルソナが発酵させ、ログが蓄積される。

完成した人格を配布するのではなく、「役割だけ定義した初期状態」を配布し、各自が育てる。
同じテンプレートから、別文化圏の艦隊が分岐していく——知的盆栽モデル。

## ペルソナテンプレート

`personas/example/` に役割定義のサンプルがある。

| 役割 | 担当 |
|---|---|
| 分析役 | 論理・構造・根本原因の分析 |
| 発散役 | 直感・飛躍・仮説の提示 |
| 観測役 | 俯瞰・ズレ・未整理の論点 |

これをベースに `personas/` に自分のプロンプトを作る。
ペルソナは命令するより、違いが活きる状況を維持することで個性が立つ。

## 問い設計テンプレート

`questions/example/` に問いタイプのYAMLがある。
会議の「場の温度」を設計するための道具。

| タイプ | 用途 |
|---|---|
| deep_dive | 深掘り・詳細化 |
| conflict_probe | 対立・相違点の生成 |
| reality_anchor | 抽象から現実へ |
| external_loop | 外部視点の導入 |
| role_split | 役割分化の強調 |
| fermentation | 発酵・熟成待ち |

UIのサイドバーから問いタイプを選ぶと、次の問い候補がその方向に寄る。

## ログとPocketPal連携

会議ログはPocketPal互換形式（`logs/meeting_*.json`）で保存される。
ペルソナログ（`logs/エミ.json`など）は配列形式のため、インポート前に変換が必要。

### PocketPal → RCF（インポート）
PocketPalのエクスポートJSONをペルソナログに取り込む：
```
python import_pocketpal.py chat_xxx.json ペルソナ名
```

### RCF → PocketPal（変換＋インポート）
ペルソナログをPocketPal形式に変換してスマホに持ち込む：
```
python convert_to_pocketpal.py logs/ペルソナ名.json --last 20
```
`--last 20`推奨。全件渡すとコンテキスト満杯になる。
生成された`ペルソナ名_pocketpal.json`をPocketPalでインポート。

### フロー
```
会議システム（RCF）  ←→  スマホPocketPal（対話）
```

## ライセンス

- コード（`*.py`）: MIT License
- ドキュメント・ペルソナテンプレート・思想テキスト: CC BY-NC-SA 4.0
