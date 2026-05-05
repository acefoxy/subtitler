# subtitler

`subtitler` is a command-line tool that finds online English subtitles, synchronizes them to a video, and writes a standalone `.srt` file next to the source video.

## One Command

```bash
subtitler "/path/to/video-or-folder"
```

That is the core idea. Point it at a file or a folder and let it do the rest.

## Default Behavior

- searches multiple online subtitle providers
- downloads an English subtitle candidate
- extracts audio with `ffmpeg`
- runs subtitle sync
- prefers high-quality WhisperX alignment when available
- writes a synced `.srt` file next to the source video

## Good Fit

Use `subtitler` when you want:

- a simple CLI workflow
- folder-wide batch processing
- synced `.srt` output instead of burnt-in video
- GPU-assisted WhisperX alignment when available

## Next Steps

- Read [Installation](installation.md)
- See [Usage](usage.md)
- Check [Folder Processing](folders.md)
- Read [Sync Strategy](sync.md)