"""Local protein inference; no training or remote services."""
import csv
import hashlib
import io
import math
import re
from pathlib import Path

ALPHABET = set('ACDEFGHIKLMNPQRSTVWYBXZJUO')
FIELDS = ['id', 'predicted_function_id', 'cosine_similarity', 'status', 'message',
          'sequence_length', 'known_token_fraction', 'kmer_size', 'overlap',
          'inference_epochs', 'seed', 'model_sha256']


def read_sequences(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    if not text.strip():
        raise ValueError('入力ファイルが空です。')
    records = []
    if text.lstrip().startswith('>'):
        identifier, parts = None, []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('>'):
                if identifier is not None:
                    records.append((identifier, ''.join(parts)))
                identifier, parts = line[1:].strip(), []
                if not identifier:
                    raise ValueError('FASTAのヘッダーにIDがありません。')
            else:
                if identifier is None:
                    raise ValueError('FASTAの先頭にヘッダーが必要です。')
                parts.append(line)
        records.append((identifier, ''.join(parts)))
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {'id', 'sequence'} <= set(reader.fieldnames):
            raise ValueError('CSVには id,sequence のヘッダーが必要です。旧形式はREADMEを参照してください。')
        for row in reader:
            if None in row or row.get('sequence') is None:
                raise ValueError(f'CSV {reader.line_num}行目の列数が不正です。')
            records.append((row['id'].strip(), row['sequence']))
    if not records:
        raise ValueError('配列がありません。')
    ids = [r[0] for r in records]
    if any(not identifier for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError('IDが空または重複しています。各配列に固有のIDを付けてください。')
    return records


def tokenize(sequence, k, overlap):
    if k < 1:
        raise ValueError('連続数は1以上が必要です。')
    if overlap:
        return [sequence[i:i+k] for i in range(len(sequence)-k+1)]
    tokens = [sequence[i:i+k] for i in range(0, len(sequence)-k+1, k)]
    # Reproduce split_amino.noduplicate_amino: cover the trailing remainder.
    if len(sequence) >= k and len(sequence) % k:
        tokens.append(sequence[-k:])
    return tokens


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def predict(model, records, k=3, overlap=True, epochs=None, seed=42,
            model_hash='', progress=None):
    epochs = model.epochs if epochs is None else epochs
    results = []
    for index, (identifier, raw) in enumerate(records):
        seq = re.sub(r'\s+', '', raw).upper()
        row = dict.fromkeys(FIELDS, '')
        row.update(id=identifier, sequence_length=len(seq), kmer_size=k,
                   overlap=overlap, inference_epochs=epochs, seed=seed,
                   model_sha256=model_hash, status='error')
        if not seq:
            row['message'] = '配列が空です。'
        elif set(seq) - ALPHABET:
            row['message'] = '不正なアミノ酸文字: ' + ''.join(sorted(set(seq)-ALPHABET))
        elif len(seq) < k:
            row['message'] = '配列長が連続数未満です。'
        else:
            tokens = tokenize(seq, k, overlap)
            fraction = sum(t in model.wv for t in tokens) / len(tokens)
            row['known_token_fraction'] = round(fraction, 6)
            if not fraction:
                row.update(status='unassigned', message='モデル語彙に一致する単語がありません。')
            else:
                # Reset per sequence so input ordering does not change the RNG stream.
                model.random.seed(seed)
                vector = model.infer_vector(tokens, epochs=epochs)
                label, similarity = model.dv.most_similar([vector], topn=1)[0]
                if not math.isfinite(float(similarity)):
                    raise ValueError('モデルが有限の類似度を返しませんでした。')
                row.update(predicted_function_id=str(label),
                           cosine_similarity=float(similarity), status='ok')
                if fraction < 1:
                    row['message'] = '一部の単語がモデル語彙にありません。'
        results.append(row)
        if progress:
            progress(index+1, len(records))
    return results


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')
