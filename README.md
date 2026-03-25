# Comment Clustering AI

AI（自然言語処理）を用いて、類似するコメントを自動でグルーピングし、件数を集計するPythonアプリケーションです。

---

## 📌 概要
CSV形式のコメントデータを入力として、意味的に近いコメント同士をクラスタリングし、テーマごとに整理します。  
アンケート分析やレビュー分析などの業務効率化を目的としています。

---

## 🎯 背景・目的
大量の自由記述コメントを手作業で分類するのは非効率であり、分析コストが高いという課題があります。  
本アプリでは、AIを活用してコメントの自動分類を行い、業務効率の向上を目指しました。

---

## ⚙️ 主な機能

- CSVファイルの読み込み
- テキストの前処理（不要文字除去・正規化）
- 埋め込み（ベクトル化）
- 類似度計算によるクラスタリング
- グループごとの件数集計
- 結果のCSV出力

---

## 🧠 使用技術

- Python 3.11
- pandas
- scikit-learn
- sentence-transformers
- numpy

---

## 📂 ディレクトリ構成

```text
comment-clustering-ai/
├── src/               # メイン処理
├── input/             # 入力データ
├── output/            # 出力結果
├── docs/              # 要件定義・設計書
├── requirements.txt
└── README.md


---

## ▶️ 実行方法

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -m src.main

---