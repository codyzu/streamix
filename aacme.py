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
    def __init__(self, file_path):
        self.file_path = file_path
        self.file_info = FileProcessor.read_file_info(file_path)
        self.streams = self.file_info.get("streams", [])
        self.audio_streams = self.find(is_audio)
        self.video_streams = self.find(is_video)

    @staticmethod
    def read_file_info(file_path):
        options = [
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams"
        ]

        child = pexpect.spawnu("ffprobe", options + [str(file_path)], logfile=sys.stdout)
        child.expect(pexpect.EOF)
        ffprobe_json = child.before
        return json.loads(ffprobe_json)

    @staticmethod
    def _apply_filters(stream, filters):
        for f in filters:
            if not f(stream):
                return False

        return True

    def find(self, *filters):
        return [s for s in self.streams if self._apply_filters(s, filters)]

    def first(self, *filters):
        return next(self.find(*filters), None)

    def find_new_first_audio(self):
        # no audio streams
        if len(self.audio_streams) == 0:
            return None

        # first audio stream is aac/eng
        if is_english_audio(self.audio_streams[0]) and is_aac_audio(self.audio_streams[0]):
            logger.info("first stream is eng/aac")
            return

        # find first aac/eng
        stream = self.first(is_aac_audio, is_english_audio)
        if stream is not None:
            return stream

        # find first eng
        stream = self.first(is_english_audio)
        if stream is not None:
            return stream

        # first aac
        stream = self.first(is_aac_audio)
        if stream is not None:
            return stream

        # last resort, first audio
        return self.first(is_audio)

    def build_ffmpeg_args(self, first_audio):
        if first_audio is None:
            logger.info("no audio stream found")
            return

        all_audio_streams = self.find(is_audio)

        if first_audio == all_audio_streams[0]:
            logger.info("fist audio stream is already eng/aac")
            return

        


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


def build_ffmpeg_args(video_info, first_audio):
    # http://ffmpeg.org/ffmpeg.html#Advanced-options
    # https://trac.ffmpeg.org/wiki/How%20to%20use%20-map%20option

    # build output map

    # copy all video streams
    video_streams = [s for s in video_info.get("streams", []) if is_video(s)]

    pass


with io.open("config.yml") as cfg_file:
    cfg.update(load_config(cfg_file))

if "logging" not in cfg:
    # click.secho("No logging configuration found", fg="red")
    print("No logging configuration found")
else:
    configure_logging(cfg["logging"])

logging.getLogger(__name__).info("Hello")

video_files = get_video_paths()

logging.root.info("Found {0} files to check".format(len(video_files)))

# audio_streams = get_audio_streams_for_file(video_files[0])
#
# print(audio_streams)
# print([a["codec_name"] for a in audio_streams])


video_info = get_video_info(video_files[0])

print(video_info)

# collect audio streams
audio_streams = [s for s in video_info.get("streams", []) if is_audio(s)]










# container = av.open("/home/cody/Downloads/The Intouchables 2011 720p BluRay x264 French AAC - Ozlem/The Intouchables 2011 720p BluRay x264 French AAC - Ozlem.mp4")
#
#
# for stream in container.streams:
#     if isinstance(stream, av.audio.stream.AudioStream):
#         print(stream.format)
#
# print("hello")


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
