import pytest
import aacme
import helpers

__author__ = 'cody'


def test_file_with_wrong_ext_is_ignored():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2], filename="skipped.file")

    assert file_processor.state == aacme.FileState.Ignore


def test_file_with_only_aac_stream_is_skipped():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2])

    assert file_processor.state == aacme.FileState.Skip


def test_file_with_unknown_codec_is_skipped():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("crazy codec")
    file_processor = helpers.build_file_processor_for_streams([s1, s2])

    assert file_processor.state == aacme.FileState.Skip


def test_first_audio_eng_and_safe_codec_is_skipped():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac", language="eng")
    s3 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == aacme.FileState.Skip


def test_no_eng_audio_is_skipped():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("dts")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == aacme.FileState.Skip


def test_other_stream_eng_and_safe_is_remap():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == aacme.FileState.Remap


def test_other_stream_eng_is_convert():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == aacme.FileState.Convert


def test_other_stream_eng_is_convert_uses_priority():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("pcm_dvd", language="eng")
    s4 = helpers.build_audio_stream("dts", language="eng")
    s5 = helpers.build_audio_stream("pcm_dvd", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    assert file_processor.state == aacme.FileState.Convert


def test_other_stream_eng_is_convert_uses_bitrate():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc", language="eng")
    s5 = helpers.build_audio_stream("abc", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    assert file_processor.state == aacme.FileState.Convert


