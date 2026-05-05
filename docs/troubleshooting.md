# Troubleshooting

## `ffmpeg binary not found`

Install `ffmpeg` and make sure it is on your `PATH`.

```bash
sudo apt-get install ffmpeg
```

## `No usable English subtitles found`

This usually means one of these:

- the providers did not have a usable match
- the filename metadata was too noisy
- a provider failed at runtime or was unreachable

Try a cleaner filename or rerun with debug logging:

```bash
subtitler "/path/to/file.mkv" --log-level DEBUG
```

## High-Quality Sync Fails

If WhisperX fails and you still want a result quickly, try a baseline mode:

```bash
subtitler "/path/to/file.mkv" --sync-mode ffsubsync
```

If you want the default high-quality path, install the optional dependency set:

```bash
python -m pip install -e .[sync,hq-sync]
```

## Existing Files Are Skipped

Use:

```bash
subtitler "/path/to/file-or-folder" --overwrite
```

## Processing Feels Slow

The slowest step is usually WhisperX, especially on first run. GPU is preferred automatically unless you disabled it with `--no-gpu`.