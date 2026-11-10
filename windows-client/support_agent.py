"""Support-Agent Windows-client.

Tray-applicatie met een globale sneltoets (standaard Ctrl+Shift+T): de
gelecteerde tekst wordt naar de Support-Agent webapp gestuurd (skill +
doeltaal), het resultaat verschijnt in een pop-up en staat direct op het
klembord.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

import pyperclip
import requests

APP_NAME = "SupportAgent"
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "support-agent.log"

LANGUAGES = {"nl": "Nederlands", "en": "English", "de": "Deutsch"}

DEFAULT_CONFIG = {
    "server_url": "https://app.jouwdomein.nl",
    "api_key": "APP_API_KEY-uit-jouw-.env",
    "skill": "support-communication",
    "target_language": "auto",
    "last_used_language": "en",
    "extra": "",
    "hotkey": "ctrl+shift+t",
}

log = logging.getLogger("support-agent-client")
EVENT_QUEUE: queue.Queue = queue.Queue()

_WORD_RE = re.compile(r"[A-Za-zäöüÄÖÜß]+")
_DUTCH = {
    "de", "het", "een", "en", "van", "te", "dat", "die", "dit", "niet", "ik", "jij", "je",
    "wij", "zijn", "is", "was", "waren", "met", "voor", "op", "aan", "in", "om", "ook",
    "als", "nog", "wel", "hoe", "wat", "wie", "waar", "naar", "bij", "uit", "door", "over",
    "huis", "liefde", "goed", "slecht", "auto", "heb", "ben", "wil", "kan", "zal",
}
_GERMAN = {
    "der", "die", "das", "und", "ist", "nicht", "ich", "du", "wir", "sie", "mit", "für",
    "auf", "ein", "eine", "zu", "von", "den", "dem", "des", "sich", "auch", "wie", "was",
    "aber", "oder", "wenn", "noch", "im", "am", "zum", "zur",
    "meinem", "meine", "mein", "liebe", "lieben", "frau", "mann", "bin", "habe", "haus",
    "auto", "gut", "schlecht",
}
_ENGLISH = {
    "the", "and", "is", "are", "was", "to", "of", "a", "an", "in", "that", "it", "for",
    "on", "with", "as", "i", "you", "we", "they", "not", "be", "this", "have", "from",
    "or", "but", "if", "so",
}


def setup_logging() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        log.warning("Config aangemaakt op %s - vul server_url en api_key in", CONFIG_PATH)
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key, value in DEFAULT_CONFIG.items():
        cfg.setdefault(key, value)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def detect_language(text: str) -> str:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    scores = {"nl": 0, "de": 0, "en": 0}
    for word in words:
        if word in _DUTCH:
            scores["nl"] += 1
        if word in _GERMAN:
            scores["de"] += 1
        if word in _ENGLISH:
            scores["en"] += 1
    if re.search(r"[ßäöüÄÖÜ]", text):
        scores["de"] += 3
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "en"


def resolve_target(cfg: dict, source: str) -> str:
    setting = str(cfg.get("target_language", "auto")).lower()
    if setting in LANGUAGES:
        return setting
    if source == "nl":
        last = str(cfg.get("last_used_language", "en")).lower()
        return last if last in LANGUAGES and last != "nl" else "en"
    return "nl"


def api_request(cfg: dict, method: str, path: str, payload=None, params=None) -> dict:
    url = cfg["server_url"].rstrip("/") + path
    resp = requests.request(
        method,
        url,
        json=payload,
        params=params,
        headers={"X-API-Key": cfg["api_key"]},
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Server reageerde met {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def fetch_skill_names(cfg: dict) -> list:
    try:
        skills = api_request(cfg, "GET", "/api/skills").get("skills", [])
        names = [s["name"] for s in skills]
        return names or [cfg.get("skill", "support-communication")]
    except Exception as exc:
        log.warning("Kan skills niet ophalen van server: %s", exc)
        return [cfg.get("skill", "support-communication")]


def process_text(cfg: dict, text: str, skill=None, target=None, extra=None) -> dict:
    source = detect_language(text)
    target = (target or resolve_target(cfg, source)).lower()
    payload = {
        "skill": skill or cfg.get("skill", "support-communication"),
        "text": text,
        "target_language": target,
        "source_language": source,
        "extra": extra if extra is not None else cfg.get("extra", ""),
    }
    data = api_request(cfg, "POST", "/api/process", payload)
    data["source_language"] = source
    if source == "nl" and target != "nl":
        cfg["last_used_language"] = target
        save_config(cfg)
    log.info(
        "process ok: skill=%s %s->%s chars=%d duration_ms=%s",
        payload["skill"], source, target, len(text), data.get("duration_ms"),
    )
    return data


def get_selection() -> str:
    keyboard.send("ctrl+c")
    time.sleep(0.4)
    return pyperclip.paste().strip()


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(30, 100, 220, 255))
    draw.text((24, 18), "S", fill=(255, 255, 255, 255))
    return img


class ResultPopup:
    def __init__(self, app: "TrayApp", text: str, result: dict) -> None:
        self.app = app
        self.cfg = app.cfg
        self.text = text
        self.win = tk.Toplevel(app.root)
        self.win.title("Support-Agent - resultaat")
        self.win.geometry("760x540")

        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Skill:").grid(row=0, column=0, sticky="w")
        self.skill_var = tk.StringVar(value=result.get("skill", self.cfg.get("skill")))
        self.skill_box = ttk.Combobox(
            top, textvariable=self.skill_var, values=fetch_skill_names(self.cfg),
            state="readonly", width=32,
        )
        self.skill_box.grid(row=0, column=1, sticky="w")
        ttk.Label(top, text="Gedetecteerde invoer:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.src_var = tk.StringVar()
        ttk.Label(top, textvariable=self.src_var).grid(row=0, column=3, sticky="w")
        ttk.Label(top, text="Doeltaal:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.lang_var = tk.StringVar()
        self.lang_box = ttk.Combobox(
            top, textvariable=self.lang_var, values=list(LANGUAGES.values()),
            state="readonly", width=32,
        )
        self.lang_box.grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(top, text="Extra info:").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(6, 0))
        self.extra_var = tk.StringVar(value=self.cfg.get("extra", ""))
        ttk.Entry(top, textvariable=self.extra_var, width=42).grid(row=1, column=3, sticky="w", pady=(6, 0))

        self.result_text = scrolledtext.ScrolledText(self.win, wrap="word", height=22)
        self.result_text.pack(fill="both", expand=True, padx=8, pady=6)

        buttons = ttk.Frame(self.win)
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        self.retry_btn = ttk.Button(buttons, text="Opnieuw (taal/extra wijzigen)", command=self.on_retry)
        self.retry_btn.pack(side="left")
        ttk.Button(buttons, text="Kopieer naar klembord", command=self.on_copy).pack(side="left", padx=6)
        ttk.Button(buttons, text="Sluiten", command=self.on_close).pack(side="right")

        self.show_result(result)
        app.popups[self.win.winfo_id()] = self
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        self.app.popups.pop(self.win.winfo_id(), None)
        self.win.destroy()

    def show_result(self, result: dict) -> None:
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", result.get("result", ""))
        source = result.get("source_language", "")
        self.src_var.set(LANGUAGES.get(source, source))
        self.lang_var.set(LANGUAGES.get(result.get("target_language", "nl"), "?"))
        self.retry_btn.config(state="normal")

    def on_copy(self) -> None:
        pyperclip.copy(self.result_text.get("1.0", "end-1c"))

    def on_retry(self) -> None:
        target = next((code for code, name in LANGUAGES.items() if name == self.lang_var.get()), "nl")
        skill = self.skill_var.get()
        extra = self.extra_var.get()
        self.retry_btn.config(state="disabled")

        def work() -> None:
            try:
                result = process_text(self.cfg, self.text, skill=skill, target=target, extra=extra)
                pyperclip.copy(result["result"])
                EVENT_QUEUE.put(("popup_update", self.win.winfo_id(), result))
            except Exception as exc:
                log.exception("Opnieuw mislukt")
                EVENT_QUEUE.put(("popup_error", self.win.winfo_id(), str(exc)))

        threading.Thread(target=work, daemon=True).start()


class TrayApp:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.withdraw()
        self.icon = None
        self.popups: dict = {}

    def run(self) -> None:
        keyboard.add_hotkey(self.cfg.get("hotkey", "ctrl+shift+t"), self.on_hotkey)
        threading.Thread(target=self._run_icon, daemon=True).start()
        self.root.after(100, self._poll)
        self.root.mainloop()

    def _poll(self) -> None:
        try:
            while True:
                kind, *rest = EVENT_QUEUE.get_nowait()
                self._handle(kind, *rest)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle(self, kind: str, *rest) -> None:
        if kind == "process":
            threading.Thread(target=self._do_process, args=(rest[0],), daemon=True).start()
        elif kind == "show_popup":
            ResultPopup(self, rest[0], rest[1])
        elif kind == "popup_update":
            popup = self.popups.get(rest[0])
            if popup:
                popup.show_result(rest[1])
        elif kind == "popup_error":
            popup = self.popups.get(rest[0])
            if popup:
                popup.retry_btn.config(state="normal")
            messagebox.showerror("Support-Agent", rest[1])
        elif kind == "show_text":
            self._show_text_window(rest[0], rest[1])
        elif kind == "error":
            log.error("%s", rest[0])
            messagebox.showerror("Support-Agent", rest[0])

    def on_hotkey(self) -> None:
        try:
            text = get_selection()
        except Exception as exc:
            EVENT_QUEUE.put(("error", f"Kan selectie niet lezen: {exc}"))
            return
        if not text:
            EVENT_QUEUE.put(("error", "Geen tekst geselecteerd"))
            return
        EVENT_QUEUE.put(("process", text))

    def _do_process(self, text: str) -> None:
        try:
            result = process_text(self.cfg, text)
        except Exception as exc:
            log.exception("Verwerking mislukt")
            EVENT_QUEUE.put(("error", str(exc)))
            return
        pyperclip.copy(result["result"])
        EVENT_QUEUE.put(("show_popup", text, result))

    def _run_icon(self) -> None:
        self.icon = Icon(APP_NAME, make_icon(), APP_NAME, self._build_menu())
        self.icon.run()

    def _refresh_menu(self) -> None:
        if self.icon:
            self.icon.menu = self._build_menu()
            self.icon.update_menu()

    def _set_skill(self, name: str) -> None:
        self.cfg["skill"] = name
        save_config(self.cfg)
        self._refresh_menu()

    def _set_target(self, lang: str) -> None:
        self.cfg["target_language"] = lang
        save_config(self.cfg)
        self._refresh_menu()

    def _edit_extra(self) -> None:
        def ask() -> None:
            value = simpledialog.askstring(
                "Extra info",
                "Standaard extra informatie voor de skill:",
                initialvalue=self.cfg.get("extra", ""),
                parent=self.root,
            )
            if value is not None:
                self.cfg["extra"] = value
                save_config(self.cfg)

        self.root.after(0, ask)

    def _show_server_log(self) -> None:
        def work() -> None:
            try:
                data = api_request(self.cfg, "GET", "/api/log", params={"limit": 200})
                lines = [f"{e['ts']}  {e['level']}: {e['msg']}" for e in data.get("entries", [])]
                EVENT_QUEUE.put(("show_text", "Serverlog (laatste 200 regels)", "\n".join(lines) or "(nog leeg)"))
            except Exception as exc:
                EVENT_QUEUE.put(("error", f"Kan serverlog niet ophalen: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _show_text_window(self, title: str, content: str) -> None:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("800x500")
        text = scrolledtext.ScrolledText(win, wrap="word")
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", content)

    def _quit(self) -> None:
        if self.icon:
            self.icon.stop()
        self.root.after(0, self.root.quit)

    def _build_menu(self) -> Menu:
        cfg = self.cfg
        skill_items = [
            MenuItem(
                name,
                lambda icon, item, s=name: self._set_skill(s),
                checked=lambda item, s=name: self.cfg.get("skill") == s,
                radio=True,
            )
            for name in fetch_skill_names(cfg)
        ]
        target = str(cfg.get("target_language", "auto")).lower()
        lang_items = [
            MenuItem(
                "Auto (op basis van invoer)",
                lambda icon, item: self._set_target("auto"),
                checked=lambda item: target == "auto",
                radio=True,
            )
        ] + [
            MenuItem(
                LANGUAGES[code],
                lambda icon, item, c=code: self._set_target(c),
                checked=lambda item, c=code: target == c,
                radio=True,
            )
            for code in ("nl", "en", "de")
        ]
        return Menu(
            MenuItem("Vertaal selectie", lambda icon, item: self.on_hotkey(), default=True),
            MenuItem("Skill", Menu(*skill_items)),
            MenuItem("Doeltaal", Menu(*lang_items)),
            MenuItem("Extra info default...", lambda icon, item: self._edit_extra()),
            MenuItem("Log tonen (lokaal)", lambda icon, item: os.startfile(LOG_PATH)),
            MenuItem("Serverlog tonen", lambda icon, item: self._show_server_log()),
            MenuItem("Instellingen openen", lambda icon, item: os.startfile(CONFIG_PATH)),
            MenuItem("Afsluiten", lambda icon, item: self._quit()),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Support-Agent client: Windows tray-app, of CLI-testmodus (--cli) die ook op Linux werkt"
    )
    parser.add_argument("--cli", metavar="TEKST", default=None,
                        help="CLI-modus: verwerk TEKST direct en print het resultaat ('-' = lees stdin)")
    parser.add_argument("--server", help="overschrijft server_url uit de config")
    parser.add_argument("--api-key", help="overschrijft api_key uit de config")
    parser.add_argument("--skill", help="overschrijft skill uit de config")
    parser.add_argument("--target", choices=["nl", "en", "de"], default=None,
                        help="doeltaal (standaard: auto op basis van gedetecteerde invoer)")
    parser.add_argument("--extra", default=None, help="extra informatie voor de skill")
    return parser.parse_args()


def run_cli(args: argparse.Namespace) -> None:
    setup_logging()
    cfg = load_config()
    if args.server:
        cfg["server_url"] = args.server
    if args.api_key:
        cfg["api_key"] = args.api_key
    if args.skill:
        cfg["skill"] = args.skill
    text = sys.stdin.read().strip() if args.cli == "-" else args.cli
    if not text:
        raise SystemExit("Geen tekst meegegeven: gebruik --cli TEKST of --cli - (stdin)")
    result = process_text(cfg, text, skill=args.skill, target=args.target, extra=args.extra)
    print(f"[gedetecteerde invoer: {result['source_language']} | doeltaal: {result['target_language']} | skill: {result['skill']}]",
          file=sys.stderr)
    print(result["result"])
    try:
        pyperclip.copy(result["result"])
        print("(resultaat staat ook op het klembord)", file=sys.stderr)
    except Exception:
        print("(geen klembord-backend gevonden; resultaat staat hierboven)", file=sys.stderr)


def main() -> None:
    args = parse_args()
    if args.cli is not None:
        run_cli(args)
        return
    global tk, ttk, scrolledtext, messagebox, simpledialog, keyboard, Icon, Menu, MenuItem, Image, ImageDraw
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, simpledialog, ttk
    import keyboard
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    setup_logging()
    log.info("Support-Agent client gestart")
    TrayApp().run()


if __name__ == "__main__":
    main()
