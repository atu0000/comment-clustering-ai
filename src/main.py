"""
main.py
-------
コメント類似集約バッチのエントリポイントです。

処理シーケンス（詳細設計 4.1）:
1. 設定（config）参照
2. loader: 入力CSV読込・必須列検証
3. preprocess: 正規化・空行除外・normalized_comment 付与
4. embedding: sentence-transformers でベクトル化
5. grouping: 類似度で group_id 採番 → 後段で集計行も生成
6. dedup: person_key 付与 → グループ内の同一人物フラグ
7. grouping.build_group_summary: グループ単位の集計 DataFrame を構築（明細 df のみ）
8. exporter: CSV 出力

実行例（プロジェクトルートで）::

    python -m src.main

Windows のコマンドプロンプト / PowerShell いずれでも、カレントディレクトリを
リポジトリのルート（requirements.txt がある階層）にして実行してください。
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src import config
from src.dedup import deduplicate_in_groups
from src.embedding import create_embeddings
from src.exporter import export_csv, output_paths
from src.grouping import assign_groups, build_group_summary
from src.loader import load_input_csv
from src.preprocess import normalize_comments


def _setup_logging() -> None:
    """標準出力へ読みやすい形式でログを流す（基本設計 11. ログ方針）。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    既定値は config に従います。実行時にだけパスを差し替えたい場合向けの最低限CLIです。

    手順書なしでも動かしやすいように、入力/出力はオプションで上書き可能にしています。
    """
    parser = argparse.ArgumentParser(
        description="類似コメントのグルーピングと件数集計（CSV→CSV）",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=config.INPUT_FILE_PATH,
        help=f"入力CSVパス（既定: {config.INPUT_FILE_PATH}）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.OUTPUT_DIR,
        help=f"出力先ディレクトリ（既定: {config.OUTPUT_DIR}）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """全体パイプラインを実行し、正常終了なら 0 を返します。"""
    _setup_logging()
    log = logging.getLogger("comment-clustering")

    args = _parse_args(argv)

    log.info("処理を開始します。")

    try:
        # ------------------------------------------------------------------
        # 1) 入力CSV読込（必須列チェック・任意列補完）
        # ------------------------------------------------------------------
        log.info("入力CSVを読み込みます: %s", args.input)
        df_raw = load_input_csv(args.input, [config.COMMENT_COLUMN])
        log.info("入力件数（読込直後）: %d 件", len(df_raw))

        # ------------------------------------------------------------------
        # 2) 前処理（normalized_comment の付与と空行除外）
        # ------------------------------------------------------------------
        df = normalize_comments(df_raw, config.COMMENT_COLUMN)
        log.info("前処理後の有効コメント件数: %d 件", len(df))
        if len(df) == 0:
            log.error("有効コメントが0件のため終了します（詳細設計 例外設計）。")
            return 1

        # ------------------------------------------------------------------
        # 3) 埋め込み（sentence-transformers）
        # ------------------------------------------------------------------
        comments = df["normalized_comment"].astype(str).tolist()
        try:
            embeddings = create_embeddings(comments, config.EMBEDDING_MODEL_NAME)
        except RuntimeError as exc:
            log.error("モデル読込または埋め込み計算に失敗しました: %s", exc)
            return 1

        if embeddings.size == 0:
            log.error("埋め込み結果が空です。終了します。")
            return 1

        # ------------------------------------------------------------------
        # 4) 類似度グルーピング（閾値は config）
        # ------------------------------------------------------------------
        df_g = assign_groups(df, embeddings, threshold=config.SIMILARITY_THRESHOLD)
        n_groups = int(df_g["group_id"].nunique()) if len(df_g) else 0
        log.info("グループ化が完了しました。グループ数: %d", n_groups)

        # ------------------------------------------------------------------
        # 5) dedup.py: 同一人物キー付与 → グループ内重複フラグ（詳細設計 3.7 / 5.6）
        # ------------------------------------------------------------------
        df_d = deduplicate_in_groups(df_g)
        log.info(
            "重複判定完了（同一人物フラグ付き明細: %d 件）",
            len(df_d),
        )

        # ------------------------------------------------------------------
        # 6) grouping: グループ集計（代表意見・件数・人数・重複件数）
        # ------------------------------------------------------------------
        summary_df = build_group_summary(df_d)

        # ------------------------------------------------------------------
        # 7) exporter.py: CSV 出力（詳細設計 3.8 / 5.7）
        # ------------------------------------------------------------------
        export_csv(df_d, summary_df, args.output_dir)
        grouped_path, details_path = output_paths(args.output_dir)
        log.info("集計CSVを出力しました: %s", grouped_path.resolve())
        log.info("明細CSVを出力しました: %s", details_path.resolve())
        log.info("処理が正常に完了しました。")
        return 0

    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error("処理中にエラーが発生しました: %s", exc)
        return 1


if __name__ == "__main__":
    # numpy / pandas の表示設定は触らず、終了コードだけ OS に返す
    raise SystemExit(main())
