import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import csv
import os
import sys
import calendar
from collections import Counter
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

try:
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# W wersji .exe dane trzymamy obok pliku wykonywalnego, nie w katalogu rozpakowania
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_path(relative):
    """Zasoby wbudowane w exe (PyInstaller) lub pliki obok skryptu."""
    return os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), relative)
DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
CSV_HEADER = ["Data", "Godzina", "Skala Bristol", "Opis", "Tagi"]
TAGS = ["Ból brzucha", "Wzdęcia", "Krew", "Śluz", "Nudności", "Stres",
        "Alkohol", "Kawa", "Ostry posiłek", "Nabiał", "Fast food", "Leki",
        "Epizod brudzenia bielizny"]
TAG_SEPARATOR = ";"
BRISTOL_DESC = {
    1: "Oddzielne zbite grudki podobne do orzechów, trudne do wydalenia",
    2: "Stolec o wydłużonym kształcie, grudkowaty",
    3: "Stolec wydłużony, z pęknięciami na powierzchni",
    4: "Smukłe, wężowate kawałki stolca, gładkie i miękkie",
    5: "Miękkie drobiny z wyraźnymi krawędziami (łatwo wydalane)",
    6: "Stolec papkowaty, kłaczaste kawałki z postrzępionymi krawędziami",
    7: "Wodnisty, bez stałych elementów (ciecz)",
}


def parse_tags(row):
    return [t for t in row[4].split(TAG_SEPARATOR) if t]


def fmt_gap(hours):
    if hours < 48:
        return f"{hours:.0f} h"
    return f"{hours / 24:.1f} dni"


MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
WEEKDAYS_PL = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]


def heat_colors(avg):
    """Kolor heatmapy (jasny, ciemny) + kolor tekstu dla średniej skali dnia."""
    if avg <= 1 or avg > 6:
        return ("#c0392b", "#e74c3c"), ("white", "white")
    if avg < 2 or avg > 5:
        return ("#d35400", "#e67e22"), ("white", "white")
    if avg < 3 or avg > 4:
        return ("#b7950b", "#d4ac0d"), ("#202020", "#202020")
    return ("#1e7e34", "#2fa572"), ("white", "white")


def plural_wpisy(n):
    if n == 1:
        return "wpis"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "wpisy"
    return "wpisów"


def correlate_tags(samples):
    """samples: lista (skala, zbiór tagów). Zwraca statystyki korelacji posortowane wg |różnicy|."""
    stats = []
    for tag in TAGS:
        with_tag = [s for s, tags in samples if tag in tags]
        if not with_tag:
            continue
        without_tag = [s for s, tags in samples if tag not in tags]
        avg_with = sum(with_tag) / len(with_tag)
        avg_without = sum(without_tag) / len(without_tag) if without_tag else None
        delta = avg_with - avg_without if avg_without is not None else None
        stats.append((tag, len(with_tag), avg_with, avg_without, delta))
    stats.sort(key=lambda s: abs(s[4]) if s[4] is not None else -1, reverse=True)
    return stats


def detect_events(samples):
    """samples: posortowana lista (datetime, skala). Zwraca (dt, rodzaj, opis)."""
    events = []
    high = [dt for dt, s in samples if s >= 6]
    windows = []
    for i in range(len(high)):
        j = i
        while j + 1 < len(high) and (high[j + 1] - high[i]).total_seconds() <= 86400:
            j += 1
        if j - i + 1 >= 3:
            windows.append((i, j))
    merged = []
    for a, b in windows:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    for a, b in merged:
        events.append((high[a], "diarrhea",
                       f"Epizod biegunki: {b - a + 1} wpisy typu 6–7 w ciągu 24 h "
                       f"({high[a]:%d.%m %H:%M} – {high[b]:%d.%m %H:%M})"))
    for a, b in zip(samples, samples[1:]):
        gap_h = (b[0] - a[0]).total_seconds() / 3600
        if gap_h >= 72:
            events.append((a[0], "gap",
                           f"Przerwa {fmt_gap(gap_h)} bez wpisu ({a[0]:%d.%m} – {b[0]:%d.%m}) — możliwe zaparcie"))
    return events


def daypart_stats(samples):
    parts = [("Noc", range(0, 5)), ("Rano", range(5, 11)),
             ("Popołudnie", range(11, 17)), ("Wieczór", range(17, 24))]
    out = []
    for name, hours in parts:
        scales = [s for dt, s in samples if dt.hour in hours]
        out.append((name, len(scales), sum(scales) / len(scales) if scales else 0))
    return out


def register_pdf_font():
    """Rejestruje font TTF z polskimi znakami. Zwraca nazwę fontu lub None."""
    candidates = []
    if MATPLOTLIB_AVAILABLE:
        ttf_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        candidates.append((os.path.join(ttf_dir, "DejaVuSans.ttf"),
                           os.path.join(ttf_dir, "DejaVuSans-Bold.ttf")))
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates.append((os.path.join(windir, "Fonts", "arial.ttf"),
                       os.path.join(windir, "Fonts", "arialbd.ttf")))
    candidates.append(("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    for regular, bold in candidates:
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont("ReportFont", regular))
            pdfmetrics.registerFont(TTFont("ReportFont-Bold", bold if os.path.exists(bold) else regular))
            pdfmetrics.registerFontFamily("ReportFont", normal="ReportFont", bold="ReportFont-Bold")
            return "ReportFont"
    return None

class BMReporter(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BM Reporter - Monitorowanie Zdrowia")
        self.geometry("640x850")

        ico = resource_path(os.path.join("icons", "app.ico"))
        if os.path.exists(ico):
            self.iconbitmap(ico)

        self.filename = os.path.join(BASE_DIR, "history.csv")
        self.init_csv()
        self.edit_index = None

        self.tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tab_add = self.tabview.add("Dodaj Wpis")
        self.tab_history = self.tabview.add("Historia")
        self.tab_charts = self.tabview.add("Wykresy")
        self.tab_corr = self.tabview.add("Korelacje")
        self.tab_analysis = self.tabview.add("Analiza")
        self.tab_cal = self.tabview.add("Kalendarz")

        self.setup_add_tab()
        self.setup_history_tab()
        self.setup_charts_tab()
        self.setup_correlations_tab()
        self.setup_analysis_tab()
        self.setup_calendar_tab()

    # --- Dostęp do danych ---

    def init_csv(self):
        """Tworzy plik CSV z nagłówkami, jeśli nie istnieje lub jest pusty."""
        if not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0:
            with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(CSV_HEADER)

    def read_entries(self):
        """Wczytuje wszystkie wpisy z CSV. Odporny na pusty i zablokowany plik."""
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # nagłówek (None zamiast StopIteration dla pustego pliku)
                # stare wpisy mają 4 kolumny — dopełniamy pustą kolumną tagów
                return [(row + [""])[:5] for row in reader if len(row) >= 4]
        except OSError as e:
            messagebox.showerror("Błąd odczytu", f"Nie udało się odczytać pliku danych:\n{e}")
            return []

    def write_entries(self, entries):
        """Nadpisuje cały plik CSV (używane przy edycji i usuwaniu)."""
        try:
            with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER)
                writer.writerows(entries)
            return True
        except OSError as e:
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać danych:\n{e}")
            return False

    # --- Zakładka "Dodaj Wpis" ---

    def setup_add_tab(self):
        self.label_title = ctk.CTkLabel(self.tab_add, text="Nowy Wpis", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=15)

        self.date_var = ctk.StringVar(value=datetime.now().strftime(DATE_FMT))
        self.date_btn = ctk.CTkButton(self.tab_add, text="", width=300, command=self.open_date_picker)
        self.date_btn.pack(pady=5)
        self.date_var.trace_add("write", lambda *a: self.date_btn.configure(text=f"Data:  {self.date_var.get()}"))
        self.date_btn.configure(text=f"Data:  {self.date_var.get()}")

        self.time_var = ctk.StringVar(value=datetime.now().strftime(TIME_FMT))
        self.time_btn = ctk.CTkButton(self.tab_add, text="", width=300, command=self.open_time_picker)
        self.time_btn.pack(pady=5)
        self.time_var.trace_add("write", lambda *a: self.time_btn.configure(text=f"Godzina:  {self.time_var.get()}"))
        self.time_btn.configure(text=f"Godzina:  {self.time_var.get()}")

        self.label_scale = ctk.CTkLabel(self.tab_add, text="Skala Bristol (Konsystencja):")
        self.label_scale.pack(pady=(15, 0))

        self.scale_var = ctk.StringVar(value="4")
        scale_frame = ctk.CTkFrame(self.tab_add, fg_color="transparent")
        scale_frame.pack(pady=5)
        self.scale_buttons = {}
        for i in range(1, 8):
            img = ctk.CTkImage(Image.open(resource_path(os.path.join("icons", "bristol", f"type{i}.png"))),
                               size=(64, 44))
            btn = ctk.CTkButton(scale_frame, image=img, text=str(i), compound="top",
                                width=76, height=72, fg_color="transparent",
                                hover_color=("#e0e0e0", "#3a3a3a"),
                                font=ctk.CTkFont(size=12, weight="bold"),
                                command=lambda v=i: self.select_scale(v))
            btn.grid(row=0, column=i - 1, padx=2)
            self.scale_buttons[i] = btn

        self.label_hint = ctk.CTkLabel(self.tab_add, text="", font=ctk.CTkFont(size=10),
                                       wraplength=560, justify="center")
        self.label_hint.pack(pady=2)
        self.select_scale(4)

        self.label_tags = ctk.CTkLabel(self.tab_add, text="Tagi (objawy i czynniki):")
        self.label_tags.pack(pady=(15, 0))

        self.tag_vars = {}
        tags_frame = ctk.CTkFrame(self.tab_add, fg_color="transparent")
        tags_frame.pack(pady=5)
        for i, tag in enumerate(TAGS):
            var = ctk.BooleanVar(value=False)
            self.tag_vars[tag] = var
            ctk.CTkCheckBox(tags_frame, text=tag, variable=var,
                            font=ctk.CTkFont(size=12), checkbox_width=18, checkbox_height=18
                            ).grid(row=i // 3, column=i % 3, sticky="w", padx=8, pady=2)

        self.label_desc = ctk.CTkLabel(self.tab_add, text="Opis / Dodatkowe uwagi:")
        self.label_desc.pack(pady=(15, 0))

        self.desc_text = ctk.CTkTextbox(self.tab_add, width=300, height=110)
        self.desc_text.pack(pady=5)

        self.btn_save = ctk.CTkButton(self.tab_add, text="Zapisz Wpis", command=self.save_entry, font=ctk.CTkFont(weight="bold"))
        self.btn_save.pack(pady=(30, 5))

        self.btn_cancel_edit = ctk.CTkButton(self.tab_add, text="Anuluj edycję", command=self.cancel_edit, fg_color="gray50", hover_color="gray40")

    def select_scale(self, value):
        value = int(value)
        self.scale_var.set(str(value))
        for i, btn in self.scale_buttons.items():
            if i == value:
                btn.configure(fg_color=("#cfe3f5", "#2a4a6b"), border_width=2, border_color="#3b8ed0")
            else:
                btn.configure(fg_color="transparent", border_width=0)
        self.label_hint.configure(text=f"Typ {value}: {BRISTOL_DESC[value]}")

    def open_date_picker(self, target_var=None):
        var = target_var if target_var is not None else self.date_var
        top = ctk.CTkToplevel(self)
        top.title("Wybierz datę")
        top.geometry("360x420")
        top.transient(self)
        top.grab_set()

        try:
            cur = datetime.strptime(var.get(), DATE_FMT).date()
        except ValueError:
            cur = datetime.now().date()
        state = {"y": cur.year, "m": cur.month}

        header = ctk.CTkFrame(top, fg_color="transparent")
        header.pack(pady=(10, 0))
        month_lbl = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14, weight="bold"), width=160)
        grid = ctk.CTkFrame(top, fg_color="transparent")
        grid.pack(pady=8)

        def pick(d):
            var.set(f"{state['y']}-{state['m']:02d}-{d:02d}")
            top.destroy()

        def rebuild():
            for w in grid.winfo_children():
                w.destroy()
            month_lbl.configure(text=f"{MONTHS_PL[state['m'] - 1]} {state['y']}")
            for col, name in enumerate(WEEKDAYS_PL):
                ctk.CTkLabel(grid, text=name, font=ctk.CTkFont(size=10, weight="bold")
                             ).grid(row=0, column=col, padx=2, pady=2)
            first, n_days = calendar.monthrange(state["y"], state["m"])
            today = datetime.now().date()
            for day in range(1, n_days + 1):
                r, c = divmod(first + day - 1, 7)
                selected = (state["y"], state["m"], day) == (cur.year, cur.month, cur.day)
                is_today = (state["y"], state["m"], day) == (today.year, today.month, today.day)
                ctk.CTkButton(grid, text=str(day), width=42, height=34,
                              fg_color="#3b8ed0" if selected else "transparent",
                              hover_color=("#e0e0e0", "#3a3a3a"),
                              border_width=2 if is_today else 0, border_color="#3b8ed0",
                              font=ctk.CTkFont(size=11),
                              command=lambda d=day: pick(d)).grid(row=r + 1, column=c, padx=2, pady=2)

        def shift(delta):
            m = state["m"] + delta
            if m < 1:
                m, state["y"] = 12, state["y"] - 1
            elif m > 12:
                m, state["y"] = 1, state["y"] + 1
            state["m"] = m
            rebuild()

        ctk.CTkButton(header, text="<", width=36, command=lambda: shift(-1)).pack(side="left", padx=4)
        month_lbl.pack(side="left")
        ctk.CTkButton(header, text=">", width=36, command=lambda: shift(1)).pack(side="left", padx=4)

        def pick_today():
            t = datetime.now().date()
            var.set(t.strftime(DATE_FMT))
            top.destroy()

        ctk.CTkButton(top, text="Dziś", width=80, command=pick_today).pack(pady=(0, 10))
        rebuild()

    def open_time_picker(self):
        top = ctk.CTkToplevel(self)
        top.title("Wybierz godzinę")
        top.geometry("360x400")
        top.transient(self)
        top.grab_set()

        try:
            cur = datetime.strptime(self.time_var.get(), TIME_FMT)
            state = {"h": cur.hour, "m": cur.minute}
        except ValueError:
            now = datetime.now()
            state = {"h": now.hour, "m": now.minute}

        clock = ctk.CTkFrame(top, fg_color=("#f0f0f0", "#2b2b2b"))
        clock.pack(pady=(16, 8), padx=20, fill="x")
        big = ctk.CTkFont(family="Consolas", size=44, weight="bold")

        def step(key, delta):
            state[key] = (state[key] + delta) % (24 if key == "h" else 60)
            refresh()

        hour_box = ctk.CTkFrame(clock, fg_color="transparent")
        hour_box.pack(side="left", expand=True, pady=8)
        ctk.CTkButton(hour_box, text="▲", width=70, height=26,
                      command=lambda: step("h", 1)).pack()
        hour_lbl = ctk.CTkLabel(hour_box, text="", font=big)
        hour_lbl.pack(pady=2)
        ctk.CTkButton(hour_box, text="▼", width=70, height=26,
                      command=lambda: step("h", -1)).pack()

        ctk.CTkLabel(clock, text=":", font=big).pack(side="left")

        minute_box = ctk.CTkFrame(clock, fg_color="transparent")
        minute_box.pack(side="left", expand=True, pady=8)
        ctk.CTkButton(minute_box, text="▲", width=70, height=26,
                      command=lambda: step("m", 1)).pack()
        min_lbl = ctk.CTkLabel(minute_box, text="", font=big)
        min_lbl.pack(pady=2)
        ctk.CTkButton(minute_box, text="▼", width=70, height=26,
                      command=lambda: step("m", -1)).pack()

        ctk.CTkLabel(top, text="Godzina (0–23):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=30)
        hour_slider = ctk.CTkSlider(top, from_=0, to=23, number_of_steps=23,
                                    command=lambda v: (state.update(h=int(round(v))), refresh()))
        hour_slider.pack(fill="x", padx=30, pady=(0, 6))
        ctk.CTkLabel(top, text="Minuty (0–59):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=30)
        minute_slider = ctk.CTkSlider(top, from_=0, to=59, number_of_steps=59,
                                      command=lambda v: (state.update(m=int(round(v))), refresh()))
        minute_slider.pack(fill="x", padx=30, pady=(0, 6))

        def refresh():
            hour_lbl.configure(text=f"{state['h']:02d}")
            min_lbl.configure(text=f"{state['m']:02d}")
            hour_slider.set(state["h"])
            minute_slider.set(state["m"])

        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(pady=(4, 12))

        def set_now():
            now = datetime.now()
            self.time_var.set(now.strftime(TIME_FMT))
            top.destroy()

        def ok():
            self.time_var.set(f"{state['h']:02d}:{state['m']:02d}")
            top.destroy()

        ctk.CTkButton(buttons, text="Teraz", width=90, fg_color="gray50", hover_color="gray40",
                      command=set_now).pack(side="left", padx=5)
        ctk.CTkButton(buttons, text="OK", width=90, command=ok).pack(side="left", padx=5)
        refresh()

    def on_tab_change(self, tab_name=None):
        # CTkTabview 6.x wywoluje command bez argumentow przy kliknieciu zakladki
        if tab_name is None:
            tab_name = self.tabview.get()
        if tab_name == "Dodaj Wpis" and self.edit_index is None:
            self.date_var.set(datetime.now().strftime(DATE_FMT))
            self.time_var.set(datetime.now().strftime(TIME_FMT))
        elif tab_name == "Wykresy":
            self.refresh_charts()
        elif tab_name == "Korelacje":
            self.refresh_correlations()
        elif tab_name == "Analiza":
            self.refresh_analysis()
        elif tab_name == "Kalendarz":
            self.refresh_calendar()

    def setup_history_tab(self):
        self.stats_frame = ctk.CTkFrame(self.tab_history, fg_color=("#f0f0f0", "#2b2b2b"))
        self.stats_frame.pack(pady=(10, 5), padx=10, fill="x")

        self.range_var = ctk.StringVar(value="7 dni")
        self.range_menu = ctk.CTkOptionMenu(
            self.stats_frame,
            values=["7 dni", "30 dni"],
            variable=self.range_var,
            command=lambda _: self.update_statistics(),
            width=100
        )
        self.range_menu.grid(row=0, column=2, padx=10, pady=(5, 10))

        self.stats_label = ctk.CTkLabel(self.stats_frame, text="Podsumowanie", font=ctk.CTkFont(weight="bold"))
        self.stats_label.grid(row=0, column=0, columnspan=2, padx=10)

        # Wartości statystyk
        # Wartości statystyk (Poprawiony układ: Etykieta -> Wartość)
        ctk.CTkLabel(self.stats_frame, text="Średnia Skala:").grid(row=1, column=0, padx=(10, 5))
        self.avg_score_var = ctk.StringVar(value="---")
        self.avg_score_lbl = ctk.CTkLabel(self.stats_frame, textvariable=self.avg_score_var, font=ctk.CTkFont(size=14))
        self.avg_score_lbl.grid(row=1, column=1, padx=(0, 30))

        ctk.CTkLabel(self.stats_frame, text="Najczęstsza:").grid(row=1, column=2, padx=(10, 5))
        self.freq_score_var = ctk.StringVar(value="---")
        self.freq_score_lbl = ctk.CTkLabel(self.stats_frame, textvariable=self.freq_score_var, font=ctk.CTkFont(size=14))
        self.freq_score_lbl.grid(row=1, column=3, padx=(0, 30))

        ctk.CTkLabel(self.stats_frame, text="Liczba wpisów:").grid(row=1, column=4, padx=(10, 5))
        self.count_var = ctk.StringVar(value="0")
        self.count_lbl = ctk.CTkLabel(self.stats_frame, textvariable=self.count_var, font=ctk.CTkFont(size=14))
        self.count_lbl.grid(row=1, column=5, padx=(0, 10))

        ctk.CTkLabel(self.stats_frame, text="% optymalnych (3–4):").grid(row=2, column=0, padx=(10, 5), pady=(0, 8))
        self.optimal_var = ctk.StringVar(value="---")
        self.optimal_lbl = ctk.CTkLabel(self.stats_frame, textvariable=self.optimal_var, font=ctk.CTkFont(size=14))
        self.optimal_lbl.grid(row=2, column=1, padx=(0, 30), pady=(0, 8))

        ctk.CTkLabel(self.stats_frame, text="vs poprzedni okres:").grid(row=2, column=2, padx=(10, 5), pady=(0, 8))
        self.trend_var = ctk.StringVar(value="---")
        self.trend_lbl = ctk.CTkLabel(self.stats_frame, textvariable=self.trend_var, font=ctk.CTkFont(size=14, weight="bold"))
        self.trend_lbl.grid(row=2, column=3, columnspan=3, padx=(0, 10), pady=(0, 8), sticky="w")

        self.filter_label = ctk.CTkLabel(self.tab_history, text="Filtruj listę poniżej:")
        self.filter_label.pack(pady=(10, 0))

        filters_frame = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        filters_frame.pack(pady=5)

        ctk.CTkLabel(filters_frame, text="Skala:").pack(side="left", padx=(0, 5))
        self.filter_var = ctk.StringVar(value="Wszystkie")
        filter_options = ["Wszystkie"] + [str(i) for i in range(1, 8)]
        self.filter_menu = ctk.CTkOptionMenu(
            filters_frame,
            values=filter_options,
            variable=self.filter_var,
            command=lambda _: self.load_history(),
            width=110
        )
        self.filter_menu.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(filters_frame, text="Tag:").pack(side="left", padx=(0, 5))
        self.tag_filter_var = ctk.StringVar(value="Wszystkie")
        self.tag_filter_menu = ctk.CTkOptionMenu(
            filters_frame,
            values=["Wszystkie"] + TAGS,
            variable=self.tag_filter_var,
            command=lambda _: self.load_history(),
            width=140
        )
        self.tag_filter_menu.pack(side="left")

        self.history_scroll = ctk.CTkScrollableFrame(self.tab_history, width=520, height=380)
        self.history_scroll.pack(pady=10, padx=10, fill="both", expand=True)

        self.btn_frame = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        self.btn_refresh = ctk.CTkButton(self.btn_frame, text="Odśwież Historię", command=self.load_history)
        self.btn_refresh.grid(row=0, column=0, padx=5)

        self.btn_export = ctk.CTkButton(
            self.btn_frame,
            text="Eksportuj do PDF",
            command=self.open_export_dialog,
            fg_color="#2c3e50",
            hover_color="#34495e"
        )
        self.btn_export.grid(row=0, column=1, padx=5)

        self.load_history()

    def save_entry(self):
        date = self.date_var.get().strip()
        time = self.time_var.get().strip()
        scale = self.scale_var.get()
        description = self.desc_text.get("1.0", "end-1c")

        try:
            date = datetime.strptime(date, DATE_FMT).strftime(DATE_FMT)
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa data. Wymagany format: RRRR-MM-DD (np. 2026-11-11).")
            return
        try:
            time = datetime.strptime(time, TIME_FMT).strftime(TIME_FMT)
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa godzina. Wymagany format: HH:MM (np. 08:30).")
            return

        tags = TAG_SEPARATOR.join(t for t in TAGS if self.tag_vars[t].get())
        row = [date, time, scale, description, tags]

        if self.edit_index is not None:
            entries = self.read_entries()
            if not (0 <= self.edit_index < len(entries)):
                messagebox.showerror("Błąd", "Edytowany wpis nie istnieje (mógł zostać usunięty).")
                self.cancel_edit()
                return
            entries[self.edit_index] = row
            if not self.write_entries(entries):
                return
            message = "Wpis został zaktualizowany!"
        else:
            try:
                with open(self.filename, mode='a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(row)
            except OSError as e:
                messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać danych: {e}")
                return
            message = "Wpis został zapisany!"

        messagebox.showinfo("Sukces", message)
        self.cancel_edit()
        self.desc_text.delete("1.0", "end")
        self.date_var.set(datetime.now().strftime(DATE_FMT))
        self.time_var.set(datetime.now().strftime(TIME_FMT))
        self.load_history()
        self.refresh_charts()
        self.refresh_correlations()
        self.refresh_analysis()
        self.refresh_calendar()

    def edit_entry(self, index):
        entries = self.read_entries()
        if not (0 <= index < len(entries)):
            messagebox.showerror("Błąd", "Wpis nie istnieje.")
            return
        row = entries[index]
        self.edit_index = index
        self.date_var.set(row[0])
        self.time_var.set(row[1])
        self.select_scale(row[2])
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", row[3])
        selected = parse_tags(row)
        for tag, var in self.tag_vars.items():
            var.set(tag in selected)
        self.label_title.configure(text="Edytuj Wpis")
        self.btn_save.configure(text="Zapisz zmiany")
        self.btn_cancel_edit.pack(pady=5)
        self.tabview.set("Dodaj Wpis")

    def cancel_edit(self):
        self.edit_index = None
        for var in self.tag_vars.values():
            var.set(False)
        self.label_title.configure(text="Nowy Wpis")
        self.btn_save.configure(text="Zapisz Wpis")
        self.btn_cancel_edit.pack_forget()

    def delete_entry(self, index):
        entries = self.read_entries()
        if not (0 <= index < len(entries)):
            messagebox.showerror("Błąd", "Wpis nie istnieje.")
            return
        row = entries[index]
        if not messagebox.askyesno("Usuń wpis", f"Czy na pewno usunąć wpis z {row[0]} {row[1]}?"):
            return
        del entries[index]
        if self.write_entries(entries):
            if self.edit_index == index:
                self.cancel_edit()
            elif self.edit_index is not None and index < self.edit_index:
                self.edit_index -= 1
            self.load_history()
            self.refresh_charts()
            self.refresh_correlations()
            self.refresh_analysis()
            self.refresh_calendar()

    def load_history(self):
        """Odczytuje dane z CSV, filtruje je i wyświetla jako listę wierszy."""
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        filter_val = self.filter_var.get()
        tag_filter = self.tag_filter_var.get()
        entries = [(i, row) for i, row in enumerate(self.read_entries())
                   if (filter_val == "Wszystkie" or row[2] == filter_val)
                   and (tag_filter == "Wszystkie" or tag_filter in parse_tags(row))]
        entries.sort(key=lambda x: (x[1][0], x[1][1]), reverse=True)

        if not entries:
            ctk.CTkLabel(self.history_scroll, text="Brak wpisów spełniających kryteria.").pack(pady=20)
        else:
            for index, row in entries:
                self.build_history_row(index, row)

        self.update_statistics()

    def build_history_row(self, index, row):
        frame = ctk.CTkFrame(self.history_scroll)
        frame.pack(fill="x", padx=5, pady=3)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(5, 0))

        ctk.CTkLabel(top, text=f"[{row[0]} {row[1]}]  Skala: {row[2]}",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        ctk.CTkButton(top, text="Usuń", width=50, fg_color="#8b3a3a", hover_color="#a04545",
                      command=lambda i=index: self.delete_entry(i)).pack(side="right", padx=(5, 0))
        ctk.CTkButton(top, text="Edytuj", width=50,
                      command=lambda i=index: self.edit_entry(i)).pack(side="right")

        tags = parse_tags(row)
        if tags:
            ctk.CTkLabel(frame, text="Tagi: " + ", ".join(tags), justify="left", wraplength=420,
                         font=ctk.CTkFont(size=11, slant="italic"),
                         text_color=("#1a6ea8", "#6db3e8")).pack(anchor="w", padx=8, pady=(2, 0))

        if row[3]:
            ctk.CTkLabel(frame, text=row[3], justify="left", wraplength=420,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=8, pady=(2, 6))
        else:
            ctk.CTkFrame(frame, height=4, fg_color="transparent").pack()

    def update_statistics(self):
        """Oblicza statystyki dla wybranego zakresu czasowego i aktualizuje UI."""
        days = 7 if self.range_var.get() == "7 dni" else 30
        cutoff_date = datetime.now().date() - timedelta(days=days - 1)
        prev_cutoff = cutoff_date - timedelta(days=days)
        recent_scales = []
        prev_scales = []

        for row in self.read_entries():
            try:
                entry_date = datetime.strptime(row[0], DATE_FMT).date()
                if entry_date >= cutoff_date:
                    recent_scales.append(int(row[2]))
                elif entry_date >= prev_cutoff:
                    prev_scales.append(int(row[2]))
            except ValueError:
                continue

        if recent_scales:
            avg = sum(recent_scales) / len(recent_scales)
            self.avg_score_var.set(f"{avg:.1f}")
            self.count_var.set(str(len(recent_scales)))
            self.freq_score_var.set(str(Counter(recent_scales).most_common(1)[0][0]))
            optimal = 100 * sum(1 for s in recent_scales if s in (3, 4)) / len(recent_scales)
            self.optimal_var.set(f"{optimal:.0f}%")
            if prev_scales:
                prev_optimal = 100 * sum(1 for s in prev_scales if s in (3, 4)) / len(prev_scales)
                delta = optimal - prev_optimal
                self.trend_var.set(f"{delta:+.0f} pp")
                if delta > 0:
                    self.trend_lbl.configure(text_color=("#1e7e34", "#2fa572"))
                elif delta < 0:
                    self.trend_lbl.configure(text_color=("#c0392b", "#e74c3c"))
                else:
                    self.trend_lbl.configure(text_color=("gray40", "gray60"))
            else:
                self.trend_var.set("brak danych")
                self.trend_lbl.configure(text_color=("gray40", "gray60"))
        else:
            self.avg_score_var.set("---")
            self.count_var.set("0")
            self.freq_score_var.set("---")
            self.optimal_var.set("---")
            self.trend_var.set("---")
            self.trend_lbl.configure(text_color=("gray40", "gray60"))

    # --- Zakładka "Wykresy" ---

    def setup_charts_tab(self):
        if not MATPLOTLIB_AVAILABLE:
            ctk.CTkLabel(self.tab_charts,
                         text="Biblioteka 'matplotlib' nie jest zainstalowana.\nUruchom w terminalu: pip install matplotlib",
                         font=ctk.CTkFont(size=14)).pack(pady=40)
            return

        controls = ctk.CTkFrame(self.tab_charts, fg_color="transparent")
        controls.pack(pady=(10, 0))

        ctk.CTkLabel(controls, text="Zakres:").pack(side="left", padx=(0, 5))
        self.chart_range_var = ctk.StringVar(value="30 dni")
        ctk.CTkOptionMenu(controls, values=["7 dni", "30 dni"], variable=self.chart_range_var,
                          command=lambda _: self.refresh_charts(), width=100).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Odśwież", width=80, command=self.refresh_charts).pack(side="left", padx=5)

        self.fig = Figure(figsize=(5.6, 6.2), dpi=100, constrained_layout=True)
        self.ax_daily = self.fig.add_subplot(2, 1, 1)
        self.ax_dist = self.fig.add_subplot(2, 1, 2)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_charts)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_charts()

    def refresh_charts(self):
        if not MATPLOTLIB_AVAILABLE or not hasattr(self, "canvas"):
            return

        days = 7 if self.chart_range_var.get() == "7 dni" else 30
        today = datetime.now().date()
        start = today - timedelta(days=days - 1)

        daily_counts = Counter()
        scale_counts = Counter()
        for row in self.read_entries():
            try:
                entry_date = datetime.strptime(row[0], DATE_FMT).date()
                scale = int(row[2])
            except ValueError:
                continue
            if start <= entry_date <= today:
                daily_counts[entry_date] += 1
                scale_counts[scale] += 1

        dates = [start + timedelta(days=i) for i in range(days)]
        counts = [daily_counts.get(d, 0) for d in dates]

        self.ax_daily.clear()
        self.ax_daily.bar([d.strftime("%d.%m") for d in dates], counts, color="#3b8ed0")
        self.ax_daily.set_title(f"Liczba wpisów dziennie (ostatnie {days} dni)")
        self.ax_daily.set_ylabel("Wpisy")
        self.ax_daily.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        self.ax_daily.tick_params(axis="x", rotation=90, labelsize=7)

        self.ax_dist.clear()
        self.ax_dist.bar(range(1, 8), [scale_counts.get(i, 0) for i in range(1, 8)], color="#2fa572")
        self.ax_dist.set_title("Rozkład skali Bristol")
        self.ax_dist.set_xlabel("Skala Bristol")
        self.ax_dist.set_ylabel("Wpisy")
        self.ax_dist.set_xticks(range(1, 8))
        self.ax_dist.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

        self.canvas.draw()

    # --- Zakładka "Korelacje" ---

    def setup_correlations_tab(self):
        controls = ctk.CTkFrame(self.tab_corr, fg_color="transparent")
        controls.pack(pady=(10, 0))

        ctk.CTkLabel(controls, text="Zakres:").pack(side="left", padx=(0, 5))
        self.corr_range_var = ctk.StringVar(value="Wszystkie")
        ctk.CTkOptionMenu(controls, values=["7 dni", "30 dni", "Wszystkie"], variable=self.corr_range_var,
                          command=lambda _: self.refresh_correlations(), width=110).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Odśwież", width=80, command=self.refresh_correlations).pack(side="left", padx=5)

        ctk.CTkLabel(self.tab_corr, justify="left", wraplength=540, font=ctk.CTkFont(size=11),
                     text=("Różnica = średnia skala Bristol z tagiem minus średnia bez tagu.\n"
                           "Dodatnia: luźniejszy stolec przy tym tagu, ujemna: twardszy.\n"
                           "* mniej niż 3 wpisy — wynik mało wiarygodny. Korelacja to nie przyczyna.")
                     ).pack(pady=(8, 0), padx=15)

        self.corr_scroll = ctk.CTkScrollableFrame(self.tab_corr, width=540, height=480)
        self.corr_scroll.pack(pady=10, padx=10, fill="both", expand=True)
        self.refresh_correlations()

    def refresh_correlations(self):
        if not hasattr(self, "corr_scroll"):
            return
        for widget in self.corr_scroll.winfo_children():
            widget.destroy()

        range_val = self.corr_range_var.get()
        cutoff = None
        if range_val != "Wszystkie":
            days = 7 if range_val == "7 dni" else 30
            cutoff = datetime.now().date() - timedelta(days=days - 1)

        samples = []
        for row in self.read_entries():
            try:
                entry_date = datetime.strptime(row[0], DATE_FMT).date()
                scale = int(row[2])
            except ValueError:
                continue
            if cutoff is None or entry_date >= cutoff:
                samples.append((scale, set(parse_tags(row))))

        stats = correlate_tags(samples)

        if not stats:
            ctk.CTkLabel(self.corr_scroll,
                         text="Brak wpisów z tagami w wybranym zakresie.\nDodaj tagi przy zapisywaniu wpisu, aby zobaczyć korelacje."
                         ).pack(pady=30)
            return

        headers = ["Tag", "Wpisy", "Śr. z tagiem", "Śr. bez tagu", "Różnica"]
        for col, text in enumerate(headers):
            ctk.CTkLabel(self.corr_scroll, text=text, font=ctk.CTkFont(size=12, weight="bold")
                         ).grid(row=0, column=col, padx=8, pady=(5, 8), sticky="w")

        for r, (tag, count, avg_with, avg_without, delta) in enumerate(stats, start=1):
            ctk.CTkLabel(self.corr_scroll, text=tag, font=ctk.CTkFont(size=12)).grid(row=r, column=0, padx=8, pady=3, sticky="w")
            count_text = str(count) + ("*" if count < 3 else "")
            ctk.CTkLabel(self.corr_scroll, text=count_text).grid(row=r, column=1, padx=8, pady=3, sticky="w")
            ctk.CTkLabel(self.corr_scroll, text=f"{avg_with:.1f}").grid(row=r, column=2, padx=8, pady=3, sticky="w")
            ctk.CTkLabel(self.corr_scroll, text=f"{avg_without:.1f}" if avg_without is not None else "---"
                         ).grid(row=r, column=3, padx=8, pady=3, sticky="w")

            if delta is None:
                delta_text, delta_color = "---", ("gray40", "gray60")
            else:
                delta_text = f"{delta:+.1f}"
                if delta >= 0.5:
                    delta_color = ("#c0392b", "#e74c3c")
                elif delta <= -0.5:
                    delta_color = ("#1a6ea8", "#5dade2")
                else:
                    delta_color = ("gray40", "gray60")
            ctk.CTkLabel(self.corr_scroll, text=delta_text, text_color=delta_color,
                         font=ctk.CTkFont(size=12, weight="bold")).grid(row=r, column=4, padx=8, pady=3, sticky="w")

    # --- Zakładka "Analiza" ---

    def setup_analysis_tab(self):
        controls = ctk.CTkFrame(self.tab_analysis, fg_color="transparent")
        controls.pack(pady=(10, 0))

        ctk.CTkLabel(controls, text="Zakres:").pack(side="left", padx=(0, 5))
        self.analysis_range_var = ctk.StringVar(value="30 dni")
        ctk.CTkOptionMenu(controls, values=["7 dni", "30 dni", "Wszystkie"], variable=self.analysis_range_var,
                          command=lambda _: self.refresh_analysis(), width=110).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Odśwież", width=80, command=self.refresh_analysis).pack(side="left", padx=5)

        self.reg_frame = ctk.CTkFrame(self.tab_analysis, fg_color=("#f0f0f0", "#2b2b2b"))
        self.reg_frame.pack(pady=(8, 0), padx=10, fill="x")
        self.reg_vars = {}
        self.reg_lbls = {}
        for col, (key, label) in enumerate([("median", "Mediana odstępów:"),
                                            ("maxgap", "Najdłuższa przerwa:"),
                                            ("since", "Od ostatniego wpisu:")]):
            ctk.CTkLabel(self.reg_frame, text=label, font=ctk.CTkFont(size=11)
                         ).grid(row=0, column=col * 2, padx=(10, 5), pady=6, sticky="w")
            var = ctk.StringVar(value="---")
            self.reg_vars[key] = var
            lbl = ctk.CTkLabel(self.reg_frame, textvariable=var, font=ctk.CTkFont(size=12, weight="bold"))
            lbl.grid(row=0, column=col * 2 + 1, padx=(0, 15), pady=6, sticky="w")
            self.reg_lbls[key] = lbl

        if MATPLOTLIB_AVAILABLE:
            self.analysis_fig = Figure(figsize=(5.6, 2.3), dpi=100, constrained_layout=True)
            self.ax_hours = self.analysis_fig.add_subplot(1, 2, 1)
            self.ax_daypart = self.analysis_fig.add_subplot(1, 2, 2)
            self.analysis_canvas = FigureCanvasTkAgg(self.analysis_fig, master=self.tab_analysis)
            self.analysis_canvas.get_tk_widget().pack(fill="x", padx=10, pady=(8, 0))
        else:
            self.daypart_frame = ctk.CTkFrame(self.tab_analysis, fg_color="transparent")
            self.daypart_frame.pack(fill="x", padx=15, pady=(8, 0))

        ctk.CTkLabel(self.tab_analysis, text="Wykryte epizody:", font=ctk.CTkFont(weight="bold")
                     ).pack(anchor="w", padx=15, pady=(8, 0))
        self.episodes_scroll = ctk.CTkScrollableFrame(self.tab_analysis, width=540, height=180)
        self.episodes_scroll.pack(pady=(4, 10), padx=10, fill="both", expand=True)
        self.refresh_analysis()

    def refresh_analysis(self):
        if not hasattr(self, "episodes_scroll"):
            return

        range_val = self.analysis_range_var.get()
        cutoff = None
        if range_val != "Wszystkie":
            days = 7 if range_val == "7 dni" else 30
            cutoff = datetime.now().date() - timedelta(days=days - 1)

        samples = []
        last_dt = None
        for row in self.read_entries():
            try:
                dt = datetime.strptime(row[0] + " " + row[1], DATE_FMT + " " + TIME_FMT)
                scale = int(row[2])
            except ValueError:
                continue
            if last_dt is None or dt > last_dt:
                last_dt = dt
            if cutoff is None or dt.date() >= cutoff:
                samples.append((dt, scale))
        samples.sort(key=lambda x: x[0])

        gaps = [(b[0] - a[0]).total_seconds() / 3600 for a, b in zip(samples, samples[1:])]
        if gaps:
            self.reg_vars["median"].set(fmt_gap(sorted(gaps)[len(gaps) // 2]))
            self.reg_vars["maxgap"].set(fmt_gap(max(gaps)))
        else:
            self.reg_vars["median"].set("---")
            self.reg_vars["maxgap"].set("---")
        if last_dt is not None:
            since_h = (datetime.now() - last_dt).total_seconds() / 3600
            self.reg_vars["since"].set(fmt_gap(since_h))
            self.reg_lbls["since"].configure(
                text_color=("#c0392b", "#e74c3c") if since_h >= 72 else ("gray20", "gray80"))
        else:
            self.reg_vars["since"].set("---")

        events = [(dt, ("#c0392b", "#e74c3c") if kind == "diarrhea" else ("#b26a00", "#e67e22"), text)
                  for dt, kind, text in detect_events(samples)]

        for widget in self.episodes_scroll.winfo_children():
            widget.destroy()
        if events:
            for dt, color, text in sorted(events, key=lambda e: e[0], reverse=True):
                ctk.CTkLabel(self.episodes_scroll, text=text, text_color=color, justify="left",
                             wraplength=500, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=8, pady=3)
        else:
            ctk.CTkLabel(self.episodes_scroll, text="Brak wykrytych epizodów w wybranym zakresie.").pack(pady=15)

        part_stats = daypart_stats(samples)

        if MATPLOTLIB_AVAILABLE:
            hour_counts = Counter(dt.hour for dt, s in samples)
            self.ax_hours.clear()
            self.ax_hours.bar(range(24), [hour_counts.get(h, 0) for h in range(24)], color="#3b8ed0")
            self.ax_hours.set_title("Wpisy wg godziny", fontsize=10)
            self.ax_hours.set_xticks([0, 6, 12, 18])
            self.ax_hours.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            self.ax_hours.tick_params(labelsize=7)

            self.ax_daypart.clear()
            self.ax_daypart.bar([p[0] for p in part_stats], [p[2] for p in part_stats], color="#2fa572")
            self.ax_daypart.set_title("Śr. skala wg pory dnia", fontsize=10)
            self.ax_daypart.set_ylim(0, 7)
            self.ax_daypart.tick_params(labelsize=7)
            self.analysis_canvas.draw()
        else:
            for widget in self.daypart_frame.winfo_children():
                widget.destroy()
            for name, count, avg in part_stats:
                text = f"{name}: {count} wpisów, śr. skala {avg:.1f}" if count else f"{name}: brak wpisów"
                ctk.CTkLabel(self.daypart_frame, text=text, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=1)

    # --- Zakładka "Kalendarz" ---

    def setup_calendar_tab(self):
        header = ctk.CTkFrame(self.tab_cal, fg_color="transparent")
        header.pack(pady=(10, 0))
        ctk.CTkButton(header, text="<", width=40, command=lambda: self.shift_month(-1)).pack(side="left", padx=5)
        self.cal_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=16, weight="bold"), width=180)
        self.cal_label.pack(side="left", padx=5)
        ctk.CTkButton(header, text=">", width=40, command=lambda: self.shift_month(1)).pack(side="left", padx=5)
        ctk.CTkButton(header, text="Dziś", width=60, command=self.goto_today).pack(side="left", padx=(15, 5))

        self.cal_stats_label = ctk.CTkLabel(self.tab_cal, text="", font=ctk.CTkFont(size=11))
        self.cal_stats_label.pack(pady=(4, 0))

        self.cal_grid = ctk.CTkFrame(self.tab_cal, fg_color="transparent")
        self.cal_grid.pack(pady=(6, 0))

        legend = ctk.CTkFrame(self.tab_cal, fg_color="transparent")
        legend.pack(pady=(8, 0))
        for color, text in [(("#1e7e34", "#2fa572"), "3–4 optymalnie"),
                            (("#b7950b", "#d4ac0d"), "2–3 / 4–5"),
                            (("#d35400", "#e67e22"), "1–2 / 5–6"),
                            (("#c0392b", "#e74c3c"), "1 / 6–7")]:
            ctk.CTkFrame(legend, width=14, height=14, fg_color=color).pack(side="left", padx=(12, 4))
            ctk.CTkLabel(legend, text=text, font=ctk.CTkFont(size=10)).pack(side="left")

        self.cal_detail = ctk.CTkLabel(self.tab_cal, text="Kliknij dzień, aby zobaczyć wpisy.",
                                       justify="left", wraplength=540, font=ctk.CTkFont(size=11))
        self.cal_detail.pack(pady=(8, 10), padx=15)

        today = datetime.now().date()
        self.cal_year, self.cal_month = today.year, today.month
        self.cal_selected = None
        self.refresh_calendar()

    def shift_month(self, delta):
        month = self.cal_month + delta
        if month < 1:
            month, self.cal_year = 12, self.cal_year - 1
        elif month > 12:
            month, self.cal_year = 1, self.cal_year + 1
        self.cal_month = month
        self.cal_selected = None
        self.refresh_calendar()

    def goto_today(self):
        today = datetime.now().date()
        self.cal_year, self.cal_month = today.year, today.month
        self.cal_selected = None
        self.refresh_calendar()

    def refresh_calendar(self):
        if not hasattr(self, "cal_grid"):
            return
        for widget in self.cal_grid.winfo_children():
            widget.destroy()
        for col, name in enumerate(WEEKDAYS_PL):
            ctk.CTkLabel(self.cal_grid, text=name, font=ctk.CTkFont(size=11, weight="bold")
                         ).grid(row=0, column=col, padx=3, pady=2)
        self.cal_label.configure(text=f"{MONTHS_PL[self.cal_month - 1]} {self.cal_year}")

        by_day = {}
        for row in self.read_entries():
            try:
                d = datetime.strptime(row[0], DATE_FMT).date()
                scale = int(row[2])
            except ValueError:
                continue
            if d.year == self.cal_year and d.month == self.cal_month:
                by_day.setdefault(d.day, []).append((row[1], scale, parse_tags(row)))

        month_scales = [s for day_entries in by_day.values() for _, s, _ in day_entries]
        if month_scales:
            self.cal_stats_label.configure(
                text=f"Wpisy: {len(month_scales)}   Śr. skala: {sum(month_scales) / len(month_scales):.1f}")
        else:
            self.cal_stats_label.configure(text="Brak wpisów w tym miesiącu.")

        first_weekday, n_days = calendar.monthrange(self.cal_year, self.cal_month)
        self.cal_cells = {}
        for day in range(1, n_days + 1):
            row, col = divmod(first_weekday + day - 1, 7)
            day_entries = by_day.get(day)
            if day_entries:
                avg = sum(s for _, s, _ in day_entries) / len(day_entries)
                fg, txt = heat_colors(avg)
                label = str(day) if len(day_entries) == 1 else f"{day}\n×{len(day_entries)}"
            else:
                fg, txt = ("#e8e8e8", "#3a3a3a"), ("gray50", "gray60")
                label = str(day)
            btn = ctk.CTkButton(self.cal_grid, text=label, width=64, height=48, fg_color=fg,
                                hover_color=fg, text_color=txt,
                                font=ctk.CTkFont(size=12, weight="bold"),
                                command=lambda d=day: self.show_day_detail(d))
            btn.grid(row=row + 1, column=col, padx=3, pady=3)
            self.cal_cells[day] = btn

        if self.cal_selected in self.cal_cells:
            self.show_day_detail(self.cal_selected)
        else:
            self.cal_detail.configure(text="Kliknij dzień, aby zobaczyć wpisy.")

    def show_day_detail(self, day):
        self.cal_selected = day
        for d, btn in self.cal_cells.items():
            btn.configure(border_width=2 if d == day else 0, border_color="#3b8ed0")
        date_str = f"{day:02d}.{self.cal_month:02d}.{self.cal_year}"
        day_entries = []
        for row in self.read_entries():
            if row[0] == f"{self.cal_year}-{self.cal_month:02d}-{day:02d}":
                day_entries.append(row)
        if not day_entries:
            self.cal_detail.configure(text=f"{date_str}: brak wpisów.")
            return
        lines = [f"{date_str} — {len(day_entries)} {plural_wpisy(len(day_entries))}:"]
        for row in sorted(day_entries, key=lambda r: r[1]):
            tags = parse_tags(row)
            line = f"{row[1]}  typ {row[2]}"
            if tags:
                line += f"  [{', '.join(tags)}]"
            lines.append(line)
        self.cal_detail.configure(text="\n".join(lines))

    def open_export_dialog(self):
        top = ctk.CTkToplevel(self)
        top.title("Eksport do PDF")
        top.geometry("360x320")
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="Zakres raportu:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(14, 4))
        range_var = ctk.StringVar(value="Cała historia")
        ctk.CTkOptionMenu(top, values=["Cała historia", "Ostatnie 7 dni", "Ostatnie 30 dni", "Własny zakres"],
                          variable=range_var, width=220,
                          command=lambda _: toggle()).pack(pady=4)

        custom = ctk.CTkFrame(top, fg_color="transparent")
        today = datetime.now().date()
        od_var = ctk.StringVar(value=(today - timedelta(days=29)).strftime(DATE_FMT))
        do_var = ctk.StringVar(value=today.strftime(DATE_FMT))
        od_btn = ctk.CTkButton(custom, text="", width=140,
                               command=lambda: self.open_date_picker(od_var))
        do_btn = ctk.CTkButton(custom, text="", width=140,
                               command=lambda: self.open_date_picker(do_var))
        od_var.trace_add("write", lambda *a: od_btn.configure(text=f"Od:  {od_var.get()}"))
        do_var.trace_add("write", lambda *a: do_btn.configure(text=f"Do:  {do_var.get()}"))
        od_btn.configure(text=f"Od:  {od_var.get()}")
        do_btn.configure(text=f"Do:  {do_var.get()}")
        od_btn.grid(row=0, column=0, padx=5, pady=5)
        do_btn.grid(row=0, column=1, padx=5, pady=5)

        def toggle():
            if range_var.get() == "Własny zakres":
                custom.pack(pady=6, before=export_btn)
            else:
                custom.pack_forget()

        def do_export():
            val = range_var.get()
            entries = self.read_entries()
            if val in ("Ostatnie 7 dni", "Ostatnie 30 dni"):
                days = 7 if val == "Ostatnie 7 dni" else 30
                cutoff = (datetime.now().date() - timedelta(days=days - 1)).strftime(DATE_FMT)
                entries = [r for r in entries if r[0] >= cutoff]
                label = val
            elif val == "Własny zakres":
                od, do = od_var.get(), do_var.get()
                try:
                    od_d = datetime.strptime(od, DATE_FMT).date()
                    do_d = datetime.strptime(do, DATE_FMT).date()
                except ValueError:
                    messagebox.showerror("Błąd", "Nieprawidłowa data. Wymagany format: RRRR-MM-DD.")
                    return
                if od_d > do_d:
                    messagebox.showerror("Błąd", "Data „Od” jest późniejsza niż „Do”.")
                    return
                entries = [r for r in entries if od <= r[0] <= do]
                label = f"{od} – {do}"
            else:
                label = "Cała historia"
            if not entries:
                messagebox.showwarning("Brak danych", "Brak wpisów w wybranym zakresie.")
                return
            top.destroy()
            self.export_to_pdf(entries, label)

        export_btn = ctk.CTkButton(top, text="Eksportuj", width=140, command=do_export)
        export_btn.pack(pady=12)

    def export_to_pdf(self, entries=None, range_label="Cała historia"):
        """Generuje raport PDF z wpisów (domyślnie cała historia) dla wybranego zakresu."""
        if not PDF_AVAILABLE:
            messagebox.showerror("Błąd", "Biblioteka 'reportlab' nie jest zainstalowana.\nUruchom w terminalu: pip install reportlab")
            return

        all_entries = entries if entries is not None else self.read_entries()
        if not all_entries:
            messagebox.showwarning("Ostrzeżenie", "Brak danych do eksportu.")
            return

        # Sortowanie chronologiczne (najstarsze na górze w PDF dla czytelności raportu)
        all_entries.sort(key=lambda x: (x[0], x[1]))

        try:
            font = register_pdf_font()
            if font is None:
                font = "Helvetica"
                messagebox.showwarning("Ostrzeżenie",
                                       "Nie znaleziono fontu z polskimi znakami — diakrytyki mogą być niepoprawne w PDF.")
            font_bold = f"{font}-Bold" if font == "ReportFont" else "Helvetica-Bold"

            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            filename_pdf = os.path.join(BASE_DIR, f"BM_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            doc = SimpleDocTemplate(filename_pdf, pagesize=letter)
            elements = []

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle("ReportTitle", parent=styles['Title'], fontName=font_bold)
            normal_style = ParagraphStyle("ReportNormal", parent=styles['Normal'], fontName=font)
            cell_style = ParagraphStyle("ReportCell", fontName=font, fontSize=9, leading=12)
            header_style = ParagraphStyle("ReportHeader", fontName=font_bold, fontSize=10, leading=12,
                                          textColor=colors.whitesmoke, alignment=1)

            elements.append(Paragraph("Raport Monitorowania Zdrowia (BM Reporter)", title_style))
            elements.append(Paragraph(f"Data generowania: {now}", normal_style))
            elements.append(Paragraph(f"Zakres raportu: {escape(range_label)}", normal_style))
            elements.append(Spacer(1, 12))

            heading_style = ParagraphStyle("ReportHeading", fontName=font_bold, fontSize=13,
                                           spaceBefore=14, spaceAfter=6)

            def section(text):
                elements.append(Paragraph(escape(text), heading_style))

            def make_table(rows, widths):
                data = [[Paragraph(escape(str(c)).replace("\n", "<br/>"),
                                   header_style if r == 0 else cell_style)
                         for c in row] for r, row in enumerate(rows)]
                t = Table(data, repeatRows=1, colWidths=widths)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.dodgerblue),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                return t

            samples = []
            for row in all_entries:
                try:
                    dt = datetime.strptime(row[0] + " " + row[1], DATE_FMT + " " + TIME_FMT)
                    scale = int(row[2])
                except ValueError:
                    continue
                samples.append((dt, scale, set(parse_tags(row))))
            samples.sort(key=lambda x: x[0])
            scales = [s for _, s, _ in samples]
            today = datetime.now().date()

            def optimal_pct(sel):
                return 100 * sum(1 for s in sel if s in (3, 4)) / len(sel) if sel else None

            section("Podsumowanie")
            sum_rows = [["Zakres", "Wpisy", "Średnia", "% optymalnych (3–4)", "Trend vs poprz. okres"]]
            for label, days in [("Całość", None), ("Ostatnie 7 dni", 7), ("Ostatnie 30 dni", 30)]:
                if days is None:
                    sel, prev = scales, []
                else:
                    cutoff = today - timedelta(days=days - 1)
                    prev_cutoff = cutoff - timedelta(days=days)
                    sel = [s for dt, s, _ in samples if dt.date() >= cutoff]
                    prev = [s for dt, s, _ in samples if prev_cutoff <= dt.date() < cutoff]
                if sel:
                    opt = optimal_pct(sel)
                    trend = f"{opt - optimal_pct(prev):+.0f} pp" if prev else "---"
                    sum_rows.append([label, str(len(sel)), f"{sum(sel) / len(sel):.1f}", f"{opt:.0f}%", trend])
                else:
                    sum_rows.append([label, "0", "---", "---", "---"])
            elements.append(make_table(sum_rows, [100, 50, 70, 110, 138]))

            section("Skala Bristol")
            elements.append(make_table([["Typ", "Opis"]] + [[str(i), BRISTOL_DESC[i]] for i in range(1, 8)],
                                       [40, 428]))

            section("Historia wpisów")
            hist_rows = [CSV_HEADER]
            for entry in all_entries:
                cells = list(entry)
                cells[4] = ", ".join(parse_tags(entry))
                hist_rows.append(cells)
            elements.append(make_table(hist_rows, [70, 58, 52, 178, 110]))

            section("Korelacje tagów")
            corr = correlate_tags([(s, tags) for _, s, tags in samples])
            if corr:
                corr_rows = [["Tag", "Wpisy", "Śr. z tagiem", "Śr. bez tagu", "Różnica"]]
                for tag, count, avg_with, avg_without, delta in corr:
                    corr_rows.append([tag, str(count) + ("*" if count < 3 else ""), f"{avg_with:.1f}",
                                      f"{avg_without:.1f}" if avg_without is not None else "---",
                                      f"{delta:+.1f}" if delta is not None else "---"])
                elements.append(make_table(corr_rows, [120, 60, 90, 90, 108]))
                elements.append(Paragraph("* mniej niż 3 wpisy — wynik mało wiarygodny. Korelacja to nie przyczyna.",
                                          normal_style))
            else:
                elements.append(Paragraph("Brak wpisów z tagami.", normal_style))

            section("Analiza")
            gaps = [(b[0] - a[0]).total_seconds() / 3600 for a, b in zip(samples, samples[1:])]
            if gaps:
                reg = (f"Mediana odstępów: {fmt_gap(sorted(gaps)[len(gaps) // 2])}; "
                       f"najdłuższa przerwa: {fmt_gap(max(gaps))}.")
            else:
                reg = "Za mało wpisów, aby ocenić regularność."
            if samples:
                reg += f" Od ostatniego wpisu: {fmt_gap((datetime.now() - samples[-1][0]).total_seconds() / 3600)}."
            elements.append(Paragraph(escape(reg), normal_style))
            elements.append(Spacer(1, 6))
            elements.append(make_table([["Pora dnia", "Wpisy", "Śr. skala"]] +
                                       [[name, str(count), f"{avg:.1f}" if count else "---"]
                                        for name, count, avg in daypart_stats([(dt, s) for dt, s, _ in samples])],
                                       [156, 156, 156]))
            elements.append(Spacer(1, 6))
            events = detect_events([(dt, s) for dt, s, _ in samples])
            if events:
                for dt, kind, text in sorted(events, key=lambda e: e[0], reverse=True):
                    ev_style = ParagraphStyle("Event", parent=normal_style,
                                              textColor=colors.HexColor("#c0392b" if kind == "diarrhea" else "#b26a00"))
                    elements.append(Paragraph(escape(text), ev_style))
            else:
                elements.append(Paragraph("Brak wykrytych epizodów (biegunka: ≥3 wpisy typu 6–7 w 24 h; "
                                          "możliwe zaparcie: przerwa ≥3 dni).", normal_style))

            section("Kalendarz (heatmapa)")
            elements.append(Paragraph("Kolor dnia = średnia skala Bristol: zielony 3–4 (optymalnie), żółty 2–3 / 4–5, "
                                      "pomarańczowy 1–2 / 5–6, czerwony 1 / 6–7; szary = brak wpisów.", normal_style))
            months = {}
            for dt, s, _ in samples:
                months.setdefault((dt.year, dt.month), {}).setdefault(dt.day, []).append(s)
            for (y, m), days in sorted(months.items()):
                elements.append(Spacer(1, 8))
                elements.append(Paragraph(f"{MONTHS_PL[m - 1]} {y}", normal_style))
                first, n_days = calendar.monthrange(y, m)
                rows = [WEEKDAYS_PL]
                week = [""] * first
                for day in range(1, n_days + 1):
                    week.append(str(day))
                    if len(week) == 7:
                        rows.append(week)
                        week = []
                if week:
                    rows.append(week + [""] * (7 - len(week)))
                cmds = [('FONTNAME', (0, 0), (-1, -1), font),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.dodgerblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke)]
                for r, row in enumerate(rows[1:], start=1):
                    for c, val in enumerate(row):
                        if not val:
                            continue
                        day = int(val)
                        if day in days:
                            bg, txt = heat_colors(sum(days[day]) / len(days[day]))
                            cmds.append(('BACKGROUND', (c, r), (c, r), colors.HexColor(bg[0])))
                            cmds.append(('TEXTCOLOR', (c, r), (c, r),
                                         colors.white if txt[0] == "white" else colors.HexColor(txt[0])))
                        else:
                            cmds.append(('BACKGROUND', (c, r), (c, r), colors.HexColor("#eeeeee")))
                cal_table = Table(rows, colWidths=[67] * 6 + [66])
                cal_table.setStyle(TableStyle(cmds))
                elements.append(cal_table)
            doc.build(elements)

            messagebox.showinfo("Sukces", f"Raport został wygenerowany:\n{filename_pdf}")
        except Exception as e:
            messagebox.showerror("Błąd eksportu", f"Wystąpił błąd podczas tworzenia PDF: {e}")

if __name__ == "__main__":
    app = BMReporter()
    app.mainloop()
