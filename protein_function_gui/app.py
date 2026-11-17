"""Launch with python app.py. Models are selected locally, never uploaded."""
import os
os.environ.setdefault('PYTHONHASHSEED', '0')
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from core import read_sequences, predict, fingerprint, csv_bytes


class App:
    def __init__(self, root):
        self.root = root
        root.title('タンパク質機能推定 | Doc2Vec')
        root.geometry('760x570')
        self.events = queue.Queue()
        self.result = None
        self.model_path = tk.StringVar()
        self.input_path = tk.StringVar()
        self.k = tk.StringVar(value='3')
        self.overlap = tk.BooleanVar(value=True)
        self.confirmed = tk.BooleanVar(value=False)
        panel = ttk.Frame(root, padding=22)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='タンパク質機能推定', font=('', 20, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='ファイルを選択 → 推定を実行 → 結果CSVを保存').pack(anchor='w', pady=(5, 18))
        for label, variable, types in [
            ('1. 学習済みモデル（信頼できる研究室のファイルのみ）', self.model_path, [('Doc2Vec', '*.model'), ('All', '*')]),
            ('2. 配列ファイル（FASTA または id,sequence のCSV）', self.input_path, [('Sequences', '*.fasta *.fa *.faa *.csv *.txt'), ('All', '*')])]:
            ttk.Label(panel, text=label).pack(anchor='w')
            line = ttk.Frame(panel)
            line.pack(fill='x', pady=(4, 12))
            ttk.Entry(line, textvariable=variable).pack(side='left', fill='x', expand=True)
            ttk.Button(line, text='選択', command=lambda v=variable, t=types: self.choose(v, t)).pack(side='right', padx=(8, 0))
        options = ttk.Frame(panel)
        options.pack(fill='x', pady=6)
        ttk.Label(options, text='学習時の連続アミノ酸数').pack(side='left')
        ttk.Spinbox(options, from_=1, to=30, textvariable=self.k, width=5).pack(side='left', padx=10)
        ttk.Checkbutton(options, text='重複あり', variable=self.overlap).pack(side='left')
        ttk.Checkbutton(panel, text='連続数・重複の有無がモデルの学習条件と一致することを確認しました', variable=self.confirmed).pack(anchor='w', pady=6)
        ttk.Label(panel, text='モデルの関連 .npy ファイルは元の名前のまま同じフォルダーに置いてください。\n類似度は確率・正解率ではありません。結果は機能IDです。', wraplength=700).pack(anchor='w', pady=8)
        actions = ttk.Frame(panel)
        actions.pack(fill='x', pady=10)
        self.run_button = ttk.Button(actions, text='3. 推定を実行', command=self.run)
        self.run_button.pack(side='left')
        self.save_button = ttk.Button(actions, text='4. 結果CSVを保存', command=self.save, state='disabled')
        self.save_button.pack(side='left', padx=12)
        self.bar = ttk.Progressbar(panel, mode='determinate')
        self.bar.pack(fill='x', pady=8)
        self.status = tk.StringVar(value='モデルと配列ファイルを選択してください。')
        ttk.Label(panel, textvariable=self.status, wraplength=700).pack(anchor='w')
        root.after(100, self.poll)

    def choose(self, variable, types):
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            variable.set(path)

    def run(self):
        try:
            k = int(self.k.get())
            if not 1 <= k <= 30:
                raise ValueError('連続数は1〜30にしてください。')
            if not self.confirmed.get():
                raise ValueError('モデルの学習条件を確認してチェックしてください。')
            model_path, input_path = self.model_path.get(), self.input_path.get()
            if not Path(model_path).is_file() or not Path(input_path).is_file():
                raise ValueError('モデルと配列ファイルを選択してください。')
            records = read_sequences(input_path)
        except (ValueError, OSError, UnicodeError) as exc:
            messagebox.showerror('入力を確認してください', str(exc))
            return
        self.result = None
        self.save_button.config(state='disabled')
        self.run_button.config(state='disabled')
        self.status.set('モデルを読み込み中…')
        self.bar['value'] = 0
        overlap = self.overlap.get()
        threading.Thread(target=self.worker, args=(model_path, records, k, overlap), daemon=True).start()

    def worker(self, path, records, k, overlap):
        try:
            from gensim.models.doc2vec import Doc2Vec
            model = Doc2Vec.load(path)
            if not len(model.dv) or not len(model.wv):
                raise ValueError('モデルに語彙または機能タグがありません。')
            rows = predict(model, records, k, overlap, model_hash=fingerprint(path),
                           progress=lambda n, total: self.events.put(('progress', (n, total))))
            self.events.put(('done', rows))
        except Exception as exc:
            self.events.put(('error', f'{type(exc).__name__}: {exc}'))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'progress':
                    n, total = data
                    self.bar['value'] = 100*n/total
                    self.status.set(f'推定中: {n} / {total}')
                else:
                    self.run_button.config(state='normal')
                    if kind == 'done':
                        self.result = csv_bytes(data)
                        ok = sum(r['status'] == 'ok' for r in data)
                        self.status.set(f'完了: {len(data)}件中 {ok}件を推定。未推定・入力エラーはCSVで確認できます。')
                        self.save_button.config(state='normal')
                    else:
                        self.status.set('処理に失敗しました。モデル・関連ファイル・実行環境を確認してください。')
                        messagebox.showerror('推定エラー', data)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='predictions.csv', filetypes=[('CSV', '*.csv')])
        if path:
            try:
                Path(path).write_bytes(self.result)
                self.status.set(f'保存しました: {path}')
            except OSError as exc:
                messagebox.showerror('保存エラー', str(exc))


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
