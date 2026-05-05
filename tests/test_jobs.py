from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from subtitler.jobs import build_output_path, discover_video_jobs, parse_video_metadata


class JobDiscoveryTests(unittest.TestCase):
    def test_parse_movie_metadata(self) -> None:
        metadata = parse_video_metadata(Path("The.Matrix.1999.1080p.BluRay.mkv"))

        self.assertEqual(metadata.title, "The Matrix")
        self.assertEqual(metadata.query, "The Matrix 1999")
        self.assertEqual(metadata.kind, "movie")
        self.assertEqual(metadata.year, 1999)

    def test_parse_episode_metadata(self) -> None:
        metadata = parse_video_metadata(Path("Show.Name.S02E03.720p.WEB-DL.mkv"))

        self.assertEqual(metadata.title, "Show Name")
        self.assertEqual(metadata.kind, "episode")
        self.assertEqual(metadata.season, 2)
        self.assertEqual(metadata.episode, 3)

    def test_discover_directory_jobs_preserves_relative_output_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            input_root = root / "input"
            nested = input_root / "series" / "season1"
            nested.mkdir(parents=True)
            (nested / "Show.Name.S01E01.mkv").write_text("video")
            (input_root / "ignore.txt").write_text("not a video")
            output_root = root / "output"

            jobs = discover_video_jobs(input_root, output_root)

            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].output_path, output_root / "series" / "season1" / "Show.Name.S01E01.srt")

    def test_build_output_path_defaults_to_sibling_srt(self) -> None:
        video_path = Path("/tmp/movies/The.Matrix.1999.1080p.BluRay.mkv")

        output_path = build_output_path(video_path, None, video_path)

        self.assertEqual(output_path, Path("/tmp/movies/The.Matrix.1999.1080p.BluRay.srt"))


if __name__ == "__main__":
    unittest.main()
