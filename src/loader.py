"""
loader.py（詳細設計書 3.3 モジュール設計）

役割:
    入力CSVファイルを読み込む。

入出力:
    入力: ファイルパス、必須列名リスト（関数設計 5.1）
    出力: pandas.DataFrame

処理内容（3.3 に明示された範囲）:
    - ファイル存在チェック
    - CSV読込
    - 必須列チェック

文字コードは基本設計に従い UTF-8 とする。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config


def load_input_csv(file_path: str | Path, required_columns: list[str]) -> pd.DataFrame:
    """
    指定CSVを読み込み、必須列の存在を確認した DataFrame を返す。

    詳細設計 5.1 `load_input_csv(file_path: str, required_columns: list[str])` に相当。
    Windows では `pathlib.Path` を渡せるよう `file_path` は Path も受け付ける。

    Parameters
    ----------
    file_path:
        入力CSVのパス。
    required_columns:
        CSV に必ず含まれるべき列名（例: ``[config.COMMENT_COLUMN]``）。

    Returns
    -------
    pd.DataFrame
        読み込んだレコード。

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合（詳細設計 10. 例外設計）。
    ValueError
        必須列が不足している場合。

    Notes
    -----
    TODO: 詳細設計 3.3 には「任意列の補完」が含まれていない。
          現状、dedup が ``name`` / ``ip_address`` / ``record_id`` を参照するため、
          欠損列があれば下記ループで NA 列を追加している。この挙動を設計書へ追記するか、
          loader を純化して dedup 前段の専用関数へ移すか要判断。
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"入力CSVが見つかりません: {path.resolve()}")

    # 基本設計: CSV の文字コードは UTF-8 を基本とする
    # TODO: BOM 付き UTF-8（utf-8-sig）や cp932 の自動判別が必要なら encoding 引数を設ける
    df = pd.read_csv(path, encoding="utf-8")

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"必須列が不足しています: {missing}. 実際の列: {list(df.columns)}"
        )

    # TODO(上記 Notes): 設計 3.3 外の暫定処理 — 下流で KeyError にならないよう任意列を補う
    _optional_for_dedup = [
        config.RECORD_ID_COLUMN,
        config.NAME_COLUMN,
        config.IP_COLUMN,
    ]
    for col in _optional_for_dedup:
        if col not in df.columns:
            df[col] = pd.NA

    return df
