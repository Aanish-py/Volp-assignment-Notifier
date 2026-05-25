import sys
import traceback

def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"FATAL ERROR:\n{error_msg}", file=sys.stderr)
    if sys.stderr:
        try:
            sys.stderr.flush()
        except:
            pass

sys.excepthook = global_exception_handler

import customtkinter as ctk
import threading
import logging
import os
import time
import schedule
import json
from dotenv import load_dotenv, set_key
from pathlib import Path

# ─── Resolve paths correctly whether running as script or .exe ────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

ENV_FILE = BASE_DIR / ".env"
TOKEN_FILE = BASE_DIR / "token.json"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
ASSIGNMENTS_FILE = BASE_DIR / "assignments.json"
LATEST_SCRAPE_FILE = BASE_DIR / "latest_scrape.json"

# Add BASE_DIR to path so imports work when run as bundled .exe
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

# ─── GUI Logger Handler ────────────────────────────────────────────────────────
class TextBoxHandler(logging.Handler):
    """Forwards Python log records into a CTkTextbox widget."""
    def __init__(self, textbox: ctk.CTkTextbox):
        super().__init__()
        self.textbox = textbox

    def emit(self, record):
        msg = self.format(record) + "\n"
        self.textbox.after(0, self._append, msg, record.levelno)

    def _append(self, msg, levelno):
        self.textbox.configure(state="normal")
        tag = "ERROR" if levelno >= logging.ERROR else \
              "WARNING" if levelno >= logging.WARNING else \
              "INFO"
        self.textbox.insert("end", msg, tag)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


# ─── App ──────────────────────────────────────────────────────────────────────
class AssignmentAutomatorApp(ctk.CTk):  
    def __init__(self):
        super().__init__()
        self.title("📚 University Assignment Automator")
        self.geometry("900x680")
        self.minsize(800, 580)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._scheduler_running = False
        self._scheduler_thread = None

        load_dotenv(ENV_FILE)
        self._build_ui()
        self._setup_logging()
        self.logger.info("Application started. Ready to check assignments!")

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Left Sidebar ──────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo_lbl = ctk.CTkLabel(
            self.sidebar,
            text="🎓\nAssignment\nAutomator",
            font=ctk.CTkFont(size=18, weight="bold"),
            justify="center"
        )
        logo_lbl.pack(pady=(30, 20))

        ctk.CTkButton(
            self.sidebar, text="⚙️  Settings",
            command=lambda: self._show_tab("settings")
        ).pack(pady=6, padx=16, fill="x")

        ctk.CTkButton(
            self.sidebar, text="▶️  Controls",
            command=lambda: self._show_tab("controls")
        ).pack(pady=6, padx=16, fill="x")

        ctk.CTkButton(
            self.sidebar, text="📊  Assignments",
            command=lambda: self._show_tab("assignments")
        ).pack(pady=6, padx=16, fill="x")

        ctk.CTkButton(
            self.sidebar, text="📋  Logs",
            command=lambda: self._show_tab("logs")
        ).pack(pady=6, padx=16, fill="x")

        # Status indicator at bottom of sidebar
        self.status_dot = ctk.CTkLabel(self.sidebar, text="⚫  Idle", anchor="w")
        self.status_dot.pack(side="bottom", pady=20, padx=16)

        # ── Main container ────────────────────────────────────────────────────
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Build each "tab" as a frame, only one shown at a time
        self._tabs = {}
        self._build_settings_tab()
        self._build_controls_tab()
        self._build_assignments_tab()
        self._build_logs_tab()

        # Open Settings on first launch so new users can enter their credentials
        self._show_tab("settings" if not ENV_FILE.exists() else "controls")

    def _show_tab(self, name: str):
        for key, frame in self._tabs.items():
            frame.pack_forget()
        self._tabs[name].pack(fill="both", expand=True)

    # ── Settings Tab ──────────────────────────────────────────────────────────
    def _build_settings_tab(self):
        frame = ctk.CTkScrollableFrame(self.main, label_text="⚙️ Settings")
        self._tabs["settings"] = frame

        # Show welcome banner only on first run (no .env file yet)
        if not ENV_FILE.exists():
            banner = ctk.CTkFrame(frame, fg_color="#1a3a5c", corner_radius=8)
            banner.pack(fill="x", padx=10, pady=(10, 4))
            ctk.CTkLabel(
                banner,
                text="👋  Welcome!  Enter your details below and click Save Settings to get started.",
                text_color="#7ec8ff",
                font=ctk.CTkFont(size=13, weight="bold"),
                wraplength=520,
                justify="left"
            ).pack(padx=14, pady=10)

        def row(label, key, show=""):
            ctk.CTkLabel(frame, text=label, anchor="w").pack(fill="x", padx=10, pady=(10, 0))
            entry = ctk.CTkEntry(frame, show=show, width=500)
            entry.insert(0, os.getenv(key, ""))
            entry.pack(fill="x", padx=10, pady=(2, 0))
            return entry, key

        self._env_fields = []
        self._env_fields.append(row("Portal URL", "PORTAL_URL"))
        self._env_fields.append(row("Portal Username / Email", "PORTAL_USER"))
        self._env_fields.append(row("Portal Password", "PORTAL_PASS", show="●"))


        ctk.CTkButton(
            frame, text="💾  Save Settings",
            fg_color="#1a7f4b", hover_color="#155c37",
            command=self._save_settings
        ).pack(pady=20, padx=10, fill="x")

        sep = ctk.CTkLabel(frame, text="── Google Tasks ──", text_color="gray")
        sep.pack(pady=(10, 4))

        self.auth_status_lbl = ctk.CTkLabel(frame, text="", anchor="w")
        self.auth_status_lbl.pack(fill="x", padx=10)
        self._refresh_auth_status()

        ctk.CTkButton(
            frame, text="🔑  Connect Google Tasks",
            command=self._google_auth_thread
        ).pack(pady=8, padx=10, fill="x")

        ctk.CTkButton(
            frame, text="🗑️  Reset Google Token",
            fg_color="#7f1a1a", hover_color="#5c1515",
            command=self._reset_google_token
        ).pack(pady=4, padx=10, fill="x")



    def _save_settings(self):
        if not ENV_FILE.exists():
            ENV_FILE.write_text("")
        for (entry, key) in self._env_fields:
            set_key(str(ENV_FILE), key, entry.get())
        load_dotenv(ENV_FILE, override=True)
        self.logger.info("Settings saved to .env file.")

    def _refresh_auth_status(self):
        if TOKEN_FILE.exists():
            self.auth_status_lbl.configure(
                text="✅ Google token found – you are connected.",
                text_color="#3dc969"
            )
        else:
            self.auth_status_lbl.configure(
                text="❌ No Google token – click Connect to authorise.",
                text_color="#e05c5c"
            )

    def _google_auth_thread(self):
        threading.Thread(target=self._google_auth, daemon=True).start()

    def _google_auth(self):
        self.logger.info("Starting Google Tasks authorisation…")
        try:
            from task_creator import TaskCreator
            tc = TaskCreator()
            if tc.service:
                self.logger.info("Google Tasks authorised successfully!")
            else:
                self.logger.error("Google authorisation failed. Check credentials.json exists.")
        except Exception as e:
            self.logger.error(f"Google auth error: {e}")
        self.after(0, self._refresh_auth_status)

    def _reset_google_token(self):
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            self.logger.info("Google token deleted. Re-connect to re-authorise.")
            self._refresh_auth_status()
        else:
            self.logger.info("No token file found – nothing to delete.")



    # ── Controls Tab ──────────────────────────────────────────────────────────
    def _build_controls_tab(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self._tabs["controls"] = frame

        ctk.CTkLabel(
            frame,
            text="Assignment Automator Controls",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(30, 8))

        ctk.CTkLabel(
            frame,
            text="Run a one-off check or keep the scheduler running in the background.",
            text_color="gray"
        ).pack(pady=(0, 30))

        # Run Now card
        card1 = ctk.CTkFrame(frame)
        card1.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(card1, text="▶️  Run Check Now", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(16, 4))
        ctk.CTkLabel(card1, text="Scrapes the portal once and creates Google Tasks for new assignments.", text_color="gray", justify="center").pack(pady=(0, 12))
        ctk.CTkButton(
            card1, text="Run Now",
            height=40,
            command=self._run_now_thread
        ).pack(pady=(0, 16), padx=20, fill="x")

        # Scheduler card
        card2 = ctk.CTkFrame(frame)
        card2.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(card2, text="🕐  Auto-Scheduler", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(16, 4))
        ctk.CTkLabel(card2, text="Runs automatically every 12 hours in the background.", text_color="gray").pack(pady=(0, 12))

        sched_row = ctk.CTkFrame(card2, fg_color="transparent")
        sched_row.pack(pady=(0, 16), padx=20, fill="x")

        self.start_sched_btn = ctk.CTkButton(
            sched_row, text="▶  Start Scheduler",
            fg_color="#1a7f4b", hover_color="#155c37",
            command=self._start_scheduler
        )
        self.start_sched_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.stop_sched_btn = ctk.CTkButton(
            sched_row, text="■  Stop Scheduler",
            fg_color="#7f1a1a", hover_color="#5c1515",
            state="disabled",
            command=self._stop_scheduler
        )
        self.stop_sched_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))

    def _run_now_thread(self):
        self._set_status("🟡  Running…", "#e0b03d")
        self._show_tab("logs")
        threading.Thread(target=self._run_check_safe, daemon=True).start()

    def _run_check_safe(self):
        try:
            load_dotenv(ENV_FILE, override=True)
            from main import run_check
            run_check()
        except Exception as e:
            self.logger.error(f"Check failed: {e}")
        self.after(0, lambda: self._set_status("⚫  Idle", "gray"))

    def _start_scheduler(self):
        if self._scheduler_running:
            return
        self._scheduler_running = True
        self.start_sched_btn.configure(state="disabled")
        self.stop_sched_btn.configure(state="normal")
        self._set_status("🟢  Scheduled", "#3dc969")
        self.logger.info("Scheduler started – will run every 12 hours.")
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def _scheduler_loop(self):
        schedule.clear()
        load_dotenv(ENV_FILE, override=True)
        from main import run_check
        run_check()
        schedule.every(12).hours.do(run_check)
        while self._scheduler_running:
            schedule.run_pending()
            time.sleep(30)

    def _stop_scheduler(self):
        self._scheduler_running = False
        schedule.clear()
        self.start_sched_btn.configure(state="normal")
        self.stop_sched_btn.configure(state="disabled")
        self._set_status("⚫  Idle", "gray")
        self.logger.info("Scheduler stopped.")

    # ── Assignments Tab ───────────────────────────────────────────────────────
    def _build_assignments_tab(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self._tabs["assignments"] = frame

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(top, text="📊 Pending Assignments", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Refresh", width=70, command=self._refresh_assignments).pack(side="right")

        self.assignments_scroll = ctk.CTkScrollableFrame(frame)
        self.assignments_scroll.pack(fill="both", expand=True)
        
        self._refresh_assignments()

    def _refresh_assignments(self):
        # Clear existing cards
        for widget in self.assignments_scroll.winfo_children():
            widget.destroy()
            
        if not LATEST_SCRAPE_FILE.exists():
            ctk.CTkLabel(self.assignments_scroll, text="No assignment data found. Run a check first!", text_color="gray").pack(pady=20)
            return
            
        try:
            with open(LATEST_SCRAPE_FILE, "r") as f:
                assignments = json.load(f)
                
            if not assignments:
                ctk.CTkLabel(self.assignments_scroll, text="No pending assignments! All caught up.", text_color="#3dc969").pack(pady=20)
                return
                
            for a in assignments:
                card = ctk.CTkFrame(self.assignments_scroll, corner_radius=8)
                card.pack(fill="x", padx=10, pady=5)
                
                title = a.get("title", "Unknown Title")
                course = a.get("course", "Unknown Course")
                deadline = a.get("deadline", "Check Portal")
                
                # Title
                ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 2))
                
                # Course & Deadline
                bottom_row = ctk.CTkFrame(card, fg_color="transparent")
                bottom_row.pack(fill="x", padx=10, pady=(0, 10))
                
                ctk.CTkLabel(bottom_row, text=f"🎓 {course}", text_color="gray", anchor="w").pack(side="left")
                
                dl_color = "#e0b03d" if "Check Portal" in deadline else "#e05c5c"
                ctk.CTkLabel(bottom_row, text=f"🕒 {deadline}", text_color=dl_color, anchor="e").pack(side="right")
                
        except Exception as e:
            ctk.CTkLabel(self.assignments_scroll, text=f"Error loading data: {e}", text_color="#e05c5c").pack(pady=20)

    # ── Live Logs Tab ─────────────────────────────────────────────────────────
    def _build_logs_tab(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self._tabs["logs"] = frame

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(top, text="📋 Live Logs", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Clear", width=70, command=self._clear_logs).pack(side="right")

        self.log_box = ctk.CTkTextbox(frame, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True)

        # Configure coloured tags
        self.log_box.tag_config("ERROR", foreground="#e05c5c")
        self.log_box.tag_config("WARNING", foreground="#e0b03d")
        self.log_box.tag_config("INFO", foreground="#aaffaa")

    def _clear_logs(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ── Logging Setup ─────────────────────────────────────────────────────────
    def _setup_logging(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
                                datefmt="%H:%M:%S")

        # File handler (keep existing automator.log)
        fh = logging.FileHandler(BASE_DIR / "automator.log", encoding="utf-8")
        fh.setFormatter(fmt)

        # GUI handler
        gh = TextBoxHandler(self.log_box)
        gh.setFormatter(fmt)

        # Avoid duplicating if the root logger already has handlers
        self.logger.handlers.clear()
        self.logger.addHandler(fh)
        self.logger.addHandler(gh)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_status(self, text: str, color: str = "white"):
        self.status_dot.configure(text=text, text_color=color)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        app = AssignmentAutomatorApp()
        app.mainloop()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        traceback.print_exc()
        input("Press Enter to exit...")
