"""
grouping.py（詳細設計書 3.6 / 5.4・5.5 関数設計）

5.4 assign_groups(df, embeddings, threshold)
    - 類似度行列を計算する
    - 閾値ベースで group_id を採番する
    補足アルゴリズム（貪欲）:
        1. 未所属を先頭からアンカーにする
        2. アンカーとの類似度を他全行と比較
        3. 閾値以上かつ未所属の行を同一グループへ
        4. 次の未所属へ

5.5 build_group_summary(df)
    - group_id 単位で集計
    - 元コメント件数
    - 代表コメントを summary_comment（詳細設計 6.3: 先頭コメントまたは中心コメント — 本実装は先頭）

出力CSV（基本設計）に含まれる unique_person_count / duplicate_comment_count は、
明細に ``person_key`` / ``is_duplicate_person`` がある場合のみ集計する。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


def assign_groups(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    threshold: float,
) -> pd.DataFrame:
    """
    コサイン類似度行列に基づき ``group_id``（1始まり連番）を付与する（詳細設計 5.4）。

    埋め込みが L2 正規化済みなら、行列要素 ``S[i,j] = dot(e_i, e_j)`` がコサイン類似度に一致する。

    Parameters
    ----------
    df:
        埋め込みと同じ行順の DataFrame。
    embeddings:
        shape (N, D)。行数は ``len(df)`` と一致させる。
    threshold:
        同一グループとみなす類似度の下限（例: 0.80）。

    Returns
    -------
    pd.DataFrame
        ``group_id`` を追加したコピー。
    """
    n = len(df)
    if embeddings.shape[0] != n:
        raise ValueError(
            f"行数と埋め込み件数が一致しません: df={n}, embeddings={embeddings.shape[0]}"
        )

    out = df.copy()

    if n == 0:
        out["group_id"] = pd.Series(dtype="int64")
        return out

    # 詳細設計 5.4「類似度行列を計算する」— 正規化ベクトルなら内積でコサイン類似度行列
    similarity_matrix: np.ndarray = embeddings @ embeddings.T

    assigned = np.zeros(n, dtype=bool)
    group_ids = np.zeros(n, dtype=np.int64)
    next_group_id = 0

    for anchor in range(n):
        if assigned[anchor]:
            continue
        next_group_id += 1
        # アンカー行の類似度（類似度行列の anchor 列／行）
        sims_to_anchor = similarity_matrix[anchor]

        for j in range(n):
            if assigned[j]:
                continue
            if float(sims_to_anchor[j]) >= threshold:
                assigned[j] = True
                group_ids[j] = next_group_id

    out["group_id"] = group_ids.astype(int)
    return out


def build_group_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    ``group_id`` ごとに集計行を構築する（詳細設計 5.5）。

    - ``original_comment_count``: グループ内の行数
    - ``summary_comment``: グループ内で**先頭に現れる行**のコメント本文
      （6.3 の「先頭コメント」方式。中心コメント方式は別関数化の TODO とする）

    ``person_key`` / ``is_duplicate_person`` 列が存在する場合（dedup 後想定）:
    - ``unique_person_count``
    - ``duplicate_comment_count``

    Parameters
    ----------
    df:
        ``group_id`` を含む DataFrame。dedup 済みなら ``person_key``, ``is_duplicate_person`` も含む。

    Returns
    -------
    pd.DataFrame
        基本設計の集計CSV想定列を持つ DataFrame。
    """
    base_columns = [
        "group_id",
        "summary_comment",
        "original_comment_count",
        "unique_person_count",
        "duplicate_comment_count",
    ]

    if len(df) == 0:
        return pd.DataFrame(columns=base_columns)

    if "group_id" not in df.columns:
        raise ValueError("group_id 列がありません。")

    has_dedup_cols = (
        "person_key" in df.columns and "is_duplicate_person" in df.columns
    )

    rows: list[dict] = []
    for gid in sorted(df["group_id"].unique().tolist()):
        part = df[df["group_id"] == gid]
        # 行順は明細CSVと一致するよう、現在の DataFrame の順で「先頭」を代表にする
        first = part.iloc[0]
        if config.COMMENT_COLUMN in df.columns:
            summary_text = str(first[config.COMMENT_COLUMN])
        else:
            summary_text = str(first["normalized_comment"])

        row_dict: dict = {
            "group_id": int(gid),
            "summary_comment": summary_text,
            "original_comment_count": int(len(part)),
        }

        if has_dedup_cols:
            row_dict["unique_person_count"] = int(part["person_key"].nunique(dropna=True))
            row_dict["duplicate_comment_count"] = int(part["is_duplicate_person"].sum())
        else:
            # dedup 前に呼ぶ場合のフォールバック（設計フローでは通常ここに来ない）
            row_dict["unique_person_count"] = int(len(part))
            row_dict["duplicate_comment_count"] = 0

        rows.append(row_dict)

    summary_df = pd.DataFrame(rows)
    summary_df = summary_df.reindex(columns=base_columns)
    summary_df.reset_index(drop=True, inplace=True)
    return summary_df
