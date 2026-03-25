"""
db.py
-----
SQLite へ集計結果・明細結果を保存し、再実行なしで参照できるようにするモジュール。

要望:
- DB保存・再集計: 集計結果や明細を SQLite 等のDBに保存し、再実行なしで再集計・検索できるようにする

方針:
- sqlite3（標準ライブラリ）で完結させる（Windowsでも追加依存なし）
- pandas DataFrame は to_sql を使わず、テーブルを作って executemany で投入する
  （pandas.to_sql は環境によって SQLAlchemy 依存が出るため避ける）
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


@dataclass(frozen=True)
class RunInfo:
    """1回の実行（run）を表すメタ情報。"""

    run_id: str
    created_at: str  # ISO 8601
    input_path: str
    model_name: str
    similarity_threshold: float


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def ensure_schema(db_path: str | Path) -> None:
    """必要なテーブルが無ければ作成する。"""
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              input_path TEXT NOT NULL,
              model_name TEXT NOT NULL,
              similarity_threshold REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS grouped_comments (
              run_id TEXT NOT NULL,
              group_id INTEGER NOT NULL,
              group_label TEXT,
              summary_comment TEXT,
              original_comment_count INTEGER,
              unique_person_count INTEGER,
              duplicate_comment_count INTEGER,
              PRIMARY KEY (run_id, group_id),
              FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS comment_details (
              run_id TEXT NOT NULL,
              row_no INTEGER NOT NULL,
              record_id TEXT,
              comment TEXT,
              normalized_comment TEXT,
              group_id INTEGER,
              person_key TEXT,
              is_duplicate_person INTEGER,
              PRIMARY KEY (run_id, row_no),
              FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            """
        )
        con.commit()
    finally:
        con.close()


def create_run(
    db_path: str | Path,
    input_path: str,
    model_name: str,
    similarity_threshold: float,
) -> RunInfo:
    """
    runs テーブルに1件作成し、run_id を返す。

    run_id は created_at をベースに一意化する（同秒複数実行の可能性があるので末尾に連番を付ける）。
    """
    ensure_schema(db_path)
    created_at = _utc_now_iso()
    base = created_at.replace(":", "").replace("-", "")
    run_id = f"run_{base}"

    con = _connect(db_path)
    try:
        # 同秒重複を避けるため、INSERT 失敗時に _2, _3... を付与
        suffix = 1
        while True:
            try_id = run_id if suffix == 1 else f"{run_id}_{suffix}"
            try:
                con.execute(
                    """
                    INSERT INTO runs(run_id, created_at, input_path, model_name, similarity_threshold)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (try_id, created_at, input_path, model_name, float(similarity_threshold)),
                )
                con.commit()
                return RunInfo(
                    run_id=try_id,
                    created_at=created_at,
                    input_path=input_path,
                    model_name=model_name,
                    similarity_threshold=float(similarity_threshold),
                )
            except sqlite3.IntegrityError:
                suffix += 1
    finally:
        con.close()


def save_grouped_comments(db_path: str | Path, run_id: str, summary_df: pd.DataFrame) -> None:
    """grouped_comments へ集計行を保存する。"""
    ensure_schema(db_path)
    cols = [
        "group_id",
        "group_label",
        "summary_comment",
        "original_comment_count",
        "unique_person_count",
        "duplicate_comment_count",
    ]
    df = summary_df.reindex(columns=cols).copy()

    rows: list[tuple[Any, ...]] = []
    for _, r in df.iterrows():
        rows.append(
            (
                run_id,
                int(r["group_id"]) if pd.notna(r["group_id"]) else None,
                None if pd.isna(r["group_label"]) else str(r["group_label"]),
                None if pd.isna(r["summary_comment"]) else str(r["summary_comment"]),
                int(r["original_comment_count"]) if pd.notna(r["original_comment_count"]) else None,
                int(r["unique_person_count"]) if pd.notna(r["unique_person_count"]) else None,
                int(r["duplicate_comment_count"]) if pd.notna(r["duplicate_comment_count"]) else None,
            )
        )

    con = _connect(db_path)
    try:
        con.executemany(
            """
            INSERT OR REPLACE INTO grouped_comments(
              run_id, group_id, group_label, summary_comment,
              original_comment_count, unique_person_count, duplicate_comment_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.commit()
    finally:
        con.close()


def save_comment_details(db_path: str | Path, run_id: str, detail_df: pd.DataFrame) -> None:
    """comment_details へ明細行を保存する。"""
    ensure_schema(db_path)
    cols = [
        "record_id",
        "comment",
        "normalized_comment",
        "group_id",
        "person_key",
        "is_duplicate_person",
    ]
    df = detail_df.reindex(columns=cols).copy()

    rows: list[tuple[Any, ...]] = []
    for i, (_, r) in enumerate(df.iterrows()):
        rows.append(
            (
                run_id,
                int(i),
                None if pd.isna(r["record_id"]) else str(r["record_id"]),
                None if pd.isna(r["comment"]) else str(r["comment"]),
                None if pd.isna(r["normalized_comment"]) else str(r["normalized_comment"]),
                int(r["group_id"]) if pd.notna(r["group_id"]) else None,
                None if pd.isna(r["person_key"]) else str(r["person_key"]),
                1 if bool(r["is_duplicate_person"]) else 0,
            )
        )

    con = _connect(db_path)
    try:
        con.executemany(
            """
            INSERT OR REPLACE INTO comment_details(
              run_id, row_no, record_id, comment, normalized_comment,
              group_id, person_key, is_duplicate_person
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.commit()
    finally:
        con.close()


def save_run_outputs(
    db_path: str | Path,
    run: RunInfo,
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
) -> None:
    """run に紐付けて summary/details をまとめて保存する。"""
    save_grouped_comments(db_path, run.run_id, summary_df)
    save_comment_details(db_path, run.run_id, detail_df)


def list_runs(db_path: str | Path, limit: int = 50) -> pd.DataFrame:
    """runs の一覧を新しい順で返す。"""
    ensure_schema(db_path)
    con = _connect(db_path)
    try:
        return pd.read_sql_query(
            """
            SELECT run_id, created_at, input_path, model_name, similarity_threshold
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            con,
            params=(int(limit),),
        )
    finally:
        con.close()


def load_grouped_comments(db_path: str | Path, run_id: str) -> pd.DataFrame:
    """指定 run_id の grouped_comments を返す。"""
    ensure_schema(db_path)
    con = _connect(db_path)
    try:
        return pd.read_sql_query(
            """
            SELECT group_id, group_label, summary_comment,
                   original_comment_count, unique_person_count, duplicate_comment_count
            FROM grouped_comments
            WHERE run_id = ?
            ORDER BY group_id
            """,
            con,
            params=(run_id,),
        )
    finally:
        con.close()


def load_comment_details(db_path: str | Path, run_id: str) -> pd.DataFrame:
    """指定 run_id の comment_details を返す。"""
    ensure_schema(db_path)
    con = _connect(db_path)
    try:
        return pd.read_sql_query(
            """
            SELECT record_id, comment, normalized_comment, group_id, person_key, is_duplicate_person
            FROM comment_details
            WHERE run_id = ?
            ORDER BY row_no
            """,
            con,
            params=(run_id,),
        )
    finally:
        con.close()


def search_groups(
    db_path: str | Path,
    query: str,
    limit: int = 50,
) -> pd.DataFrame:
    """
    再計算なしで「検索」できる最小機能。
    - group_label / summary_comment に query を含むグループを検索
    """
    ensure_schema(db_path)
    q = f"%{query}%"
    con = _connect(db_path)
    try:
        return pd.read_sql_query(
            """
            SELECT run_id, group_id, group_label, summary_comment,
                   original_comment_count, unique_person_count, duplicate_comment_count
            FROM grouped_comments
            WHERE group_label LIKE ? OR summary_comment LIKE ?
            ORDER BY run_id DESC, group_id ASC
            LIMIT ?
            """,
            con,
            params=(q, q, int(limit)),
        )
    finally:
        con.close()


def delete_runs(db_path: str | Path, run_ids: list[str]) -> int:
    """
    指定した run_id を削除する（複数対応）。

    runs を削除すると、外部キーの ON DELETE CASCADE により
    grouped_comments / comment_details も自動的に削除される。

    Returns
    -------
    int
        削除対象として指定された run_id の件数（存在しないIDも含む）。
    """
    ensure_schema(db_path)
    if len(run_ids) == 0:
        return 0

    con = _connect(db_path)
    try:
        con.executemany(
            "DELETE FROM runs WHERE run_id = ?",
            [(rid,) for rid in run_ids],
        )
        con.commit()
        return len(run_ids)
    finally:
        con.close()


def delete_all_runs(db_path: str | Path) -> None:
    """
    全履歴（runs）を削除する。
    CASCADE により明細・集計も削除される。
    """
    ensure_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM runs;")
        con.commit()
    finally:
        con.close()

