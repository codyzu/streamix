import json
import helpers
import aacme
import io

__author__ = 'cody'


#########################################
#
# Test processor state
#
#########################################

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


#########################################
#
# Test remap stream order
#
#########################################

def test_remap_moves_safe_eng_to_first():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4]


def test_remap_moves_first_safe_eng_to_first():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    s5 = helpers.build_audio_stream("aac", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4, s5]


#########################################
#
# Test convert stream selection
#
#########################################

def test_convert_selects_eng():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s3


def test_convert_selects_by_priority():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("pcm_dvd", language="eng")
    s4 = helpers.build_audio_stream("dts", language="eng")
    s5 = helpers.build_audio_stream("pcm_dvd", language="eng")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s4


def test_convert_uses_bitrate():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng", bitrate=1)
    s4 = helpers.build_audio_stream("abc", language="eng", bitrate=10)
    s5 = helpers.build_audio_stream("abc", language="eng", bitrate=2)
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
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

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s6


#########################################
#
# Test remap command
#
#########################################

def test_remap_command_only_copies():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
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

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    assert "aac" not in cmd


def test_remap_command_respects_stream_order():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("aac", language="eng")
    s4 = helpers.build_audio_stream("aac")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    stream_order = file_processor._remap_stream_order()
    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    stream_index = 0
    tokens = cmd.split()
    for i, t in enumerate(tokens):
        if t.startswith("-map"):
            # the command following the -map should match the stream order (using the index)
            assert tokens[i+1] == "0:{0}".format(stream_order[stream_index]["index"])
            stream_index += 1


#########################################
#
# Test convert command
#
#########################################

def test_convert_command_leaves_original_stream():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    actual_stream_map = [int(tokens[i+1][2:]) for i, t in enumerate(tokens) if t.startswith("-map")]

    assert actual_stream_map == [0, 2, 1, 2, 3]


def test_convert_command_uses_default_bitrate_if_not_set():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng")
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    encode_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[encode_token_index + 1] == str(320000)


def test_convert_command_uses_default_bitrate_if_lower():
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng", bitrate=100)
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    encode_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[encode_token_index + 1] == str(320000)


def test_convert_command_uses_stream_bitrate_if_higher():
    expected_bitrate = 480000
    s1 = helpers.build_video_stream()
    s2 = helpers.build_audio_stream("aac")
    s3 = helpers.build_audio_stream("abc", language="eng", bitrate=expected_bitrate)
    s4 = helpers.build_audio_stream("abc")
    file_processor = helpers.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    bitrate_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[bitrate_token_index + 1] == str(expected_bitrate)


#########################################
#
# Test convert stream selection
#
#########################################

def test_stream_reads_bitrate():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = aacme.Stream(streams[1], [])

    assert stream.get_bitrate() == "768000"


def test_stream_not_in_eng():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = aacme.Stream(streams[1], [])

    assert stream.is_eng() == False


def test_stream_is_eng():
    with io.open("test-info_en.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = aacme.Stream(streams[0], [])

    assert stream.is_eng() == True


def test_stream_get_codec():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = aacme.Stream(streams[1], [])

    assert stream.get_codec() == "dca"
