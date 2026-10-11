"""IBKR Portfolio Advisor - Windows desktop app (read-only: never places orders)."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")
import numpy as np  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import demo  # noqa: E402
import gateway  # noqa: E402
from analytics import Settings  # noqa: E402
from pipeline import compute, load_data  # noqa: E402

# ---------------------------------------------------------------- theme
C_BG, C_SIDE, C_CARD, C_LINE = "#0f1115", "#14171c", "#1a1d24", "#262a33"
C_TXT, C_MUTED = "#e8eaed", "#8b919c"
C_ACC, C_GREEN, C_RED, C_AMBER = "#4c9be8", "#3ecf8e", "#ff6b6b", "#f0b429"
FONT = "Segoe UI"
CFG_PATH = Path(os.getenv("APPDATA") or Path.home()) / "IBKR-Advisor" / "config.json"
DEFAULTS = dict(host="127.0.0.1", port=4001, client_id=17, gateway_path="", years="1", rf="3.0",
                max_w="20", vol="", extras="", fmp_key="")
# connection state -> (dot colour, sidebar text)
CONN = {"up": (C_GREEN, "IB Gateway connected"),
        "starting": (C_AMBER, "Waiting for IB Gateway login..."),
        "down": (C_RED, "IB Gateway not running - click to launch"),
        "error": (C_RED, "")}
ACTION_COLOR = {"CLOSE": C_RED, "SELL (REDUCE)": "#ff9f6b", "BUY MORE": C_GREEN,
                "BUY (NEW)": C_ACC, "HOLD": C_MUTED}
HEAT = LinearSegmentedColormap.from_list("heat", ["#b3453f", "#2a2d35", "#2f9e6e"])


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_cfg(cfg: dict):
    try:
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


def isnan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))


def pct(x, d=1, sign=False):
    return "-" if isnan(x) else f"{x * 100:{'+' if sign else ''}.{d}f}%"


def num(x, d=2):
    return "-" if isnan(x) else f"{x:,.{d}f}"


def flt(text: str, default: float) -> float:
    try:
        return float(str(text).replace(",", ".").strip())
    except ValueError:
        return default


def font(size=13, weight="normal"):
    return ctk.CTkFont(FONT, size, weight)


# ---------------------------------------------------------------- widgets
class Kpi(ctk.CTkFrame):
    def __init__(self, master, title, fmt, higher_better=True):
        super().__init__(master, fg_color=C_CARD, corner_radius=12)
        self.fmt, self.hb = fmt, higher_better
        ctk.CTkLabel(self, text=title, text_color=C_MUTED, font=font(12)).pack(anchor="w", padx=16, pady=(14, 0))
        self.v = ctk.CTkLabel(self, text="-", font=font(28, "bold"))
        self.v.pack(anchor="w", padx=16)
        self.s = ctk.CTkLabel(self, text=" ", text_color=C_MUTED, font=font(12))
        self.s.pack(anchor="w", padx=16, pady=(0, 14))

    def set(self, cur, prop):
        self.v.configure(text=self.fmt(cur))
        if isnan(prop) or isnan(cur) or abs(prop - cur) < 1e-9:
            self.s.configure(text="same when proposed" if not isnan(prop) else " ", text_color=C_MUTED)
            return
        good = None if self.hb is None else ((prop > cur) == self.hb)
        color = C_MUTED if good is None else C_GREEN if good else C_RED
        self.s.configure(text=f"{'▲' if prop > cur else '▼'} {self.fmt(prop)} proposed", text_color=color)


def make_table(parent, cols, widths, left=(0,), stretch=None, height=12):
    card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=12)
    tv = ttk.Treeview(card, columns=cols, show="headings", height=height, selectmode="browse")
    for i, (c, w) in enumerate(zip(cols, widths)):
        tv.heading(c, text=c, anchor="w" if i in left else "e")
        tv.column(c, width=w, anchor="w" if i in left else "e", stretch=(c == stretch))
    sb = ttk.Scrollbar(card, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
    sb.pack(side="right", fill="y", pady=10, padx=(0, 6))
    return card, tv


def mpl_card(parent, figsize):
    card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=12)
    fig = Figure(figsize=figsize, facecolor=C_CARD)
    canvas = FigureCanvasTkAgg(fig, master=card)
    canvas.get_tk_widget().configure(bg=C_CARD, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
    return card, fig, canvas


def style_axes(ax):
    ax.set_facecolor(C_CARD)
    ax.tick_params(colors=C_MUTED, labelsize=9, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)


class Dialog(ctk.CTkToplevel):
    def __init__(self, master, title, size):
        super().__init__(master, fg_color=C_BG)
        self.title(title)
        self.geometry(size)
        self.resizable(False, False)
        self.transient(master)
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def field(self, parent, row, label, var, show=None):
        ctk.CTkLabel(parent, text=label, text_color=C_MUTED, font=font(12)).grid(
            row=row, column=0, sticky="w", pady=7, padx=(0, 14))
        ctk.CTkEntry(parent, textvariable=var, show=show, fg_color=C_CARD, border_color=C_LINE,
                     height=32).grid(row=row, column=1, sticky="ew")


class SettingsDialog(Dialog):
    def __init__(self, master, cfg, on_save):
        super().__init__(master, "Settings", "520x690")
        self.cfg, self.on_save = cfg, on_save
        ctk.CTkLabel(self, text="Settings", font=font(20, "bold")).pack(pady=(22, 4))
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=36, pady=10)
        form.columnconfigure(1, weight=1)
        rows = [("IB Gateway path (blank = auto)", "gateway_path"), ("API host", "host"),
                ("API port (live: 4001)", "port"), ("Client ID", "client_id"),
                ("History (years, 1-5)  *", "years"), ("Risk-free rate (%)", "rf"),
                ("Max weight per position (%)", "max_w"), ("Volatility cap (%, optional)", "vol"),
                ("Extra candidate tickers  *", "extras"), ("FMP API key (P/E history)  *", "fmp_key")]
        self.vars = {k: tk.StringVar(value=str(cfg[k])) for _, k in rows}
        for i, (label, k) in enumerate(rows):
            self.field(form, i, label, self.vars[k], show="*" if k == "fmp_key" else None)
        ctk.CTkLabel(self, wraplength=420, justify="left", text_color=C_MUTED, font=font(11),
                     text="* applied on the next 'Refresh data'.\n\nWithout an FMP key the average P/E uses "
                          "Yahoo's last ~4 annual reports. A free key from financialmodelingprep.com gives "
                          "longer history (up to 15 years, depending on your plan). The key is stored in "
                          "plain text in your user profile.").pack(padx=36, pady=6, anchor="w")
        self.err = ctk.CTkLabel(self, text="", text_color=C_RED)
        self.err.pack()
        ctk.CTkButton(self, text="Save", height=38, command=self.save).pack(fill="x", padx=36, pady=(4, 14))

    def save(self):
        vals = {k: v.get().strip() for k, v in self.vars.items()}
        try:
            vals["port"], vals["client_id"] = int(vals["port"]), int(vals["client_id"])
        except ValueError:
            self.err.configure(text="Port and client ID must be integers.")
            return
        vals["host"] = vals["host"] or "127.0.0.1"
        self.cfg.update(vals)
        save_cfg(self.cfg)
        self.destroy()
        self.on_save()


# ---------------------------------------------------------------- app
class App(ctk.CTk):
    PAGES = [("overview", "Overview"), ("suggestions", "Suggestions"), ("positions", "Positions"),
             ("valuation", "Valuation (P/E)"), ("sectors", "Sector momentum"), ("discover", "Discover")]

    def __init__(self):
        super().__init__(fg_color=C_BG)
        ctk.set_appearance_mode("dark")
        self.title("IBKR Portfolio Advisor")
        self.geometry("1360x860")
        self.minsize(1180, 740)
        self.cfg = load_cfg()
        self.q: queue.Queue = queue.Queue()
        self.busy, self.raw, self.result = False, None, None
        self.conn, self.auto_loaded = None, False
        self.launch_req, self.wake = False, threading.Event()
        self._style_tables()
        self._sidebar()
        self._content()
        self.show_page("overview")
        self.after(150, self._poll)
        threading.Thread(target=self._watch_gateway, daemon=True).start()

    # ------------------------------------------------------------ layout
    def _style_tables(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.configure("Treeview", background=C_CARD, fieldbackground=C_CARD, foreground=C_TXT,
                     rowheight=34, borderwidth=0, font=(FONT, 11))
        st.configure("Treeview.Heading", background=C_CARD, foreground=C_MUTED, relief="flat",
                     borderwidth=0, padding=(8, 8), font=(FONT, 10, "bold"))
        st.map("Treeview", background=[("selected", "#262d3b")], foreground=[("selected", C_TXT)])
        st.map("Treeview.Heading", background=[("active", C_CARD)])
        st.configure("Vertical.TScrollbar", background=C_LINE, troughcolor=C_CARD, borderwidth=0,
                     arrowsize=0, gripcount=0)

    def _sidebar(self):
        side = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color=C_SIDE)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ctk.CTkLabel(side, text="Portfolio Advisor", font=font(19, "bold")).pack(anchor="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(side, text="Interactive Brokers  -  read-only", text_color=C_MUTED,
                     font=font(11)).pack(anchor="w", padx=20, pady=(0, 22))
        self.nav = {}
        for key, label in self.PAGES:
            b = ctk.CTkButton(side, text=label, anchor="w", height=38, corner_radius=8, fg_color="transparent",
                              hover_color="#1d222b", text_color=C_MUTED, font=font(13),
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=12, pady=2)
            self.nav[key] = b

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=16)
        self.progress = ctk.CTkProgressBar(bottom, height=4, mode="indeterminate", progress_color=C_ACC,
                                           fg_color=C_LINE)
        self.progress.pack(fill="x", pady=(0, 6))
        self.progress.set(0)
        self.status = ctk.CTkLabel(bottom, text="", text_color=C_MUTED, font=font(11),
                                   wraplength=200, justify="left", anchor="w")
        self.status.pack(fill="x", pady=(0, 6))
        conn = ctk.CTkFrame(bottom, fg_color=C_CARD, corner_radius=8)
        conn.pack(fill="x", pady=(0, 8))
        self.conn_dot = ctk.CTkLabel(conn, text="\u25cf", text_color=C_MUTED, font=font(16), width=18)
        self.conn_dot.pack(side="left", padx=(10, 4), pady=6)
        self.conn_lbl = ctk.CTkLabel(conn, text="Checking IB Gateway...", text_color=C_MUTED, font=font(11),
                                     wraplength=160, justify="left", anchor="w")
        self.conn_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        for w in (conn, self.conn_dot, self.conn_lbl):
            w.bind("<Button-1>", self._conn_click)
        self.btn_refresh = ctk.CTkButton(bottom, text="Refresh data", height=32, fg_color="#232833",
                                         hover_color="#2b3140", command=self.refresh)
        self.btn_refresh.pack(fill="x", pady=3)
        self.btn_re = ctk.CTkButton(bottom, text="Re-analyze", height=32, fg_color="#232833",
                                    hover_color="#2b3140", state="disabled", command=self.reanalyze)
        self.btn_re.pack(fill="x", pady=3)
        ctk.CTkButton(bottom, text="Settings", height=32, fg_color="transparent", border_width=1,
                      border_color=C_LINE, text_color=C_MUTED,
                      command=lambda: SettingsDialog(self, self.cfg, self._settings_saved)).pack(fill="x", pady=3)
        ctk.CTkButton(bottom, text="Try demo data", height=26, fg_color="transparent", hover_color="#1d222b",
                      text_color=C_MUTED, font=font(11),
                      command=lambda: self._start(demo_mode=True)).pack(fill="x", pady=(3, 0))

    def _content(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=24, pady=20)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.pack(fill="x")
        self.title_lbl = ctk.CTkLabel(head, text="Overview", font=font(26, "bold"), anchor="w")
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = ctk.CTkLabel(head, text="Log in to IB Gateway to load your portfolio.", text_color=C_MUTED,
                                    font=font(13), anchor="w", justify="left")
        self.sub_lbl.pack(anchor="w", pady=(2, 0))
        self.warn_lbl = ctk.CTkLabel(main, text="", text_color=C_AMBER, font=font(12), anchor="w",
                                     justify="left", wraplength=1000)
        self.warn_lbl.pack_forget()
        self.head = head
        ctk.CTkLabel(main, text="Educational tool, not investment advice. Historical, in-sample statistics "
                                "do not predict future returns.", text_color="#5b616c",
                     font=font(10)).pack(side="bottom", anchor="w", pady=(8, 0))
        self.body = ctk.CTkFrame(main, fg_color="transparent")
        self.body.pack(fill="both", expand=True, pady=(12, 0))
        self.pages = {k: ctk.CTkFrame(self.body, fg_color="transparent") for k, _ in self.PAGES}
        self._page_overview(self.pages["overview"])
        self._page_suggestions(self.pages["suggestions"])
        self._page_positions(self.pages["positions"])
        self._page_valuation(self.pages["valuation"])
        self._page_sectors(self.pages["sectors"])
        self._page_discover(self.pages["discover"])

    def _note(self, parent, text):
        ctk.CTkLabel(parent, text=text, text_color=C_MUTED, font=font(12), anchor="w", justify="left",
                     wraplength=1000).pack(fill="x", pady=(0, 8))

    def _page_overview(self, p):
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self.kpis = {}
        for i, (k, title, fmt, hb) in enumerate([
                ("sharpe", "Sharpe ratio", num, True), ("ret", "Annual return", pct, True),
                ("vol", "Volatility", pct, False), ("mdd", "Max drawdown", pct, True),
                ("beta", "Beta vs SPY", num, None), ("eff_n", "Effective positions", lambda x: num(x, 1), True)]):
            row.columnconfigure(i, weight=1, uniform="k")
            self.kpis[k] = Kpi(row, title, fmt, hb)
            self.kpis[k].grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
        self.oos_lbl = ctk.CTkLabel(p, text="", text_color=C_MUTED, font=font(12), anchor="w", justify="left",
                                    wraplength=1000)
        self.oos_lbl.pack(fill="x", pady=(12, 8))
        card, self.fig_ov, self.cv_ov = mpl_card(p, (10, 4.2))
        card.pack(fill="both", expand=True)

    def _page_suggestions(self, p):
        self.sug_note = ctk.CTkLabel(p, text="", text_color=C_MUTED, font=font(12), anchor="w")
        self.sug_note.pack(fill="x", pady=(0, 8))
        card, self.t_sug = make_table(p, ("Symbol", "Action", "Now", "Target", "~Shares", "~Value", "Why"),
                                      (90, 130, 70, 70, 80, 110, 640), left=(0, 1, 6), stretch="Why", height=10)
        card.pack(fill="both", expand=True)
        for a, c in ACTION_COLOR.items():
            self.t_sug.tag_configure(a, foreground=c)
        self.sug_detail = ctk.CTkLabel(p, text="Select a row to read the full reasoning.", text_color=C_MUTED,
                                       font=font(12), anchor="w", justify="left", wraplength=1000, height=44)
        self.sug_detail.pack(fill="x", pady=(8, 0))
        self.t_sug.bind("<<TreeviewSelect>>", self._sug_select)

    def _sug_select(self, _e=None):
        sel = self.t_sug.selection()
        if sel:
            v = self.t_sug.item(sel[0], "values")
            self.sug_detail.configure(text=f"{v[0]} - {v[1]}: {v[6]}", text_color=C_TXT)

    def _page_positions(self, p):
        card, self.t_pos = make_table(
            p, ("Symbol", "Qty", "Price", "Value", "Weight", "Return", "Vol", "Sharpe", "% of risk",
                "Corr. rest", "Unreal. P&L"), (90, 80, 120, 110, 80, 80, 80, 80, 90, 90, 120), stretch="Unreal. P&L")
        card.pack(fill="both", expand=True)

    def _page_valuation(self, p):
        self.val_note = ctk.CTkLabel(p, text="", text_color=C_MUTED, font=font(12), anchor="w",
                                     justify="left", wraplength=1000)
        self.val_note.pack(fill="x", pady=(0, 8))
        card, self.t_val = make_table(
            p, ("Symbol", "Held", "P/E (TTM)", "Fwd P/E", "Avg 5y", "Avg 10y", "Avg 15y", "vs avg", "Signal"),
            (90, 70, 90, 90, 100, 100, 100, 90, 110), left=(0, 8), stretch="Signal")
        card.pack(fill="both", expand=True)
        for a, c in (("Cheap", C_GREEN), ("Expensive", C_RED), ("Fair", C_TXT), ("-", C_MUTED)):
            self.t_val.tag_configure(a, foreground=c)

    def _page_sectors(self, p):
        self._note(p, "S&P 500 sectors (SPDR ETFs) ranked by momentum score = average of 3M, 6M and 12-1M "
                      "returns (the last month is skipped, as in the classic momentum factor). "
                      "RS = 3M return relative to SPY. Last column: price above/below its 200-day average.")
        card, self.fig_sec, self.cv_sec = mpl_card(p, (10, 5))
        card.pack(fill="both", expand=True)

    def _page_discover(self, p):
        self._note(p, "Candidates ranked by how much adding 5% would improve your portfolio's Sharpe ratio "
                      "(low correlation with your holdings helps most).")
        card, self.t_cand = make_table(
            p, ("Symbol", "Name", "Category", "Return", "Vol", "Sharpe", "Corr.", "d Sharpe +5%", "d Vol +5%"),
            (80, 230, 220, 80, 80, 80, 70, 110, 100), left=(0, 1, 2), stretch="Category")
        card.pack(fill="both", expand=True)

    def show_page(self, key):
        for k, f in self.pages.items():
            f.pack_forget()
        for k, b in self.nav.items():
            b.configure(fg_color="#232833" if k == key else "transparent",
                        text_color=C_TXT if k == key else C_MUTED)
        self.pages[key].pack(fill="both", expand=True)
        self.title_lbl.configure(text=dict(self.PAGES)[key])
        self.current = key

    # ------------------------------------------------------------ actions
    def _watch_gateway(self):
        """Background thread: launch IB Gateway at startup if needed, then probe its API port."""
        launched_at = None
        try:
            if not gateway.port_open(self.cfg["host"], int(self.cfg["port"])) and not gateway.is_running():
                exe = gateway.launch(self.cfg["gateway_path"])
                launched_at = time.time()
                self.q.put(("status", f"Started {exe}"))
        except Exception as e:  # noqa: BLE001
            self.q.put(("conn", ("error", str(e))))
            self.wake.wait(5)
        while True:
            self.wake.clear()
            try:
                if self.launch_req:
                    self.launch_req = False
                    gateway.launch(self.cfg["gateway_path"])
                    launched_at = time.time()
                if gateway.port_open(self.cfg["host"], int(self.cfg["port"])):
                    state = ("up", "")
                elif gateway.is_running() or (launched_at and time.time() - launched_at < 120):
                    state = ("starting", "")
                else:
                    state = ("down", "")
            except Exception as e:  # noqa: BLE001
                state = ("error", str(e))
            self.q.put(("conn", state))
            self.wake.wait(3)

    def _conn_click(self, _e=None):
        if self.conn in ("down", "error"):
            self.launch_req = True
            self.conn_lbl.configure(text="Launching IB Gateway...")
            self.wake.set()

    def _set_conn(self, state, detail):
        color, text = CONN[state]
        self.conn_dot.configure(text_color=color)
        self.conn_lbl.configure(text=detail or text)
        for w in (self.conn_dot, self.conn_lbl):
            w.configure(cursor="hand2" if state in ("down", "error") else "")
        if state == "up" and not self.auto_loaded and not self.busy:
            self.auto_loaded = True  # first login -> load the portfolio automatically
            self.refresh()
        self.conn = state

    def _settings_saved(self):
        self.wake.set()  # re-probe in case host/port changed
        self.reanalyze()

    def settings(self) -> Settings:
        vol = flt(self.cfg["vol"], 0.0)
        return Settings(rf=flt(self.cfg["rf"], 3.0) / 100,
                        max_weight=min(max(flt(self.cfg["max_w"], 20), 5), 100) / 100,
                        vol_cap=vol / 100 if vol > 0 else None)

    def refresh(self):
        self._start()

    def reanalyze(self):
        if self.raw is not None:
            self._start(reuse=True)

    def _start(self, reuse=False, demo_mode=False):
        if self.busy:
            return
        self.busy = True
        self.progress.start()
        for b in (self.btn_refresh, self.btn_re):
            b.configure(state="disabled")
        s = self.settings()
        cfg = dict(host=self.cfg["host"], port=int(self.cfg["port"]), client_id=int(self.cfg["client_id"]),
                   years=int(min(max(flt(self.cfg["years"], 1), 1), 5)), fmp_key=self.cfg["fmp_key"],
                   extras=[t for t in self.cfg["extras"].replace(";", ",").split(",") if t.strip()])
        raw = self.raw if reuse else None
        say = lambda m: self.q.put(("status", m))  # noqa: E731

        def work():
            try:
                r = demo.make_demo_raw() if demo_mode else (raw if raw is not None else load_data(cfg, say))
                if not reuse:
                    r["fmp_key"] = cfg["fmp_key"] if not demo_mode else ""
                self.q.put(("raw", r))
                say("Analyzing...")
                self.q.put(("result", compute(r, s, say)))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.q.put(("error", str(e) or repr(e)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "conn":
                    self._set_conn(*payload)
                elif kind == "status":
                    self.status.configure(text=payload)
                elif kind == "raw":
                    self.raw = payload
                elif kind == "result":
                    self._idle("Up to date")
                    self.show(payload)
                elif kind == "error":
                    self._idle("Failed")
                    self._warn(f"Error: {payload}", C_RED)
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _warn(self, text, color):
        self.warn_lbl.configure(text=text, text_color=color)
        if text:
            self.warn_lbl.pack(fill="x", pady=(6, 0), after=self.head)
        else:
            self.warn_lbl.pack_forget()

    def _idle(self, msg):
        self.busy = False
        self.progress.stop()
        self.progress.set(0)
        self.status.configure(text=msg)
        for b in (self.btn_refresh, self.btn_re):
            b.configure(state="normal")

    # ------------------------------------------------------------ render
    def show(self, r: dict):
        a = r["account"]
        self.result = r
        self.sub_lbl.configure(
            text=f"Account {a['accounts']}   -   Net liquidation {a['nav']:,.0f} {a['base']}   -   "
                 f"Analysed {r['total']:,.0f} {a['base']}   -   Cash {a['cash']:,.0f} {a['base']}   -   "
                 f"{r['n_days']} trading days")
        self._warn("  ".join(r["warnings"]), C_AMBER)

        c, p = r["current"], r["proposed"]
        for k, kpi in self.kpis.items():
            kpi.set(c[k], p[k])
        o = r["oos"]
        self.oos_lbl.configure(text=(
            f"Reality check: fitted on the first 70% of the history, judged on the last {o['days']} days: "
            f"Sharpe {num(o['current'])} (your portfolio) vs {num(o['proposed'])} (proposed). If the proposal "
            "doesn't win here, treat the in-sample gain as noise.") if o else "")
        self._draw_overview(r)

        for t in (self.t_sug, self.t_pos, self.t_val, self.t_cand):
            t.delete(*t.get_children())
        counts = {}
        for s in r["suggestions"]:
            counts[s["action"]] = counts.get(s["action"], 0) + 1
            act = s["action"] != "HOLD"
            self.t_sug.insert("", "end", tags=(s["action"],), values=(
                s["symbol"], s["action"], pct(s["cur_w"]), pct(s["tgt_w"]),
                f"{s['shares']:,}" if act else "-", f"{s['value']:+,.0f}" if act else "-", s["why"]))
        self.sug_note.configure(text="   ".join(f"{n} x {k}" for k, n in counts.items()) +
                                f"   (values in {a['base']}, within your invested stock/ETF capital)")
        for d in sorted(r["positions"], key=lambda d: -d["weight"]):
            self.t_pos.insert("", "end", values=(
                d["symbol"], f"{d['qty']:,.0f}", f"{d['price']:,.2f} {d['currency']}", f"{d['value']:,.0f}",
                pct(d["weight"]), pct(d["ret"]), pct(d["vol"]), num(d["sharpe"]), pct(d["risk"]),
                num(d["corr"]), f"{d['pnl']:+,.0f}"))
        for v in r["valuation"]:
            def avg(k):
                n = v[f"n{k}"]
                return "-" if v[f"avg{k}"] is None else f"{v[f'avg{k}']:.1f}" + ("" if n >= int(k) else f" ({n}y)")
            self.t_val.insert("", "end", tags=(v["signal"],), values=(
                v["symbol"], pct(v["weight"]) if v["weight"] is not None else "new", num(v["pe"], 1),
                num(v["fwd"], 1), avg("5"), avg("10"), avg("15"), pct(v["prem"], 0, True), v["signal"]))
        self.val_note.configure(text=(
            "Current P/E compared with its own history. " + (
                "Averages from FMP annual ratios; '(ny)' means only n years were available."
                if r.get("has_fmp") else
                "No FMP key set: averages are rebuilt from Yahoo's last annual reports (about 4 years). "
                "Add a free FMP key in Settings for up to 15 years.") +
            "  Signal: Cheap < -15% vs the 10y average (5y if unavailable), Expensive > +15%. "
            "A low P/E can also mean falling earnings."))
        for d in r["candidates"][:25]:
            self.t_cand.insert("", "end", values=(
                d["symbol"], d["name"], d["category"], pct(d["ret"]), pct(d["vol"]), num(d["sharpe"]),
                num(d["corr"]), f"{d['d_sharpe']:+.3f}", f"{d['d_vol'] * 100:+.2f} pt"))
        self._draw_sectors(r["sectors"])

    def _draw_overview(self, r):
        self.fig_ov.clear()
        ax1, ax2 = self.fig_ov.subplots(1, 2, gridspec_kw={"width_ratios": [3, 2]})
        for ax in (ax1, ax2):
            style_axes(ax)
        colors = {"Current": C_ACC, "Proposed (in-sample)": C_GREEN, "SPY": "#777c88"}
        for col in r["curves"].columns:
            ax1.plot(r["curves"].index, r["curves"][col], label=col, color=colors.get(col), lw=1.8)
        ax1.set_title("Growth of 1 (constant weights)", color=C_TXT, fontsize=11, loc="left")
        ax1.legend(facecolor=C_CARD, labelcolor=C_TXT, edgecolor=C_LINE, fontsize=9, frameon=False)
        ax1.grid(color=C_LINE, lw=0.6)
        cur, tgt = r["weights_cur"], r["weights_tgt"]
        syms = [s for s in dict.fromkeys(list(cur) + list(tgt)) if cur.get(s, 0) > 0.005 or tgt.get(s, 0) > 0.005]
        syms.sort(key=lambda s: max(cur.get(s, 0), tgt.get(s, 0)))
        y = np.arange(len(syms))
        ax2.barh(y - 0.19, [cur.get(s, 0) * 100 for s in syms], 0.36, color=C_ACC, label="Current")
        ax2.barh(y + 0.19, [tgt.get(s, 0) * 100 for s in syms], 0.36, color=C_GREEN, label="Proposed")
        ax2.set_yticks(y, syms)
        ax2.set_title("Weights (%)", color=C_TXT, fontsize=11, loc="left")
        ax2.legend(facecolor=C_CARD, labelcolor=C_TXT, edgecolor=C_LINE, fontsize=9, frameon=False)
        self.fig_ov.tight_layout()
        self.cv_ov.draw()

    def _draw_sectors(self, rows):
        self.fig_sec.clear()
        ax = self.fig_sec.subplots()
        style_axes(ax)
        if not rows:
            ax.text(0.5, 0.5, "No sector data", color=C_MUTED, ha="center", transform=ax.transAxes)
            self.cv_sec.draw()
            return
        cols = [("m1", "1M"), ("m3", "3M"), ("m6", "6M"), ("m12", "12M"), ("m12_1", "12-1M"), ("rs3", "RS vs SPY (3M)")]
        data = np.array([[d[k] for k, _ in cols] for d in rows], dtype=float)
        ax.imshow(np.nan_to_num(np.clip(data, -0.3, 0.3)), cmap=HEAT, vmin=-0.3, vmax=0.3, aspect="auto",
                  extent=(-0.5, len(cols) - 0.5, len(rows) - 0.5, -0.5))
        ax.set_xlim(-0.5, len(cols) + 0.5)
        ax.set_ylim(len(rows) - 0.5, -0.5)
        for i in range(len(rows)):
            for j in range(len(cols)):
                v = data[i, j]
                ax.text(j, i, "-" if np.isnan(v) else f"{v * 100:+.1f}%", ha="center", va="center",
                        color="white", fontsize=10, fontweight="bold" if j == 4 else "normal")
            up = rows[i]["above200"]
            ax.text(len(cols), i, "▲ above" if up else "▼ below", ha="center", va="center",
                    color=C_GREEN if up else C_RED, fontsize=9)
        for x in np.arange(-0.5, len(cols), 1):
            ax.axvline(x, color=C_CARD, lw=2)
        for yv in np.arange(-0.5, len(rows), 1):
            ax.axhline(yv, color=C_CARD, lw=2)
        ax.set_xticks(list(range(len(cols))) + [len(cols)], [n for _, n in cols] + ["vs 200d avg"])
        ax.set_yticks(range(len(rows)), [f"{d['rank']}. {d['name']} ({d['etf']})" for d in rows])
        ax.xaxis.tick_top()
        ax.tick_params(axis="x", colors=C_TXT, labelsize=10)
        ax.tick_params(axis="y", colors=C_TXT, labelsize=10)
        self.fig_sec.tight_layout()
        self.cv_sec.draw()


if __name__ == "__main__":
    App().mainloop()
