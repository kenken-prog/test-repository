# タンパク質機能推定GUI（最小版）

Linuxのローカルデスクトップで動くPython / Tkinterアプリです。配列ファイルを選択し、添付の学習済みDoc2Vecモデルで全長配列の機能を推定し、CSVに保存します。データやモデルの外部送信はありません。学習、Optuna、断片化、多数決、精度評価は今回の対象外です。

## Linuxでの起動

Python 3.10〜3.12を推奨します。この環境ではPython 3.12.14とGensim 4.4.0で推定処理を確認しました。
Ubuntu / Debianで必要な場合、以下を実行してください（sudoは管理者権限が必要です）。

```bash
sudo apt install python3-venv python3-tk
```

GitHubのZIPを展開し、`protein_function_gui` フォルダーを開いて次を実行します。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash run.sh
```

初回の依存ライブラリのインストールにはネット接続が必要です。以降の推定はオフラインで行えます。
Tkinterの表示にはデスクトップ環境が必要です。画面のないSSH端末だけでは起動できません。

このGitHubリポジトリには学習済みモデル・論文・研究データは含みません。手元にある `model_dv.model` を用意してください。

1. モデル選択で、手元にある `model_dv.model` を指定します。
2. FASTAまたはCSVを選択します。`examples/input.fasta` と `examples/input.csv` は形式確認用の例です。
3. 添付モデルでは連続数 **3**・**重複あり**にします。学習条件の確認欄にチェックします。
4. 「推定を実行」を押し、完了後「結果CSVを保存」を押します。

## 入力

UTF-8（BOM可）のFASTA、またはヘッダー付きCSVです。

```csv
id,sequence
protein_001,MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ
```

FASTAは複数行配列に対応しています。FASTAヘッダーの全文をIDとして保持します。
小文字は大文字に変換し、配列内の空白・改行は除去します。IDは空欄不可・重複不可です。
20標準アミノ酸に加え B/X/Z/J/U/O を受け付けます。ハイフン、数字、終止記号 `*` はエラーにします。
空配列・短すぎる配列・不正文字はその行だけエラーとしてCSVに記録します。

添付の旧コードはヘッダーなしで既知データの4列目、未知データの3列目を配列として読み込んでいました。元データの列の意味が未確認のため、自動判別はしません。旧データを使う場合は、ID列と配列列を取り出して上記CSVに変換してください。

## 出力

Excelでも読みやすいUTF-8 BOM付きCSVです。入力順に1配列1行を出力します。

- `id`: 入力ID
- `predicted_function_id`: 最類似のDoc2Vecタグ（添付モデルではCOG ID）
- `cosine_similarity`: コサイン類似度。確率・正解率ではありません
- `status`: `ok`（推定済）、`error`（入力不正）、`unassigned`（全単語が語彙外）
- `message`: エラー・語彙外単語に関する説明
- `sequence_length`, `known_token_fraction`: 配列長とモデル語彙に含まれる単語の割合
- `kmer_size`, `overlap`, `inference_epochs`, `seed`: 推定条件
- `model_sha256`: 使用したモデル本体のSHA-256

閾値による判定は行いません。低い類似度でも最類似タグを返します。機能名への変換にはCOG IDと機能名の対応表が別途必要です。

## 推定処理と確認状況

アミノ酸配列を指定された連続数で単語に分割し、Doc2Vecの `infer_vector` と `dv.most_similar(topn=1)` で最も類似するタグを返します。連続数と重複の有無は学習時と一致させてください。
推定epochsにはモデルのepochsを使用し、配列ごとにseed=42を設定します。run.shではPYTHONHASHSEED=0を指定します。ライブラリ・CPU等の違いにより数値差が生じる場合があります。

単体テスト3件で入力形式、配列分割、小規模モデルの保存・読み込み・推定、異常入力の処理を確認しました。GUIの画面操作と利用先のLinux上での動作は未確認です。予測精度は利用する学習済みモデルとデータに依存します。

```bash
.venv/bin/python -m unittest discover -s tests -v
```

学習済みモデルはPython pickleを含むため、信頼できるファイルのみ読み込んでください。モデルに関連 .npy ファイルがある場合は、元の名前のまま同じフォルダーに配置します。
