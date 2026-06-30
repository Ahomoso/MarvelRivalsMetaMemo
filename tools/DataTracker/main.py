import subprocess
import tkinter as tk
from tkinter import messagebox

from browser_driver import create_driver
from match_uid_fetcher import fetch_match_uids
from match_detail_fetcher import fetch_match_details

#おれ　1032997637
#たへー　693888859
PLAYER_ID = "693888859"
SEASON = 17


class MRDataTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MR Data Tracker")
        self.root.geometry("420x320")

        self.driver = None

        self.status = tk.StringVar()
        self.status.set("待機中")

        tk.Label(root, text="MR Data Tracker", font=("Meiryo", 14)).pack(pady=10)

        tk.Button(
            root,
            text="Chrome起動",
            width=30,
            command=self.on_start_chrome
        ).pack(pady=8)

        tk.Button(
            root,
            text="match_uid取得",
            width=30,
            command=self.on_fetch_match_uids
        ).pack(pady=8)

        tk.Button(
            root,
            text="詳細取得",
            width=30,
            command=self.on_fetch_match_details
        ).pack(pady=8)

        tk.Label(root, textvariable=self.status, fg="blue").pack(pady=10)

        tk.Button(
            root,
            text="終了",
            width=30,
            command=self.on_close
        ).pack(pady=8)


    def get_driver(self):
        if self.driver is None:
            self.status.set("Chromeへ接続中...")
            self.root.update()
            self.driver = create_driver()

        return self.driver

    def on_fetch_match_uids(self):
        try:
            self.status.set("match_uid取得中...")
            self.root.update()

            driver = self.get_driver()
            match_uids = fetch_match_uids(driver, PLAYER_ID, SEASON)

            self.status.set(f"match_uid取得完了: {len(match_uids)}件")
            messagebox.showinfo("完了", f"match_uidを{len(match_uids)}件取得しました。")

        except Exception as e:
            self.status.set("エラー")
            messagebox.showerror("エラー", str(e))

    def on_fetch_match_details(self):
        try:
            self.status.set("詳細取得中...")
            self.root.update()

            driver = self.get_driver()
            saved = fetch_match_details(driver)

            self.status.set(f"詳細取得完了: {saved}件保存")
            messagebox.showinfo("完了", f"詳細を{saved}件保存しました。")

        except Exception as e:
            self.status.set("エラー")
            messagebox.showerror("エラー", str(e))

    def on_close(self):
        try:
            if self.driver:
                self.driver.close()
        finally:
            self.root.destroy()

    def on_start_chrome(self):
        try:
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

            subprocess.Popen([
                chrome_path,
                "--remote-debugging-port=9222",
                "--user-data-dir=C:\\chrome-debug"
            ])

            self.status.set("Chromeを起動しました")
            messagebox.showinfo(
                "完了",
                "Chromeをリモートデバッグモードで起動しました。"
            )

        except FileNotFoundError:
            messagebox.showerror(
                "エラー",
                "Chromeが見つかりません。"
            )

        except Exception as ex:
            messagebox.showerror(
                "エラー",
                str(ex)
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = MRDataTrackerApp(root)
    root.mainloop()