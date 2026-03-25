"""
preprocess.py（詳細設計書 3.4 モジュール設計）

役割:
    コメント列の前処理を行う。

入出力:
    入力: pandas.DataFrame, コメント列名（関数設計 5.2）
    出力: pandas.DataFrame（``normalized_comment`` 列を追加）

処理内容（3.4）:
    - None / NaN の除外（= 正規化結果が空の行を落とす）
    - strip 実施
    - 改行を空白へ置換
    - 連続空白を1つに正規化
    - 空文字行除外

追加列:
    normalized_comment — 埋め込みの入力本文として用いる（詳細設計 6.1）。
"""

from __future__ import annotations

import re

import pandas as pd


def normalize_comments(df: pd.DataFrame, comment_column: str) -> pd.DataFrame:
    """
    ``comment_column`` を正規化し ``normalized_comment`` を付与し、無効行を除外する。

    詳細設計 5.2 ``normalize_comments(df, comment_column)`` に相当。

    Parameters
    ----------
    df:
        入力レコード。``comment_column`` を含むこと。
    comment_column:
        コメント本文が入った列名（通常は ``config.COMMENT_COLUMN``）。

    Returns
    -------
    pd.DataFrame
        ``normalized_comment`` 付き。空コメント除外後、``reset_index(drop=True)`` 済み。

    Raises
    ------
    ValueError
        ``comment_column`` が DataFrame に存在しない場合。

    Notes
    -----
    TODO: 要件定義の「記号揺れを軽微に吸収」— 全角半角統一・句読点統一などを
          ここに追加するか、別モジュールに分離するかは未決定。
    TODO: 極端に長いコメントの切り詰め（トークン上限対策）は embedding 側と相談。
    """
    if comment_column not in df.columns:
        raise ValueError(f"コメント列がありません: {comment_column}")

    out = df.copy()

    # 欠損と文字列を扱いやすくする（None/NaN は正規化で空文字扱いになり最終的に除外）
    raw = out[comment_column].astype("string")

    def _normalize_one(text: object) -> str:
        if pd.isna(text):
            return ""
        s = str(text).strip()
        # 改行・タブ等を通常スペースに寄せてから連続空白を1つに
        s = re.sub(r"\s+", " ", s.replace("\r", " ").replace("\n", " "))
        return s.strip()

    out["normalized_comment"] = raw.map(_normalize_one)

    # 空文字は対象外（設計 3.4「空文字行除外」）
    out = out[out["normalized_comment"] != ""].copy()
    out.reset_index(drop=True, inplace=True)

    return out
