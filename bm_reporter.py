import customtkinter as ctk
from tkinter import messagebox
import csv
import os
import sys
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
CSV_HEADER = ["Data", "Godzina", "Skala Bristol", "Opis"]


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

        self.setup_add_tab()
        self.setup_history_tab()
        self.setup_charts_tab()

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
                return [row for row in reader if len(row) >= 4]
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
        self.date_entry = ctk.CTkEntry(self.tab_add, textvariable=self.date_var, width=300, placeholder_text="Data (RRRR-MM-DD)")
        self.date_entry.pack(pady=5)

        self.time_var = ctk.StringVar(value=datetime.now().strftime(TIME_FMT))
        self.time_entry = ctk.CTkEntry(self.tab_add, textvariable=self.time_var, width=300, placeholder_text="Godzina (HH:MM)")
        self.time_entry.pack(pady=5)

        self.label_scale = ctk.CTkLabel(self.tab_add, text="Skala Bristol (Konsystencja):")
        self.label_scale.pack(pady=(15, 0))

        self.scale_var = ctk.StringVar(value="4")
        self.scale_dropdown = ctk.CTkOptionMenu(
            self.tab_add,
            values=[str(i) for i in range(1, 8)],
            variable=self.scale_var,
            width=300
        )
        self.scale_dropdown.pack(pady=5)

        self.label_hint = ctk.CTkLabel(self.tab_add, text="1: Twarde grudki | 4: Miękki kawałek | 7: Płynny", font=ctk.CTkFont(size=10))
        self.label_hint.pack(pady=2)

        self.label_desc = ctk.CTkLabel(self.tab_add, text="Opis / Dodatkowe uwagi:")
        self.label_desc.pack(pady=(15, 0))

        self.desc_text = ctk.CTkTextbox(self.tab_add, width=300, height=150)
        self.desc_text.pack(pady=5)

        self.btn_save = ctk.CTkButton(self.tab_add, text="Zapisz Wpis", command=self.save_entry, font=ctk.CTkFont(weight="bold"))
        self.btn_save.pack(pady=(30, 5))

        self.btn_cancel_edit = ctk.CTkButton(self.tab_add, text="Anuluj edycję", command=self.cancel_edit, fg_color="gray50", hover_color="gray40")

    def on_tab_change(self, tab_name=None):
        # CTkTabview 6.x wywoluje command bez argumentow przy kliknieciu zakladki
        if tab_name is None:
            tab_name = self.tabview.get()
        if tab_name == "Dodaj Wpis" and self.edit_index is None:
            self.date_var.set(datetime.now().strftime(DATE_FMT))
            self.time_var.set(datetime.now().strftime(TIME_FMT))
        elif tab_name == "Wykresy":
            self.refresh_charts()

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

        self.filter_label = ctk.CTkLabel(self.tab_history, text="Filtruj listę poniżej:")
        self.filter_label.pack(pady=(10, 0))

        self.filter_var = ctk.StringVar(value="Wszystkie")
        filter_options = ["Wszystkie"] + [str(i) for i in range(1, 8)]
        self.filter_menu = ctk.CTkOptionMenu(
            self.tab_history,
            values=filter_options,
            variable=self.filter_var,
            command=lambda _: self.load_history()
        )
        self.filter_menu.pack(pady=5)

        self.history_scroll = ctk.CTkScrollableFrame(self.tab_history, width=520, height=380)
        self.history_scroll.pack(pady=10, padx=10, fill="both", expand=True)

        self.btn_frame = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        self.btn_refresh = ctk.CTkButton(self.btn_frame, text="Odśwież Historię", command=self.load_history)
        self.btn_refresh.grid(row=0, column=0, padx=5)

        self.btn_export = ctk.CTkButton(
            self.btn_frame,
            text="Eksportuj do PDF",
            command=self.export_to_pdf,
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

        row = [date, time, scale, description]

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

    def edit_entry(self, index):
        entries = self.read_entries()
        if not (0 <= index < len(entries)):
            messagebox.showerror("Błąd", "Wpis nie istnieje.")
            return
        row = entries[index]
        self.edit_index = index
        self.date_var.set(row[0])
        self.time_var.set(row[1])
        self.scale_var.set(row[2])
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", row[3])
        self.label_title.configure(text="Edytuj Wpis")
        self.btn_save.configure(text="Zapisz zmiany")
        self.btn_cancel_edit.pack(pady=5)
        self.tabview.set("Dodaj Wpis")

    def cancel_edit(self):
        self.edit_index = None
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

    def load_history(self):
        """Odczytuje dane z CSV, filtruje je i wyświetla jako listę wierszy."""
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        filter_val = self.filter_var.get()
        entries = [(i, row) for i, row in enumerate(self.read_entries())
                   if filter_val == "Wszystkie" or row[2] == filter_val]
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

        if row[3]:
            ctk.CTkLabel(frame, text=row[3], justify="left", wraplength=420,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=8, pady=(2, 6))
        else:
            ctk.CTkFrame(frame, height=4, fg_color="transparent").pack()

    def update_statistics(self):
        """Oblicza statystyki dla wybranego zakresu czasowego i aktualizuje UI."""
        days = 7 if self.range_var.get() == "7 dni" else 30
        cutoff_date = datetime.now().date() - timedelta(days=days - 1)
        recent_scales = []

        for row in self.read_entries():
            try:
                entry_date = datetime.strptime(row[0], DATE_FMT).date()
                if entry_date >= cutoff_date:
                    recent_scales.append(int(row[2]))
            except ValueError:
                continue

        if recent_scales:
            avg = sum(recent_scales) / len(recent_scales)
            self.avg_score_var.set(f"{avg:.1f}")
            self.count_var.set(str(len(recent_scales)))
            self.freq_score_var.set(str(Counter(recent_scales).most_common(1)[0][0]))
        else:
            self.avg_score_var.set("---")
            self.count_var.set("0")
            self.freq_score_var.set("---")

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

    def export_to_pdf(self):
        """Generuje raport PDF z całą historią zapisanych danych."""
        if not PDF_AVAILABLE:
            messagebox.showerror("Błąd", "Biblioteka 'reportlab' nie jest zainstalowana.\nUruchom w terminalu: pip install reportlab")
            return

        all_entries = self.read_entries()
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
            elements.append(Spacer(1, 20))

            data = [[Paragraph(escape(h), header_style) for h in CSV_HEADER]]
            for entry in all_entries:
                data.append([Paragraph(escape(cell).replace("\n", "<br/>"), cell_style) for cell in entry])

            table = Table(data, repeatRows=1, colWidths=[70, 60, 62, 276])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.dodgerblue),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))

            elements.append(table)
            doc.build(elements)

            messagebox.showinfo("Sukces", f"Raport został wygenerowany:\n{filename_pdf}")
        except Exception as e:
            messagebox.showerror("Błąd eksportu", f"Wystąpił błąd podczas tworzenia PDF: {e}")

if __name__ == "__main__":
    app = BMReporter()
    app.mainloop()
