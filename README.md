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

Open the Colab notebook and run it there: [quran_segmenter_colab.ipynb](notebooks/quran_segmenter_colab.ipynb). Upload at least these three files before running the processing cells; the first cell will install dependencies via `quran-segmenter setup-colab`:

- [`qpc-hafs-word-by-word.json`](https://qul.tarteel.ai/resources/quran-script/312) (words)
- [`quran-metadata-misc.json`](https://git.sr.ht/~rehandaphedar/quranic-universal-library-extras/blob/main/quran-metadata-misc.json) (metadata)
- Your recitation audio as an `.mp3` (found in the reciter JSONs downloadable from https://qul.tarteel.ai/resources/recitation)

**Fast start (English demo):**
- Use the provided pre-segmented translation at `example/en-sahih-international-simple.json`.
- Download embeddings from the Hugging Face dataset (contains `spans.npz` and `en-sahih-international-simple.npz`): `git clone https://huggingface.co/datasets/rehandaphedar/rabtize ./quran_data/embeddings`.
- Register with `translation_id=en-sahih-international-simple` and point to those two `.npz` files to skip LLM segmentation.

**New language:**
- Bring a translation JSON, register it with `quran-segmenter register`, then run `quran-segmenter prepare <translation_id>` (requires `GEMINI_API_KEY`) to generate segments and embeddings.

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

| Format         | Example                   | Description                                                                      |
|----------------|---------------------------|----------------------------------------------------------------------------------|
| Single verse   | `2:282`                   | Surah 2, verse 282                                                               |
| Verse range    | `2:255-260`               | Surah 2, verses 255–260                                                          |
| Full surah     | `2`                       | All 286 verses of Surah 2                                                        |
| First N verses | `2:1-10`                  | First 10 verses of Surah 2                                                       |
| Preface phrases| `taawwudh+basmalah+2:1-5` | Prepend taawwudh and/or basmalah before the verses (also works for full surahs)  |

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
