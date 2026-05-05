# Sync Strategy

## Default Mode

`subtitler` defaults to `high-quality` sync.

That means:

1. it obtains a subtitle candidate
2. it may run a baseline sync pass first
3. it refines timing with WhisperX forced alignment

GPU is preferred automatically when available.

## High-Quality Mode Is Strict

When you explicitly or implicitly run high-quality mode, WhisperX failures are treated as real failures.

That is intentional. The tool should not silently hand back a lower-quality result when you asked for the best sync path.

## Faster Alternatives

If speed matters more than alignment quality:

```bash
subtitler "/path/to/movie.mkv" --sync-mode ffsubsync
```

or:

```bash
subtitler "/path/to/movie.mkv" --sync-mode alass
```

## First Run Behavior

The first WhisperX run may download model files. That is a one-time cost per machine or environment.