import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from collector.collector_app import CollectorApp
from config import load_config


BASE_DIR = Path(__file__).resolve().parent


class LauncherApp:
    def __init__(self, root):
        self.config = load_config()
        self.root = root
        self.root.title(self.config.launcher_title)
        self.root.geometry("360x240")
        self.root.resizable(False, False)

        tk.Label(root, text=self.config.app_name, font=("Meiryo", 14)).pack(pady=12)
        tk.Label(root, text="起動する機能を選択してください", font=("Meiryo", 10)).pack(pady=4)

        tk.Button(
            root,
            text="集積装置を開く",
            width=24,
            command=self.open_collector,
        ).pack(pady=10)

        tk.Button(
            root,
            text="ビュワーを開く",
            width=24,
            command=self.open_viewer,
        ).pack(pady=6)

        tk.Button(
            root,
            text="終了",
            width=24,
            command=self.root.destroy,
        ).pack(pady=18)

        tk.Button(
            root,
            text="設定を開く",
            width=24,
            command=self.open_config,
        ).pack(pady=2)

    def _open_child(self, factory, title):
        window = tk.Toplevel(self.root)
        window.title(title)
        factory(window)
        window.transient(self.root)
        window.grab_set()

    def open_collector(self):
        # Collector is Tk-based, so it can live as a child window in this process.
        self._open_child(CollectorApp, self.config.collector_title)

    def open_viewer(self):
        # Viewer uses a Qt event loop, so it is launched in a separate process.
        subprocess.Popen([sys.executable, "-m", "viewer.viewer_app"], cwd=str(BASE_DIR))

    def open_config(self):
        config_path = BASE_DIR / "app_config.json"
        if not config_path.exists():
            messagebox.showerror("エラー", f"設定ファイルが見つかりません: {config_path}")
            return
        subprocess.Popen(["explorer", str(config_path)])


if __name__ == "__main__":
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()
