import subprocess
import sqlite3
import tkinter as tk
from tkinter import messagebox

from collector.browser_driver import create_driver
from collector.match_detail_fetcher import fetch_match_details
from collector.match_uid_fetcher import fetch_match_uids
from collector.top500_stats_fetcher import fetch_top500_stats
from config import load_config
from collector.db_register import register_matches_from_files
from sql_utils import load_sql


CONFIG = load_config()
DB_PATH = CONFIG.database_path
SQL_PRUNE_NON_RANK_MATCH_UIDS = load_sql("collector/collector_prune_non_rank_match_uids.sql")
SQL_DELETE_MATCH_PLAYER_HEROES = load_sql("collector/db_delete_match_player_heroes.sql")
SQL_DELETE_MATCH_PLAYERS = load_sql("collector/db_delete_match_players.sql")
SQL_DELETE_MATCHES = load_sql("collector/db_delete_matches.sql")


class CollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(CONFIG.collector_title)
        self.root.geometry("460x470")
        self.root.resizable(False, False)

        self.driver = None
        self.status = tk.StringVar(value="idle")
        self.target_uid = tk.StringVar(value=CONFIG.default_player_uid)
        self._widgets = []

        tk.Label(root, text="Collector", font=("Meiryo", 14)).pack(pady=10)

        uid_frame = tk.Frame(root)
        uid_frame.pack(pady=4)
        tk.Label(uid_frame, text="Target UID", width=10, anchor="w").pack(side=tk.LEFT)
        entry = tk.Entry(uid_frame, textvariable=self.target_uid, width=28)
        entry.pack(side=tk.LEFT)
        self._widgets.append(entry)

        self._add_button(root, "1. Start Chrome", self.on_start_chrome)
        self._add_button(root, "2. Fetch match_uids", self.on_fetch_match_uids)
        self._add_button(root, "3. Fetch match details", self.on_fetch_match_details)
        self._add_button(root, "4. Register DB", self.on_register_db)
        self._add_button(root, "5. TOP500 Stats Update", self.on_update_top500_stats)
        self._add_button(root, "6. Delete quick/custom data", self.on_delete_quick_custom_data)
        tk.Label(root, textvariable=self.status, fg="blue").pack(pady=10)
        self._add_button(root, "Close", self.on_close)

    def _add_button(self, root, text, command):
        button = tk.Button(root, text=text, width=30, command=command)
        button.pack(pady=8)
        self._widgets.append(button)
        return button

    def _set_busy(self, busy: bool):
        cursor = "watch" if busy else ""
        self.root.configure(cursor=cursor)
        for widget in self._widgets:
            try:
                widget.configure(state="disabled" if busy else "normal")
            except tk.TclError:
                pass
        self.root.update_idletasks()

    def _run_busy(self, status_text: str, func):
        self._set_busy(True)
        try:
            self.status.set(status_text)
            self.root.update()
            return func()
        finally:
            self._set_busy(False)

    def get_driver(self):
        if self.driver is None:
            self.status.set("Starting Chrome...")
            self.root.update()
            self.driver = create_driver()
        return self.driver

    def _get_target_uid(self) -> str:
        player_id = self.target_uid.get().strip()
        if not player_id:
            raise ValueError("Target UID is required")
        return player_id

    def on_fetch_match_uids(self):
        try:
            player_id = self._get_target_uid()
            driver = self.get_driver()
            match_uids = self._run_busy(
                "Fetching match_uids for all targets...",
                lambda: fetch_match_uids(driver, player_id, CONFIG.season),
            )
            self.status.set(f"Fetched {len(match_uids)} match_uids")
            messagebox.showinfo("Done", f"Fetched {len(match_uids)} match_uids")
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Error", str(e))

    def on_fetch_match_details(self):
        try:
            driver = self.get_driver()
            player_id = self._get_target_uid()
            saved = self._run_busy(
                "Fetching match details...",
                lambda: fetch_match_details(driver, player_id),
            )
            self.status.set(f"Fetched {saved} match details")
            messagebox.showinfo("Done", f"Saved {saved} match details")
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Error", str(e))

    def on_register_db(self):
        try:
            count = self._run_busy("Registering DB...", register_matches_from_files)
            self.status.set(f"Registered {count} matches")
            messagebox.showinfo("Done", f"Registered {count} matches into DB")
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Error", str(e))

    def on_update_top500_stats(self):
        try:
            driver = self.get_driver()
            def run_update():
                try:
                    return fetch_top500_stats(driver)
                except Exception as inner_exc:
                    message = str(inner_exc).lower()
                    if "target window already closed" in message or "web view not found" in message:
                        self._reset_driver()
                        retry_driver = self.get_driver()
                        return fetch_top500_stats(retry_driver)
                    raise

            count = self._run_busy("Updating TOP500 stats...", run_update)
            self.status.set(f"Updated TOP500 stats: {count}")
            messagebox.showinfo("Done", f"Updated {count} hero stats")
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Error", str(e))

    def on_delete_quick_custom_data(self):
        try:
            count = self._run_busy("Deleting quick/custom data...", self._delete_quick_custom_data)
            self.status.set(f"Deleted {count} matches")
            messagebox.showinfo("Done", f"Deleted {count} quick/custom matches")
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Error", str(e))

    def on_close(self):
        try:
            if self.driver:
                self.driver.quit()
        finally:
            self.root.destroy()

    def on_start_chrome(self):
        try:
            subprocess.Popen(
                [
                    CONFIG.chrome_path,
                    f"--remote-debugging-port={CONFIG.chrome_debug_port}",
                    f"--user-data-dir={CONFIG.chrome_user_data_dir}",
                ]
            )
            self.status.set("Chrome started")
            self.root.after(200, self._restore_focus)
        except FileNotFoundError:
            messagebox.showerror("Error", "Chrome not found")
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def _restore_focus(self):
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def _delete_quick_custom_data(self) -> int:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            cur = conn.cursor()
            cur.execute(SQL_PRUNE_NON_RANK_MATCH_UIDS)
            match_uids = [row[0] for row in cur.fetchall()]
            if not match_uids:
                return 0

            for match_uid in match_uids:
                conn.execute(SQL_DELETE_MATCH_PLAYER_HEROES, (match_uid,))
                conn.execute(SQL_DELETE_MATCH_PLAYERS, (match_uid,))
                conn.execute(SQL_DELETE_MATCHES, (match_uid,))

            conn.commit()
            return len(match_uids)
        finally:
            conn.close()

    def _reset_driver(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
