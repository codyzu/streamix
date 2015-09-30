import pytest
import aacme
import helpers

__author__ = 'cody'


def test_file_with_wrong_ext_is_ignored():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2], filename="skipped.file")

    assert file_processor.state == aacme.FileState.Ignore
