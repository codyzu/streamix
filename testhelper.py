import io
import pathlib
import streamix
import pytest
import json

__author__ = 'cody'

@pytest.fixture
def tmp_path(tmpdir):
    return pathlib.Path(str(tmpdir))


def build_stream(codec_type, codec_name, language=None, bitrate=None):
    stream = {
        "codec_type": codec_type,
        "codec_name": codec_name
    }

    if language is not None:
        stream["tags"] = {"language": language}

    if bitrate is not None:
        stream["bit_rate"] = bitrate

    return stream


def build_video_stream():
    return build_stream(codec_type="video", codec_name="mp4")


def build_audio_stream(codec_name, language=None, bitrate=None):
    return build_stream(codec_type="audio", codec_name=codec_name, language=language, bitrate=bitrate)


def build_info(streams):
    info = {"streams": []}

    for index, s in enumerate(streams):
        s["index"] = index
        info["streams"].append(s)

    return info


def build_file_processor_for_info(info, filename=None):
    name = "file.mkv" if filename is None else filename

    streamix.load_config()

    file_processor = streamix.FileProcessor(pathlib.Path(name))
    file_processor.file_info = info
    file_processor._file_info_loaded()

    return file_processor


def build_file_processor_for_streams(streams, filename=None)->streamix.FileProcessor:
    name = "file.mkv" if filename is None else filename
    return build_file_processor_for_info(build_info(streams), filename)


def build_file_processor_for_json_file(json_file, filename=None):
    with io.open(str(json_file)) as f:
        info = json.load(f)
    return build_file_processor_for_info(info, filename)
