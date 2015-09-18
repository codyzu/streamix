import json
import logging
import logging.config
import pathlib
import sys
import pexpect
import yaml
import io
# import click
import collections
import io
# import av

__author__ = 'cody'

cfg = {}
logger = logging.root


# http://ffmpeg.org/ffmpeg.html#Advanced-options
# https://trac.ffmpeg.org/wiki/How%20to%20use%20-map%20option


def configure_logging(logging_cfg):
    logging.config.dictConfig(logging_cfg)


def load_config(cfg_file):
    return yaml.load(cfg_file)


def get_config_value(key, default=None):
    if key in cfg:
        return cfg[key]
    return default


def get_video_paths():
    directories = [pathlib.Path(d) for d in get_config_value("directories", [])]
    globs = ["**/*.{0}".format(e) for e in get_config_value("extensions", ["avi"])]

    video_files = []
    for directory in directories:
        logging.info("Searching directory: {0}".format(directory))
        for glob in globs:
            video_files.extend(directory.glob(glob))

    return video_files


class FileProcessor(object):
    def __init__(self, file_path, cfg):
        self.file_path = file_path
        self.file_info = FileProcessor.read_file_info(file_path)
        self.streams = self.file_info.get("streams", [])
        self.audio_streams = self._find(is_audio)
        self.video_streams = self._find(is_video)
        self.cfg = cfg

    def process(self):
        target_audio_stream = self._find_new_first_audio()
        new_stream_order = self._create_new_stream_order(target_audio_stream)

        # stop now if there is nothing to change
        if new_stream_order is None:
            return

        ffmpeg_params = self._build_ffmpeg_params(new_stream_order, target_audio_stream)
        print(ffmpeg_params)

    @staticmethod
    def read_file_info(file_path):
        options = [
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams"
        ]

        child = pexpect.spawnu("ffprobe", options + [str(file_path)])
        child.expect(pexpect.EOF)
        ffprobe_json = child.before
        return json.loads(ffprobe_json)

    @staticmethod
    def _apply_filters(stream, filters):
        for f in filters:
            if not f(stream):
                return False

        return True

    def _find(self, *filters):
        return [s for s in self.streams if self._apply_filters(s, filters)]

    def _first(self, *filters):
        filtered = self._find(*filters)
        return filtered[0] if len(filtered) > 0 else None

    def _find_new_first_audio(self):
        # find first aac/eng
        stream = self._first(is_aac_audio, is_english_audio)
        if stream is not None:
            return stream

        # find first eng
        stream = self._first(is_english_audio)
        if stream is not None:
            return stream

        # first aac
        stream = self._first(is_aac_audio)
        if stream is not None:
            return stream

        # last resort, first audio
        return self._first(is_audio)

    def _create_new_stream_order(self, first_audio):
        if first_audio is None:
            logger.info("no audio stream found")
            return

        all_audio_streams = self._find(is_audio)

        if first_audio == all_audio_streams[0]:
            logger.info("fist audio stream is already eng/aac")
            return

        current_first_audio_stream = all_audio_streams[0]

        new_stream_order = []
        for s in self.streams:
            # when we reach the new first audio, skip it
            if s == first_audio:
                continue

            # when we reach the current first audio, add the new first audio, just before
            if s == current_first_audio_stream:
                new_stream_order.append(first_audio)

            # add the stream
            new_stream_order.append(s)

        return new_stream_order

    def _out_param_for_stream(self, current_stream, first_audio, index):
        if current_stream == first_audio and not is_aac_audio(first_audio):
            return "-c:{index} aac -b:{index} 320k".format(index=index)
        else:
            return "-c:{index} copy".format(index=index)


    def _build_ffmpeg_params(self, new_stream_order, first_audio):
        in_params = []
        for s in new_stream_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index, s in enumerate(new_stream_order):
            out_params.append(self._out_param_for_stream(s, first_audio, index))

        return "ffmpeg -strict experimental {ins} {outs}".format(ins=" ".join(in_params),outs= " ".join(out_params))




        


# Stream filters
def is_aac_audio(stream):
    if not is_audio(stream):
        return False

    if stream.get("codec_name", "").lower() == "aac":
        return True

    return False


def is_english_audio(stream):
    if not is_audio(stream):
        return False

    if stream.get("tags", {}).get("language", "").lower() == "eng":
        return True

    return False


def is_video(stream):
    return stream.get("codec_type", "").lower() == "video"


def is_audio(stream):
    return stream.get("codec_type", "").lower() == "audio"


def is_not(filter):
    return lambda s: not filter(s)




with io.open("config.yml") as cfg_file:
    cfg.update(load_config(cfg_file))

if "logging" not in cfg:
    # click.secho("No logging configuration found", fg="red")
    print("No logging configuration found")
else:
    configure_logging(cfg["logging"])

video_files = get_video_paths()

logging.root.info("Found {0} files to check".format(len(video_files)))

for v in video_files:
    processor = FileProcessor(v, cfg)
    processor.process()


"""
To review the logic: if 1st audio stream aac, then do nothing
if another audio stream is aac, move it to the first
if its english aac
when I say move, I will call ffmpeg with "map" parameters to remap the streams
then finally, if another english stream exists, re-encode to aac.
if no english streams found, do nothing

I need a way to change the type of conversion as well...let me give me the defaul
ffmpeg -i input.wav -strict experimental -c:a aac -b:a 320k output.m4a
ok, I'll make the parameters configurable through the cfg file
This default I use for aac conversation
-strict experimental -c:a aac -b:a 240k
320 i mean
-strict experimental -c:a aac -b:a 320k
"""
