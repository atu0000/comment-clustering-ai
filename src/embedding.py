"""
embedding.py（詳細設計書 3.5 / 5.3 関数設計）

関数名:
    create_embeddings(comments: list[str], model_name: str) -> np.ndarray

処理概要（5.3）:
    - コメント一覧を埋め込みベクトルへ変換する

モジュール役割（3.5）:
    - モデルロード
    - encode 実行
    - ベクトル返却
"""

from __future__ import annotations

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from src import config

logger = logging.getLogger(__name__)


def create_embeddings(comments: list[str], model_name: str) -> np.ndarray:
    """
    コメント文字列のリストを埋め込み行列へ変換する（詳細設計 5.3）。

    sentence-transformers でエンコードし、shape (N, D) の ``float32`` 配列を返す。
    グルーピング側でコサイン類似度を使うため、ここでは ``normalize_embeddings=True`` とし、
    単位ベクトル間の内積がコサイン類似度と一致するようにする。

    Parameters
    ----------
    comments:
        前処理済みコメント（通常は ``normalized_comment`` をリスト化したもの）。
    model_name:
        利用するモデル識別子（例: ``intfloat/multilingual-e5-base``）。

    Returns
    -------
    np.ndarray
        行 i が ``comments[i]`` に対応する埋め込み。``comments`` が空のときは shape ``(0, 0)``。

    Raises
    ------
    RuntimeError
        モデル読み込みまたは ``encode`` に失敗した場合（詳細設計 10. 例外設計）。

    Notes
    -----
    multilingual-e5 系は対称タスクでも ``query:`` 接頭辞を付与する運用が推奨されることが多い。
    接頭辞・バッチサイズは ``config`` の定数に従う（5.3 外の実装都合）。
    """
    if len(comments) == 0:
        return np.zeros((0, 0), dtype=np.float32)

    try:
        logger.info("埋め込みモデルを読み込みます: %s", model_name)
        model = SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"埋め込みモデルの読み込みに失敗しました: {model_name}") from exc

    prefixed = [f"{config.E5_QUERY_PREFIX}{text}" for text in comments]

    try:
        vectors = model.encode(
            prefixed,
            batch_size=config.EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("埋め込みベクトルの計算に失敗しました（encode エラー）。") from exc

    if not isinstance(vectors, np.ndarray):
        vectors = np.asarray(vectors, dtype=np.float32)

    return vectors.astype(np.float32, copy=False)
