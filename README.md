# BM Reporter

Desktopowa aplikacja do monitorowania zdrowia jelit — dziennik wypróżnień oparty na **skali Bristol**, z historią wpisów, statystykami, wykresami i eksportem raportu do PDF.

Interfejs w języku polskim, zbudowany w CustomTkinter (nowoczesny wygląd, tryb jasny/ciemny zgodny z systemem).

## Funkcje

- **Dodaj Wpis** — data i godzina (domyślnie bieżące), konsystencja w skali Bristol (1–7), dowolny opis/uwagi. Walidacja formatów daty (`RRRR-MM-DD`) i godziny (`HH:MM`).
- **Historia** — lista wpisów sortowana od najnowszych, z możliwością **edycji** i **usuwania** (z potwierdzeniem) oraz filtrem po skali Bristol.
- **Statystyki** — średnia skala, najczęstsza wartość i liczba wpisów z ostatnich **7 lub 30 dni**.
- **Wykresy** (matplotlib) — liczba wpisów dziennie oraz rozkład skali Bristol w wybranym zakresie (7/30 dni).
- **Eksport do PDF** (reportlab) — raport z pełną historią w formie tabeli, z obsługą polskich znaków (DejaVu Sans / Arial).

### Skala Bristol

| Typ | Opis |
|-----|------|
| 1 | Twarde grudki |
| 2 | Kiełbaskowaty, grudkowaty |
| 3 | Kiełbaskowaty z pęknięciami |
| 4 | Miękki, gładki kawałek (optymalny) |
| 5 | Miękkie kawałki z brzegami |
| 6 | Puszysty, nierówny |
| 7 | Płynny |

## Wymagania

- Python 3.10+
- Biblioteki:

```bash
pip install customtkinter matplotlib reportlab
```

> `matplotlib` i `reportlab` są opcjonalne — bez nich aplikacja działa, ale zakładka „Wykresy" i eksport PDF są wyłączone.

## Uruchomienie

```bash
python bm_reporter.py
```

## Budowanie wersji .exe (Windows)

```bash
pip install pyinstaller
pyinstaller BMReporter.spec
```

Plik `BMReporter.exe` pojawi się w katalogu `dist/`. Aplikacja jest okienkowa (bez konsoli), z ikoną `icons/app.ico`.

## Przechowywanie danych

Wpisy zapisywane są w pliku **`history.csv`** (UTF-8, nagłówek: `Data, Godzina, Skala Bristol, Opis`):

- przy uruchomieniu ze skryptu — obok `bm_reporter.py`,
- przy uruchomieniu z `.exe` — obok pliku wykonywalnego (nie w katalogu tymczasowym rozpakowania).

Plik tworzony jest automatycznie przy pierwszym uruchomieniu.

> **Prywatność:** `history.csv` oraz wygenerowane raporty PDF to prywatne dane zdrowotne — są wykluczone z repozytorium przez `.gitignore` i nigdzie nie są wysyłane. Wszystkie dane pozostają lokalnie na Twoim komputerze.

## Struktura projektu

```
├── bm_reporter.py        # cała aplikacja (GUI + logika + CSV + PDF)
├── BMReporter.spec       # konfiguracja PyInstaller (wersja .exe)
├── icons/
│   ├── app.ico           # ikona aplikacji
│   ├── generate_icons.py # skrypt generujący ikony (PIL)
│   └── propozycja-*.png  # alternatywne projekty ikony
└── .gitignore
```

## Technologie

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — GUI
- [matplotlib](https://matplotlib.org/) — wykresy
- [ReportLab](https://www.reportlab.com/) — generowanie PDF
- [PyInstaller](https://pyinstaller.org/) — pakowanie do `.exe`