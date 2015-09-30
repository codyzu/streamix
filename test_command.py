import helpers
import aacme
import pytest
import unittest.mock

__author__ = 'cody'


def test_command():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("dts", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2], filename="test.mkv")

    cmd =  file_processor._get_command()

    assert len(cmd) > 0

