# subtitler

[![CI](https://github.com/acefoxy/subtitler/actions/workflows/ci.yml/badge.svg)](https://github.com/acefoxy/subtitler/actions/workflows/ci.yml)
[![Docs](https://github.com/acefoxy/subtitler/actions/workflows/docs.yml/badge.svg)](https://github.com/acefoxy/subtitler/actions/workflows/docs.yml)

`subtitler` is a Python CLI that finds online English subtitles, synchronizes them to your video, and writes a standalone `.srt` file next to the source video.

Documentation site: https://acefoxy.github.io/subtitler/

## Why It Exists

Most subtitle workflows are too manual: find a subtitle, test whether it matches, shift it a bit, try another one, then repeat for every file in a folder. `subtitler` compresses that into one command:

```bash
subtitler "/path/to/video-or-folder"
```

By default it:

- accepts a single video file or a full directory tree
- searches online English subtitles through multiple providers
- extracts audio and performs subtitle synchronization
- prefers high-quality WhisperX alignment when available
- writes a synced `.srt` next to each source file
- prefers GPU for WhisperX automatically when CUDA is available

## Quick Start

On Debian or Ubuntu:

```bash
sudo apt-get install ffmpeg
git clone https://github.com/acefoxy/subtitler.git
cd subtitler
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[sync,hq-sync]
```

Then run:

```bash
subtitler "/path/to/movie.mkv"
```

That creates:

```text
/path/to/movie.srt
```

## Folder Processing

Point `subtitler` at a folder and it will scan recursively for supported video files.

```bash
subtitler "/path/to/folder-with-videos"
```

Examples:

- `Movies/Film.mp4` -> `Movies/Film.srt`
- `Series/Season 1/Episode 01.mkv` -> `Series/Season 1/Episode 01.srt`

If you want the subtitles written to another directory while preserving the relative folder structure:

```bash
subtitler "/path/to/videos" --output-dir "/path/to/output"
```

## Useful Commands

Force overwrite of existing subtitle output:

```bash
subtitler "/path/to/movie.mkv" --overwrite
```

Use a faster baseline sync engine instead of high-quality alignment:

```bash
subtitler "/path/to/movie.mkv" --sync-mode ffsubsync
```

Disable GPU preference for WhisperX:

```bash
subtitler "/path/to/movie.mkv" --no-gpu
```

Skip synchronization entirely and just save the downloaded subtitle:

```bash
subtitler "/path/to/movie.mkv" --sync-mode skip
```

## Requirements

- Python 3.11+
- `ffmpeg`
- `subliminal` for provider search, installed via the package dependencies
- at least one baseline sync engine for non-WhisperX modes:
  - `ffsubsync` recommended
  - `alass` optional fallback if you install its binary separately
- optional but recommended for best results:
  - `whisperx`

## Optional OpenSubtitles Credentials

The default provider chain works without credentials. If you still want direct OpenSubtitles fallback, set:

```bash
export SUBTITLER_OPENSUBTITLES_API_KEY="your_api_key"
export SUBTITLER_OPENSUBTITLES_USERNAME="your_username"
export SUBTITLER_OPENSUBTITLES_PASSWORD="your_password"
```

You can also pass them as CLI flags.

## Development

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Build the docs locally:

```bash
python -m pip install -e .[docs]
mkdocs serve
```

## Notes

- Default output naming is `original_name.srt`.
- Search quality is best when filenames contain clear movie or episode names.
- Default runtime mode is `high-quality` with GPU preference enabled.
- Explicit `high-quality` mode is strict: if WhisperX refinement fails, the command exits with an error instead of silently returning a lower-quality fallback.
