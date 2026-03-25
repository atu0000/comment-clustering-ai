"""
dedup.py（詳細設計書 3.7 / 5.6 関数設計）

役割:
    同一人物判定を実施する。

入出力:
    入力: ``group_id`` 付き DataFrame
    出力: ``person_key`` / ``is_duplicate_person`` 付き DataFrame

処理内容:
    - name / ip_address / record_id に基づき ``person_key`` を生成（5.6）
    - グループ内で同一 ``person_key`` の2件目以降を重複とみなす（5.6）

公開API:
    ``deduplicate_in_groups`` … 上記を1回で適用（main から呼び出す想定）
    ``build_person_key`` / ``mark_duplicates`` … 詳細設計 5.6 の関数単位
"""

from __future__ import annotations

import pandas as pd

from src import config


def _is_non_empty_scalar(val: object) -> bool:
    """欠損・空文字・空白のみを「無」とみなす。"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return len(str(val).strip()) > 0


def build_person_key(row: pd.Series, name_column: str, ip_column: str) -> str:
    """
    1行分の同一人物キーを返す（詳細設計 5.6）。

    優先順位:
        1. name と ip が両方ある → ``"{name}_{ip}"``（サンプル出力の ``田中_192.168.0.1`` 形式）
        2. ip のみ
        3. name のみ
        4. どちらもない → ``record_id``（列 ``config.RECORD_ID_COLUMN``）が取れればそれ、なければ行ラベル

    Parameters
    ----------
    row:
        対象行。``iloc`` で取った Series は ``.name`` に元のインデックスが入る。
    name_column / ip_column:
        名前列・IP列の名前（通常は ``config.NAME_COLUMN`` / ``config.IP_COLUMN``）。
    """
    rid_col = config.RECORD_ID_COLUMN

    name_ok = name_column in row.index and _is_non_empty_scalar(row[name_column])
    ip_ok = ip_column in row.index and _is_non_empty_scalar(row[ip_column])

    if name_ok and ip_ok:
        name = str(row[name_column]).strip()
        ip = str(row[ip_column]).strip()
        return f"{name}_{ip}"
    if ip_ok:
        return str(row[ip_column]).strip()
    if name_ok:
        return str(row[name_column]).strip()

    if rid_col in row.index and _is_non_empty_scalar(row[rid_col]):
        return str(row[rid_col]).strip()

    # インデックスラベル（``reset_index`` 後は 0,1,2,... を想定）
    label = row.name
    if label is not None and not (isinstance(label, float) and pd.isna(label)):
        return str(label)
    return "0"


def mark_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    ``group_id`` と ``person_key`` の組合せ単位で重複を判定する（詳細設計 5.6）。

    同一グループ内で同一人物キーが再登場した行を ``is_duplicate_person=True`` とし、
    **各 (group_id, person_key) で最初に現れた行のみ False** とする。
    走査順は DataFrame の現在の行順に従う（CSV上の登場順を保持）。
    """
    if "group_id" not in df.columns:
        raise ValueError("group_id 列がありません。")
    if "person_key" not in df.columns:
        raise ValueError("person_key 列がありません。")

    out = df.copy()
    flags: list[bool] = []
    seen_keys: set[tuple[int, str]] = set()

    for _, row in out.iterrows():
        gid = int(row["group_id"])
        pk = str(row["person_key"])
        gpk = (gid, pk)
        if gpk in seen_keys:
            flags.append(True)
        else:
            seen_keys.add(gpk)
            flags.append(False)

    out["is_duplicate_person"] = flags
    return out


def add_person_keys(df: pd.DataFrame) -> pd.DataFrame:
    """
    全行に ``person_key`` を付与する。

    ``build_person_key`` を各行に適用する。行ラベルは ``iloc`` により
    DataFrame のインデックス（連番想定）が ``Series.name`` に載る。
    """
    out = df.copy()
    keys: list[str] = []
    for i in range(len(out)):
        row = out.iloc[i]
        keys.append(
            build_person_key(row, config.NAME_COLUMN, config.IP_COLUMN),
        )
    out["person_key"] = keys
    return out


def deduplicate_in_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    ``group_id`` 付きの明細に対し、人物キー付与とグループ内重複フラグを一度に行う（3.7 全体）。

    main.py からは本関数を呼ぶことで、設計書シーケンスの「dedup.py で重複判定」に相当させる。
    """
    keyed = add_person_keys(df)
    return mark_duplicates(keyed)
