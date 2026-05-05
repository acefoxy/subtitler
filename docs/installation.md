# Installation

## Requirements

- Python 3.11 or newer
- `ffmpeg`

Optional but recommended:

- `ffsubsync` for fast baseline sync
- `whisperx` for the default high-quality alignment path
- CUDA-capable GPU for faster WhisperX runs

## Ubuntu or Debian

```bash
sudo apt-get install ffmpeg
git clone https://github.com/acefoxy/subtitler.git
cd subtitler
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[sync,hq-sync]
```

## Install Docs Dependencies

If you want to build the documentation site locally:

```bash
python -m pip install -e .[docs]
```

## Verify The CLI

```bash
subtitler --help
```

If the console script is not on your `PATH`, run it through the virtual environment:

```bash
.venv/bin/subtitler --help
```