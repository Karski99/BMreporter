# BM Reporter

A desktop app for gut health monitoring — a bowel movement diary based on the **Bristol Stool Scale**, with entry history, statistics, charts, and PDF report export.

Polish and English UI with a **language switcher** (top-right; the choice is persisted in `settings.json`), built with CustomTkinter (modern look, light/dark mode following the system theme). PDF reports follow the selected language. Tag values are stored canonically in Polish in `history.csv` for compatibility and displayed in the active language.

## Features

- **Language switcher** — full Polish/English UI (top-right selector); the choice is persisted in `settings.json` and the whole interface rebuilds instantly. PDF reports follow the selected language.
- **Add Entry** — date and time (defaulting to now) chosen via a **popup calendar** and a **digital clock picker** (large HH:MM display with up/down steppers and sliders, "now" shortcut), **graphical Bristol scale selector** (7 illustrated, clickable thumbnails with a live description of the selected type), **symptom/factor tags** (13 presets: abdominal pain, bloating, blood, mucus, nausea, stress, alcohol, coffee, spicy meal, dairy, fast food, medication, soiling episodes), free-form description/notes.
- **History** — entry list sorted newest first, with **edit** and **delete** (with confirmation), plus Bristol scale **and tag filters**. Tags are shown on each entry.
- **Statistics** — average scale, most frequent value, entry count, **% of optimal entries (types 3–4)** and the **trend vs the previous period** (percentage points, color-coded) for the last **7 or 30 days**.
- **Correlations** — per-tag table: entry count, average Bristol scale **with vs. without** the tag, and the difference (positive = looser stool, negative = harder). Range: 7/30 days or all time. Samples under 3 entries are flagged as unreliable.
- **Analysis** (scrollable) — regularity (median gap between entries, longest gap, time since last entry with a ≥3-day warning), **episode detection** (diarrhea: ≥3 entries of type 6–7 within 24 h; possible constipation: gaps ≥3 days), **time-of-day patterns** (entries-per-hour histogram + average scale by night/morning/afternoon/evening), **7-day moving-average trend** with the optimal 3–4 band, **weekday rhythm** (average scale per weekday, heat-colored), **episode/gap timeline** (bars on a date axis), **tag co-occurrence** (tag pairs counted within the same entry), and **rule-based insights** (tag effects, week-over-week changes in % optimal and average, episodes, long gaps, share of extreme entries). Range: 7/30 days or all time.
- **Calendar** — monthly **heatmap**: each day colored by its average Bristol scale (green = optimal 3–4, yellow/orange/red = increasing deviation), entry counters on busy days, month navigation, per-month summary, and a click-to-view day detail (times, types, tags).
- **Charts** (matplotlib) — four panels for the selected range (7/30 days): daily entry count with diarrhea-episode days highlighted in red, Bristol scale distribution, daily average scale with the optimal 3–4 band, and a tag-correlation bar chart (difference of averages).
- **PDF export** (reportlab) — multi-section report with a **selectable date range** (whole history, last 7/30 days, or a custom from–to range via calendar pickers): summary (counts, averages, % optimal, trend vs previous period), Bristol scale legend, history table with tags, tag correlations, analysis (regularity, detected episodes, time-of-day, week-vs-week comparison, weekday rhythm table, embedded 7-day trend chart, tag co-occurrence table, episode/gap timeline chart, rule-based insights), and monthly calendar heatmaps. Generated in the selected UI language (Polish/English), with diacritics-capable fonts (DejaVu Sans / Arial).

### Bristol Stool Scale

| Type | Description |
|------|-------------|
| 1 | Separate hard lumps, like nuts (difficult to pass) |
| 2 | Sausage-shaped, but lumpy |
| 3 | Like a sausage but with cracks on its surface |
| 4 | Like a sausage or snake, smooth and soft (average stool) |
| 5 | Soft blobs with clear cut edges |
| 6 | Fluffy pieces with ragged edges, a mushy stool (diarrhoea) |
| 7 | Watery, no solid pieces, entirely liquid (diarrhoea) |

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

Entries are saved to **`history.csv`** (UTF-8, header: `Data, Godzina, Skala Bristol, Opis, Tagi` — i.e. date, time, Bristol scale, description, semicolon-separated tags):

- when run from the script — next to `bm_reporter.py`,
- when run from the `.exe` — next to the executable (not in the temporary extraction directory).

The file is created automatically on first launch. Files in the older 4-column format (without `Tagi`) are read seamlessly and upgraded to the new header on the next save/edit/delete. Tag values are stored canonically in Polish (for backward compatibility) and displayed in the active UI language.

The UI language preference is saved to **`settings.json`** (next to the script/executable, default: Polish).

> **Privacy:** `history.csv`, generated PDF reports and `settings.json` are local-only — excluded from the repository via `.gitignore` and never uploaded anywhere. All data stays on your computer.

## Project structure

```
├── bm_reporter.py        # the whole app (GUI + logic + CSV + PDF)
├── BMReporter.spec       # PyInstaller configuration (.exe build)
├── icons/
│   ├── app.ico           # application icon
│   ├── generate_icons.py # icon generation script (PIL)
│   ├── generate_bristol.py # Bristol scale thumbnail generation script (PIL)
│   ├── bristol/type1-7.png # Bristol scale illustrations used by the entry form
│   └── propozycja-*.png  # alternative icon designs
└── .gitignore
```

## Tech stack

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — GUI
- [matplotlib](https://matplotlib.org/) — charts
- [ReportLab](https://www.reportlab.com/) — PDF generation
- [PyInstaller](https://pyinstaller.org/) — packaging into `.exe`