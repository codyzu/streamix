import helpers
import aacme
import pytest
import unittest.mock

__author__ = 'cody'


def test_remap_moves_safe_eng_to_first():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4]


def test_remap_moves_first_safe_eng_to_first():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    s5 = helpers.build_audio_stream("aac", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4, s5]


def test_convert_selects_eng():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s3


def test_convert_selects_by_priority():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("pcm_dvd", language="eng")
    s4 = helpers.build_audio_stream("dts", language="eng")
    s5 = helpers.build_audio_stream("pcm_dvd", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s4


def test_convert_uses_bitrate():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng", bitrate=1)
    s4 = helpers.build_audio_stream("abc", language="eng", bitrate=10)
    s5 = helpers.build_audio_stream("abc", language="eng", bitrate=2)
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s4


def test_convert_uses_bitrate_after_priority():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("pcm_dvd", language="eng", bitrate=1)
    s4 = helpers.build_audio_stream("dts", language="eng", bitrate=10)
    s5 = helpers.build_audio_stream("pcm_dvd", language="eng", bitrate=2)
    s6 = helpers.build_audio_stream("dts", language="eng", bitrate=100)
    s7 = helpers.build_audio_stream("pcm_dvd", language="eng", bitrate=1000)
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5, s6, s7])

    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s6


def test_remap_command_only_copies():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    cmd = file_processor._get_command()

    tokens = cmd.split()
    for i, t in enumerate(tokens):
        if t.startswith("-c"):
            # the command following the -c must be copy
            assert tokens[i+1] == "copy"


def test_remap_command_never_calls_aac():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    cmd = file_processor._get_command()

    assert "aac" not in cmd


def test_remap_command_respects_stream_order():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    stream_order = file_processor._remap_stream_order()
    cmd = file_processor._get_command()

    stream_index = 0
    tokens = cmd.split()
    for i, t in enumerate(tokens):
        if t.startswith("-map"):
            # the command following the -map should match the stream order (using the index)
            assert tokens[i+1] == "0:{0}".format(stream_order[stream_index]["index"])
            stream_index += 1


def test_convert_command_leaves_original_stream():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    cmd = file_processor._get_command()

    actual_stream_map = []
    tokens = cmd.split()
    for i, t in enumerate(tokens):
        if t.startswith("-map"):
            actual_stream_map.append(int(tokens[i+1][2:]))

    assert actual_stream_map == [0, 2, 1, 2, 3]


def test_convert_command_uses_default_bitrate_if_not_set():
    pass


def test_convert_command_uses_default_bitrate_if_lower():
    pass


def test_convert_command_uses_stream_bitrate_if_higher():
    pass
