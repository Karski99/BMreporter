# BM Reporter

A desktop app for gut health monitoring — a bowel movement diary based on the **Bristol Stool Scale**, with entry history, statistics, charts, and PDF report export.

Polish-language UI, built with CustomTkinter (modern look, light/dark mode following the system theme).

## Features

- **Add Entry** — date and time (defaulting to now), Bristol scale consistency (1–7), free-form description/notes. Validation of date (`YYYY-MM-DD`) and time (`HH:MM`) formats.
- **History** — entry list sorted newest first, with **edit** and **delete** (with confirmation) and a Bristol scale filter.
- **Statistics** — average scale, most frequent value, and entry count for the last **7 or 30 days**.
- **Charts** (matplotlib) — daily entry count and Bristol scale distribution for a selected range (7/30 days).
- **PDF export** (reportlab) — full-history report as a table, with Polish diacritics support (DejaVu Sans / Arial).

### Bristol Stool Scale

| Type | Description |
|------|-------------|
| 1 | Separate hard lumps |
| 2 | Sausage-shaped, lumpy |
| 3 | Sausage-shaped with cracks |
| 4 | Smooth, soft sausage (optimal) |
| 5 | Soft blobs with clear edges |
| 6 | Fluffy, ragged pieces |
| 7 | Entirely liquid |

## Requirements

- Python 3.10+
- Dependencies:

```bash
pip install customtkinter matplotlib reportlab
```

> `matplotlib` and `reportlab` are optional — the app runs without them, but the "Charts" tab and PDF export are disabled.

## Running

```bash
python bm_reporter.py
```

## Building the .exe (Windows)

```bash
pip install pyinstaller
pyinstaller BMReporter.spec
```

The `BMReporter.exe` file will appear in the `dist/` directory. The app is windowed (no console), with the `icons/app.ico` icon.

## Data storage

Entries are saved to **`history.csv`** (UTF-8, header: `Data, Godzina, Skala Bristol, Opis` — i.e. date, time, Bristol scale, description):

- when run from the script — next to `bm_reporter.py`,
- when run from the `.exe` — next to the executable (not in the temporary extraction directory).

The file is created automatically on first launch.

> **Privacy:** `history.csv` and generated PDF reports are private health data — they are excluded from the repository via `.gitignore` and are never uploaded anywhere. All data stays local on your computer.

## Project structure

```
├── bm_reporter.py        # the whole app (GUI + logic + CSV + PDF)
├── BMReporter.spec       # PyInstaller configuration (.exe build)
├── icons/
│   ├── app.ico           # application icon
│   ├── generate_icons.py # icon generation script (PIL)
│   └── propozycja-*.png  # alternative icon designs
└── .gitignore
```

## Tech stack

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — GUI
- [matplotlib](https://matplotlib.org/) — charts
- [ReportLab](https://www.reportlab.com/) — PDF generation
- [PyInstaller](https://pyinstaller.org/) — packaging into `.exe`