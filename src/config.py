"""
config.py（詳細設計書 3.2 モジュール設計）

役割:
    各種設定値を保持する。基本設計では「定数または設定ファイルで変更可能」とされているが、
    本フェーズでは Python モジュール上の定数として集約する。

設計上の想定定数（03_詳細設計書 3.2 より）:
    INPUT_FILE_PATH, OUTPUT_DIR, COMMENT_COLUMN, NAME_COLUMN, IP_COLUMN,
    SIMILARITY_THRESHOLD, EMBEDDING_MODEL_NAME
"""

from __future__ import annotations

from pathlib import Path

# -----------------------------------------------------------------------------
# パス解決用（設計書の project_root 相当）
# `src/config.py` の1つ上の階層をプロジェクトルートとみなす。
# -----------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# =============================================================================
# 詳細設計 3.2「想定定数」
# =============================================================================

# 入力CSVのパス（詳細設計 7 設定値詳細の例: input/sample_comments.csv）
INPUT_FILE_PATH: Path = PROJECT_ROOT / "input" / "sample_comments.csv"

# 出力先ディレクトリ（詳細設計 7: output）
OUTPUT_DIR: Path = PROJECT_ROOT / "output"

# 列名（詳細設計 6・7 データ項目）
COMMENT_COLUMN: str = "comment"
NAME_COLUMN: str = "name"
IP_COLUMN: str = "ip_address"

# 類似度しきい値（基本設計 8.3。コサイン類似度の初期値例 0.80）
SIMILARITY_THRESHOLD: float = 0.80

# 埋め込みモデル（詳細設計 7・8.2。sentence-transformers 利用）
EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"

# =============================================================================
# DB（SQLite）保存（将来拡張 → 実装）
# =============================================================================
# 生成物は output 配下にまとめ、DBも同様に配置する。
DB_PATH: Path = OUTPUT_DIR / "comment_clustering.db"

# DBに保存する際、同一 run_id で summary/details を紐付ける。
# run_id の生成は db.py 側で行う（ISO 8601 のタイムスタンプ等）。

# =============================================================================
# 設計 3.2 以外だが、既存の src 配下モジュールが参照している値
# TODO: embedding.py / exporter.py / dedup.py を詳細設計どおりに切り直す際、
#       これらを各モジュールへ移すか、設定ファイル（YAML等）読込に置き換える。
# =============================================================================
RECORD_ID_COLUMN: str = "record_id"
GROUPED_OUTPUT_FILENAME: str = "grouped_comments.csv"
DETAILS_OUTPUT_FILENAME: str = "comment_details.csv"
E5_QUERY_PREFIX: str = "query: "
EMBEDDING_BATCH_SIZE: int = 32

# =============================================================================
# ルールベース・ラベル自動生成（要件/設計の追記に対応）
# =============================================================================
# ルール例（ユーザー要望）:
# 「使いやすい」「簡単」「分かりやすい」 → 操作性
# 「遅い」「重い」「固まる」 → 性能
# 「高い」「料金」「コスト」 → 価格
# 「見にくい」「デザイン」「UI」 → 画面デザイン
#
# TODO: 本番運用では辞書を外部ファイル化（YAML/JSON/CSV）し、業務で育てる想定。
LABEL_KEYWORDS: dict[str, list[str]] = {
    "操作性": ["使いやすい", "簡単", "分かりやすい"],
    "性能": ["遅い", "重い", "固まる", "フリーズ"],
    "価格": ["高い", "料金", "コスト"],
    "画面デザイン": ["見にくい", "デザイン", "ui", "UI"],
}

# どのルールにも当てはまらない場合のラベル
DEFAULT_GROUP_LABEL: str = "その他"

# =============================================================================
# TODO: 非機能要件（基本設計 8.2）— 設定の外部ファイル化・環境変数上書き
# =============================================================================
# - INPUT_FILE_PATH / OUTPUT_DIR を .env や config.yaml から読む
# - SIMILARITY_THRESHOLD を実行引数で上書き（main 側の argparse と二重管理に注意）
# - CSV 文字コードを UTF-8 固定以外（例: utf-8-sig）に切替可能にする
