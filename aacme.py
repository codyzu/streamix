import json
import logging
import logging.config
import pathlib
import sys
import pexpect
import yaml
import click
import collections
import io
import av

__author__ = 'cody'

cfg = {}


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


def get_video_info(path):
    options = [
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams"
    ]

    child = pexpect.spawnu("ffprobe", options + [str(path)], logfile=sys.stdout)
    child.expect(pexpect.EOF)
    ffprobe_json = child.before
    return json.loads(ffprobe_json)


def get_audio_streams_for_file(path):
    video_info = get_video_info(path)

    audio_streams = []

    if "streams" in video_info:
        audio_streams = [s for s in video_info["streams"] if s["codec_type"] == "audio"]

    return audio_streams


with click.open_file("config.yml") as cfg_file:
    cfg.update(load_config(cfg_file))

if "logging" not in cfg:
    click.secho("No logging configuration found", fg="red")
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

# 1) first audio stream is aac


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