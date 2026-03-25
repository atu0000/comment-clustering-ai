"""
exporter.py（詳細設計書 3.8 / 5.7 関数設計）

関数名:
    ``export_csv(detail_df: pd.DataFrame, summary_df: pd.DataFrame, output_dir: str) -> None``

役割:
    集計CSV・明細CSVを出力する。

出力ファイル:
    - ``grouped_comments.csv`` … グループ集計
    - ``comment_details.csv`` … レコード明細

処理概要（5.7）:
    - 出力先ディレクトリ作成
    - CSV 保存（UTF-8）
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config


def export_csv(
    detail_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    output_dir: str | Path,
) -> None:
    """
    明細・集計の2種類のCSVを ``output_dir`` に保存する（詳細設計 5.7）。

    Parameters
    ----------
    detail_df:
        明細（``comment_details`` 想定列）。
    summary_df:
        集計（``grouped_comments`` 想定局）。
    output_dir:
        Unicode パスを扱うため ``pathlib.Path`` も受け付ける（Windows 対応）。

    Raises
    ------
    OSError
        ディレクトリ作成またはファイル書き込みに失敗した場合（詳細設計 10）。
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped_path = out_dir / config.GROUPED_OUTPUT_FILENAME
    details_path = out_dir / config.DETAILS_OUTPUT_FILENAME

    summary_cols = [
        "group_id",
        "group_label",
        "summary_comment",
        "original_comment_count",
        "unique_person_count",
        "duplicate_comment_count",
    ]
    detail_cols = [
        config.RECORD_ID_COLUMN,
        config.COMMENT_COLUMN,
        "normalized_comment",
        "group_id",
        "person_key",
        "is_duplicate_person",
    ]

    summary_out = summary_df.reindex(columns=summary_cols)
    detail_out = detail_df.reindex(columns=detail_cols)

    try:
        summary_out.to_csv(grouped_path, index=False, encoding="utf-8")
        detail_out.to_csv(details_path, index=False, encoding="utf-8")
    except OSError as exc:
        raise OSError(
            f"CSVの書き込みに失敗しました: {grouped_path} / {details_path}"
        ) from exc


def output_paths(output_dir: str | Path) -> tuple[Path, Path]:
    """
    出力CSVの絶対パス組を返す（ログ用。設計書 5.7 の戻り値 void とは別の補助）。

    main.py で保存後のパス表示に利用する。
    """
    base = Path(output_dir)
    return base / config.GROUPED_OUTPUT_FILENAME, base / config.DETAILS_OUTPUT_FILENAME
