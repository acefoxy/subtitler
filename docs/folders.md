# Folder Processing

Point `subtitler` at a folder and it walks the directory tree recursively.

```bash
subtitler "/path/to/media-library"
```

## What It Picks Up

The scanner looks for supported video files such as:

- `.mp4`
- `.mkv`
- `.avi`
- `.mov`
- `.webm`

## Output Behavior

Without `--output-dir`, subtitles are written next to the original file:

- `Movies/Film.mp4` -> `Movies/Film.srt`
- `Series/Season 1/Episode 01.mkv` -> `Series/Season 1/Episode 01.srt`

With `--output-dir`, the relative structure is preserved:

```bash
subtitler "/media/in" --output-dir "/media/out"
```

- `/media/in/movies/a.mp4` -> `/media/out/movies/a.srt`
- `/media/in/shows/s1/e1.mkv` -> `/media/out/shows/s1/e1.srt`

## Existing Output Files

If the target `.srt` already exists, the file is skipped unless you pass `--overwrite`.