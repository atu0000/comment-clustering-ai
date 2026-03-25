"""
streamlit_app.py
----------------
Streamlit UI（将来拡張 → 実装）

要望:
- CSVアップロード
- ボタンで実行
- 結果CSVのダウンロード
- DB保存・過去実行の参照（再実行なしで検索/再集計の入口）

起動例（プロジェクトルートで）:
    py -3 -m pip install -r requirements.txt
    py -3 -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from src import config
from src.db import (
    create_run,
    list_runs,
    load_comment_details,
    load_grouped_comments,
    save_run_outputs,
    search_groups,
)
from src.dedup import deduplicate_in_groups
from src.embedding import create_embeddings
from src.grouping import assign_groups, build_group_summary
from src.loader import load_input_csv
from src.preprocess import normalize_comments


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8").encode("utf-8")


def _run_pipeline_on_df(df_raw: pd.DataFrame, threshold: float, model_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    アップロードCSVの DataFrame を入力に、集計・明細を返す。
    main.py の処理を Streamlit から呼べるように最小限に並べ替えたもの。
    """
    df = normalize_comments(df_raw, config.COMMENT_COLUMN)
    if len(df) == 0:
        raise ValueError("有効コメントが0件です。comment列をご確認ください。")

    comments = df["normalized_comment"].astype(str).tolist()
    embeddings = create_embeddings(comments, model_name)
    df_g = assign_groups(df, embeddings, threshold=threshold)
    df_d = deduplicate_in_groups(df_g)
    summary_df = build_group_summary(df_d)
    return summary_df, df_d


def main() -> None:
    st.set_page_config(page_title="comment-clustering-ai", layout="wide")
    st.title("comment-clustering-ai")
    st.caption("CSV入力 → 類似グルーピング → 重複判定 → 集計CSV/明細CSV を生成し、SQLite に保存します。")

    # ---------------------------------------------------------------------
    # 表示の日本語化（アップローダーの既定英語テキスト対策）
    # Streamlit の file_uploader ドロップ領域には固定文言が出るため、CSSで上書きする。
    # 注意: Streamlit の内部DOMは将来変更される可能性があるため、効かなくなった場合は
    #       data-testid を見直す。
    # ---------------------------------------------------------------------
    st.markdown(
        """
<style>
/* Drag and drop file here → 日本語に差し替え（テキスト自体は残しつつ視覚的に隠す） */
div[data-testid="stFileUploaderDropzone"] p,
div[data-testid="stFileUploaderDropzone"] small {
  visibility: hidden;
}

div[data-testid="stFileUploaderDropzone"]::before {
  content: "ここにCSVファイルをドラッグ＆ドロップしてください";
  display: block;
  color: rgba(250, 250, 250, 0.92);
  font-size: 0.95rem;
  margin-bottom: 0.25rem;
}

div[data-testid="stFileUploaderDropzone"]::after {
  content: "（CSV形式 / 最大200MB）";
  display: block;
  color: rgba(250, 250, 250, 0.65);
  font-size: 0.80rem;
}

/* Browse files ボタンの英語を隠して日本語を表示 */
div[data-testid="stFileUploaderDropzone"] button {
  position: relative;
}
div[data-testid="stFileUploaderDropzone"] button span {
  visibility: hidden;
}
div[data-testid="stFileUploaderDropzone"] button::after {
  content: "ファイルを選択";
  visibility: visible;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["実行（CSVアップロード）", "過去実行（SQLite）"])

    with tabs[0]:
        st.subheader("実行（CSVアップロード）")

        uploaded = st.file_uploader("入力CSVをアップロード", type=["csv"])
        col1, col2, col3 = st.columns(3)
        with col1:
            threshold = st.slider("類似度閾値", min_value=0.50, max_value=0.95, value=float(config.SIMILARITY_THRESHOLD), step=0.01)
        with col2:
            model_name = st.text_input("埋め込みモデル名", value=config.EMBEDDING_MODEL_NAME)
        with col3:
            save_to_db = st.checkbox("SQLiteに保存する", value=True)

        st.write("必須列: `comment`（任意: `record_id`, `name`, `ip_address`）")

        if st.button("実行", type="primary", disabled=uploaded is None):
            try:
                if uploaded is None:
                    st.warning("CSVをアップロードしてください。")
                    return

                # CSVをDataFrameへ
                df_raw = pd.read_csv(uploaded, encoding="utf-8")
                if config.COMMENT_COLUMN not in df_raw.columns:
                    st.error(f"必須列 `{config.COMMENT_COLUMN}` が見つかりません。列: {list(df_raw.columns)}")
                    return

                with st.spinner("処理中（初回はモデルダウンロードで時間がかかることがあります）..."):
                    summary_df, detail_df = _run_pipeline_on_df(df_raw, threshold=threshold, model_name=model_name)

                st.success("完了しました。")

                st.markdown("### 集計（grouped_comments）")
                st.dataframe(summary_df, use_container_width=True)

                st.markdown("### 明細（comment_details）")
                st.dataframe(detail_df, use_container_width=True)

                st.download_button(
                    "集計CSVをダウンロード",
                    data=_df_to_csv_bytes(summary_df),
                    file_name=config.GROUPED_OUTPUT_FILENAME,
                    mime="text/csv",
                )
                st.download_button(
                    "明細CSVをダウンロード",
                    data=_df_to_csv_bytes(detail_df),
                    file_name=config.DETAILS_OUTPUT_FILENAME,
                    mime="text/csv",
                )

                if save_to_db:
                    run = create_run(
                        db_path=config.DB_PATH,
                        input_path=getattr(uploaded, "name", "uploaded.csv"),
                        model_name=model_name,
                        similarity_threshold=float(threshold),
                    )
                    save_run_outputs(config.DB_PATH, run, summary_df=summary_df, detail_df=detail_df)
                    st.info(f"SQLiteに保存しました: {config.DB_PATH} (run_id={run.run_id})")

            except Exception as exc:  # noqa: BLE001
                st.exception(exc)

    with tabs[1]:
        st.subheader("過去実行（SQLite）")
        st.write(f"DB: `{config.DB_PATH}`")

        colA, colB = st.columns([2, 1])
        with colA:
            runs_df = list_runs(config.DB_PATH, limit=50)
            st.dataframe(runs_df, use_container_width=True)
        with colB:
            query = st.text_input("検索（label / summary）", value="")
            if query.strip():
                hit = search_groups(config.DB_PATH, query.strip(), limit=50)
                st.markdown("### 検索結果（grouped_comments）")
                st.dataframe(hit, use_container_width=True)

        run_id = st.text_input("表示する run_id（上の一覧からコピー）", value="")
        if run_id.strip():
            summary = load_grouped_comments(config.DB_PATH, run_id.strip())
            details = load_comment_details(config.DB_PATH, run_id.strip())
            st.markdown("### 集計（grouped_comments）")
            st.dataframe(summary, use_container_width=True)
            st.markdown("### 明細（comment_details）")
            st.dataframe(details, use_container_width=True)

            st.download_button(
                "このrunの集計CSVをダウンロード",
                data=_df_to_csv_bytes(summary),
                file_name=f"{run_id.strip()}_{config.GROUPED_OUTPUT_FILENAME}",
                mime="text/csv",
            )
            st.download_button(
                "このrunの明細CSVをダウンロード",
                data=_df_to_csv_bytes(details),
                file_name=f"{run_id.strip()}_{config.DETAILS_OUTPUT_FILENAME}",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()

