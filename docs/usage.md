# Usage

## Single File

```bash
subtitler "/path/to/movie.mkv"
```

This writes:

```text
/path/to/movie.srt
```

## Overwrite Existing Output

```bash
subtitler "/path/to/movie.mkv" --overwrite
```

## Write To Another Directory

```bash
subtitler "/path/to/videos" --output-dir "/path/to/output"
```

The relative folder structure is preserved.

## Choose Sync Mode

High-quality is the default:

```bash
subtitler "/path/to/movie.mkv"
```

Use a faster baseline sync mode:

```bash
subtitler "/path/to/movie.mkv" --sync-mode ffsubsync
```

Skip sync entirely:

```bash
subtitler "/path/to/movie.mkv" --sync-mode skip
```

## Disable GPU Preference

```bash
subtitler "/path/to/movie.mkv" --no-gpu
```

## Optional Environment Variables

```bash
export SUBTITLER_OPENSUBTITLES_API_KEY="your_api_key"
export SUBTITLER_OPENSUBTITLES_USERNAME="your_username"
export SUBTITLER_OPENSUBTITLES_PASSWORD="your_password"
export SUBTITLER_LOG_LEVEL="DEBUG"
```