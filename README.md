# Quran Segmenter

A production-grade tool for generating timed subtitle segments for Quran video recitations. Splits verses into readable segments with synchronized Arabic text and translations.

## Features

- **Multi-language support**: Works with any translation
- **Automatic segmentation**: Uses LLM to intelligently split long verses
- **Audio alignment**: Synchronizes text with recitation audio
- **Flexible verse selection**: Single verse, ranges, or entire surahs
- **Persistent state**: Google Drive integration for Colab, local storage for CLI
- **Caching**: Avoids redundant computation

## Quick Start

### Option 1: Google Colab (Recommended for beginners)

1. Open the notebook: [quran_segmenter_colab.ipynb](notebooks/quran_segmenter_colab.ipynb)
2. Run **Cell 1** to install dependencies (~10 minutes first time)
3. Run **Cell 2** to mount Google Drive and initialize
4. Follow the cells in order

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/yourname/quran-segmenter.git
cd quran-segmenter

# Install the package
pip install -e .

# Initialize project
quran-segmenter init --data-dir ./quran_data

# Register a translation
quran-segmenter register en-sahih ./translations/en-sahih.json \
    --name "Sahih International" --language en

# Prepare translation (one-time)
export GEMINI_API_KEY=your_key
quran-segmenter prepare en-sahih

# Process audio
quran-segmenter process audio.mp3 "2:282" en-sahih -o output.json
```

## Required Files

Before using the tool, you need these data files:

| File                         | Description          | Where to get |
|------------------------------|-----------------------|--------------|
| `qpc-hafs-word-by-word.json` | Arabic word data      | QPC Data     |
| `quran-metadata-misc.json`   | Verse metadata        | Same source  |
| `{translation}.json`         | Translation file      | Various sources |

---

## Verse Specification Format

The tool accepts these verse formats:

| Format        | Example      | Description                     |
|---------------|--------------|---------------------------------|
| Single verse  | `2:282`      | Surah 2, verse 282              |
| Verse range   | `2:255-260`  | Surah 2, verses 255–260         |
| Full surah    | `2`          | All 286 verses of Surah 2       |
| First N verses| `2:1-10`     | First 10 verses of Surah 2      |

**Note:** Cross-surah ranges (e.g., `2:286-3:5`) are **not** supported.

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ONE-TIME SETUP (per translation)             │
├─────────────────────────────────────────────────────────────────┤
│  1. jumlize     │ LLM splits translation into segments          │
│  2. rabtize     │ Generate span embeddings (global, once)       │
│  3. rabtize     │ Generate segment embeddings (per translation) │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING (per audio file)                  │
├─────────────────────────────────────────────────────────────────┤
│  1. lafzize     │ Audio → word-level timestamps                 │
│  2. rabtize     │ Align translation segments to Arabic words    │
│  3. assembler   │ Combine into final timed segments             │
└─────────────────────────────────────────────────────────────────┘
```

## Output Format

```json
{
  "2:282": [
    {
      "start": 0.04,
      "end": 4.74,
      "arabic": "يَٰٓأَيُّهَا ٱلَّذِينَ ءَامَنُوٓاْ",
      "translation": "O you who believe!",
      "is_last": false
    },
    {
      "start": 5.92,
      "end": 16.02,
      "arabic": "إِذَا تَدَايَنتُم بِدَيۡنٍ إِلَىٰٓ أَجَلٖ مُّسَمّٗى فَٱكۡتُبُوهُۚ",
      "translation": "When you contract a debt for a specified term, write it down.",
      "is_last": false
    }
  ]
}
```

## Configuration

Configuration is stored in `data/config.json` and persists across sessions:
```json
{
  "translations": {
    "en-sahih": {
      "id": "en-sahih",
      "name": "Sahih International",
      "is_segmented": true,
      "embeddings_path": "data/embeddings/en-sahih.npz"
    }
  },
  "spans_embeddings_generated": true
}
```

## Troubleshooting

### "Translation not prepared" error
Run `quran-segmenter prepare <translation_id>` first.

### Lafzize server won't start
Check that `quran-metadata-misc.json` is in the lafzize directory.

### State lost after Colab restart
Make sure Google Drive is mounted and you ran the initialization cell.

### LLM segmentation fails
Some verses may need higher model settings. The tool will report which verses failed.

## License

MIT