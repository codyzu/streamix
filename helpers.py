import pathlib
import aacme
import pytest

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


def build_file_processor_for_streams(streams, filename=None)->aacme.FileProcessor:
    name = "file.mkv" if filename is None else filename

    aacme.load_config()

    file_processor = aacme.FileProcessor(pathlib.Path(name))
    file_processor.file_info = build_info(streams)
    file_processor._file_info_loaded()

    return file_processor
