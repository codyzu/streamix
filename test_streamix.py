import json
import testhelper
import streamix
import io
import unittest.mock

__author__ = 'cody'


#########################################
#
# Test processor state
#
#########################################

def test_file_with_wrong_ext_is_ignored():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2], filename="skipped.file")

    assert file_processor.state == streamix.FileState.Ignore


def test_file_with_only_aac_stream_is_skipped():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2])

    assert file_processor.state == streamix.FileState.Skip


def test_file_with_unknown_codec_is_skipped():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("crazy codec")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2])

    assert file_processor.state == streamix.FileState.Skip


def test_first_audio_eng_and_safe_codec_is_skipped():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac", language="eng")
    s3 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == streamix.FileState.Skip


def test_no_eng_audio_is_skipped():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("dts")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == streamix.FileState.Skip


def test_other_stream_eng_and_safe_is_remap():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == streamix.FileState.Remap


def test_other_stream_eng_is_convert():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3])

    assert file_processor.state == streamix.FileState.Convert


def test_other_stream_eng_is_convert_uses_priority():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("pcm_dvd", language="eng")
    s4 = testhelper.build_audio_stream("dts", language="eng")
    s5 = testhelper.build_audio_stream("pcm_dvd", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    assert file_processor.state == streamix.FileState.Convert


def test_other_stream_eng_is_convert_uses_bitrate():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    s4 = testhelper.build_audio_stream("abc", language="eng")
    s5 = testhelper.build_audio_stream("abc", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    assert file_processor.state == streamix.FileState.Convert


#########################################
#
# Test remap stream order
#
#########################################

def test_remap_moves_safe_eng_to_first():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    s4 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4]


def test_remap_moves_first_safe_eng_to_first():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    s4 = testhelper.build_audio_stream("aac")
    s5 = testhelper.build_audio_stream("aac", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
    stream_order = file_processor._remap_stream_order()

    assert stream_order == [s1, s3, s2, s4, s5]


#########################################
#
# Test convert stream selection
#
#########################################

def test_convert_selects_eng():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s3


def test_convert_selects_by_priority():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("pcm_dvd", language="eng")
    s4 = testhelper.build_audio_stream("dts", language="eng")
    s5 = testhelper.build_audio_stream("pcm_dvd", language="eng")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s4


def test_convert_uses_bitrate():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng", bitrate=1)
    s4 = testhelper.build_audio_stream("abc", language="eng", bitrate=10)
    s5 = testhelper.build_audio_stream("abc", language="eng", bitrate=2)
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s4


def test_convert_uses_bitrate_after_priority():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("pcm_dvd", language="eng", bitrate=1)
    s4 = testhelper.build_audio_stream("dts", language="eng", bitrate=10)
    s5 = testhelper.build_audio_stream("pcm_dvd", language="eng", bitrate=2)
    s6 = testhelper.build_audio_stream("dts", language="eng", bitrate=100)
    s7 = testhelper.build_audio_stream("pcm_dvd", language="eng", bitrate=1000)
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4, s5, s6, s7])

    # noinspection PyProtectedMember
    selected_stream = file_processor._select_stream().raw

    assert selected_stream == s6


#########################################
#
# Test remap command
#
#########################################

def test_remap_command_only_copies():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    s4 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    for i, t in enumerate(tokens):
        if t.startswith("-c"):
            # the command following the -c must be copy
            assert tokens[i+1] == "copy"


def test_remap_command_never_calls_aac():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    s4 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    assert "aac" not in cmd


def test_remap_command_respects_stream_order():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("aac", language="eng")
    s4 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

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

def test_convert_command_leaves_original_stream_map_params():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    actual_stream_map = [int(tokens[i+1][2:]) for i, t in enumerate(tokens) if t.startswith("-map")]

    assert actual_stream_map == [0, 2, 1, 2, 3]


def test_convert_command_maps_streams_in_codec_params():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    actual_codec_map = [int(t[3:]) for t in tokens if t.startswith("-c:")]

    # expect the codec map to be sequential
    assert actual_codec_map == [0, 1, 2, 3, 4]


def test_convert_command_uses_default_bitrate_if_not_set():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng")
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    encode_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[encode_token_index + 1] == str(320000)


def test_convert_command_uses_default_bitrate_if_lower():
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng", bitrate=100)
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    encode_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[encode_token_index + 1] == str(320000)


def test_convert_command_uses_stream_bitrate_if_higher():
    expected_bitrate = 480000
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng", bitrate=expected_bitrate)
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    bitrate_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[bitrate_token_index + 1] == str(expected_bitrate)


def test_convert_command_uses_correct_bitrate_if_file_has_string_bitrate():
    expected_bitrate = 480000
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    s3 = testhelper.build_audio_stream("abc", language="eng", bitrate=str(expected_bitrate))
    s4 = testhelper.build_audio_stream("abc")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2, s3, s4])

    # noinspection PyProtectedMember
    cmd = file_processor._get_command()

    tokens = cmd.split()
    encode_token_index = next(i for i, t in enumerate(tokens) if t.startswith("-b:"))
    assert tokens[encode_token_index + 1] == str(expected_bitrate)


#########################################
#
# Test convert stream selection
#
#########################################

def test_stream_reads_bitrate():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = streamix.Stream(streams[1], [])

    assert stream.get_bitrate() == 768000


def test_stream_not_in_eng():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = streamix.Stream(streams[1], [])

    assert stream.is_eng() == False


def test_stream_is_eng():
    with io.open("test-info_en.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = streamix.Stream(streams[0], [])

    assert stream.is_eng() == True


def test_stream_get_codec():
    with io.open("test-info_fr.json") as f:
        info_json = json.load(f)

    streams = info_json["streams"]

    stream = streamix.Stream(streams[1], [])

    assert stream.get_codec() == "dca"


#########################################
#
# Test run
#
#########################################

@unittest.mock.patch("streamix.os.rename")
def test_subprocess_call(mock_rename):
    s1 = testhelper.build_video_stream()
    s2 = testhelper.build_audio_stream("aac")
    file_processor = testhelper.build_file_processor_for_streams([s1, s2])

    with unittest.mock.patch("streamix.logger") as mock_logger:
        with unittest.mock.patch("streamix.FileProcessor._get_command") as mock_get_command:
            mock_get_command.return_value = "ls -la"
            file_processor.run()

        assert mock_logger.info.called
        info_args = mock_logger.info.call_args
        assert info_args[0][0].startswith("Successfully re-encoded:")


def test_command_with_client_json():
    file_processor = testhelper.build_file_processor_for_json_file("test-info_client.json")

    with unittest.mock.patch("streamix.os.rename"):
        with unittest.mock.patch("streamix.pexpect.runu") as mock_run:
            mock_run.return_value = "", 0

            with unittest.mock.patch("streamix.logger") as mock_logger:
                file_processor.run()

    info_messages = [p[0] for p, _ in mock_logger.info.call_args_list]
    executing_token = "Executing: "
    execution_message = next(m for m in info_messages if m.startswith(executing_token))
    ffmpeg_command = execution_message[len(executing_token):]

    assert ffmpeg_command == 'ffmpeg -i "file.mkv" -metadata title="file.mkv" -map 0:0 -map 0:1 -map 0:1 -c:0 copy -c:1 aac -b:1 1536000 -c:2 copy -strict experimental "file.tmp.mkv"'
