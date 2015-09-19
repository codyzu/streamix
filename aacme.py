import json
import logging
import logging.config
import pathlib
import os
import pexpect
import yaml
import io

__author__ = 'cody'

# http://ffmpeg.org/ffmpeg.html#Advanced-options
# https://trac.ffmpeg.org/wiki/How%20to%20use%20-map%20option

# global variables
cfg = {}
logger = logging.root


def configure_logging(logging_cfg):
    logging.config.dictConfig(logging_cfg)


def load_config(cfg_file):
    return yaml.load(cfg_file)


def collect_canditate_files():
    """Scan the directories for all matchig files"""
    directories = [pathlib.Path(d) for d in cfg.get("directories", [])]
    globs = ["*.{0}".format(e) for e in cfg.get("extensions", ["avi"])]

    matching_files = []
    for directory in directories:
        logging.info("Searching directory: {0}".format(directory))
        for glob in globs:
            matching_files.extend(directory.rglob(glob))

    return matching_files


class FileProcessor(object):
    """Determines if a file should be processed and builds the ffmpeg command to process the file"""

    def __init__(self, file_path: pathlib.Path, cfg: dict):
        self.file_path = file_path
        self.streams = []
        self.cfg = cfg

    def process(self) -> str:
        """Read the file streams and build the ffmpeg command to transform the file (if required)
        """
        file_info = self.read_file_info()
        self.streams = file_info.get("streams", [])
        target_audio_stream = self._find_new_first_audio()
        new_stream_order = self._create_new_stream_order(target_audio_stream)

        # stop now if there is nothing to change
        if new_stream_order is None:
            return

        return self._build_ffmpeg_params(new_stream_order, target_audio_stream)

    def read_file_info(self):
        ffprobe_cmd = "ffprobe -v quiet -print_format json -show_format -show_streams {0}".format(self.file_path)

        ffprobe_json, code = pexpect.runu(ffprobe_cmd, timeout=30, withexitstatus=True)
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
            logger.debug("no audio stream found")
            return

        all_audio_streams = self._find(is_audio)

        if first_audio == all_audio_streams[0]:
            logger.debug("fist audio stream is already eng/aac")
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

        return "ffmpeg -i {input} {ins} {outs} {extra} {output}".format(input=str(self.file_path),
                                                                        ins=" ".join(in_params),
                                                                        outs=" ".join(out_params),
                                                                        extra=cfg.get("extra_encode_params", ""),
                                                                        output=self.temp_file_name)

    @property
    def temp_file_name(self):
        return self.file_path.with_suffix(".tmp{0}".format(self.file_path.suffix))


class FfmpegRunner:
    def __init__(self, ffmpeg_command: str, file_processor: FileProcessor):
        self.ffmpeg_command = ffmpeg_command
        self.file_processor = file_processor

    def run(self):
        timeout_sec = cfg.get("encode_timeout_mins", None)
        if timeout_sec is not None:
            timeout_sec *= 60

        # stop now if dry run set
        if cfg.get("dry-run", False):
            logger.warning("Skipping (dry-run): {0}".format(self.ffmpeg_command))
            return

        logger.info("Executing: {0}".format(self.ffmpeg_command))

        try:
            output, code = pexpect.runu(self.ffmpeg_command, timeout=timeout_sec, withexitstatus=True)
        except Exception as e:
            logger.exception("Failed to encode file: {0}".format(self.file_processor.file_path))

            # delete any temp file
            if self.file_processor.temp_file_name.is_file():
                logger.warning("Cleaning up file: {0}".format(self.file_processor.temp_file_name))
                os.remove(str(self.file_processor.temp_file_name))
        else:
            if code != 0:
                logger.error(output)
                return
            else:
                logger.debug(output)

            os.rename(str(self.file_processor.temp_file_name), str(self.file_processor.file_path))
            logger.info("Successfully re-encoded: {0}".format(self.file_processor.file_path))


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


# main logic
with io.open("config.yml") as cfg_file:
    cfg.update(load_config(cfg_file))

if "logging" not in cfg:
    print("No logging configuration found")
else:
    configure_logging(cfg["logging"])

video_files = collect_canditate_files()

logging.root.debug("Checking {0} files".format(len(video_files)))

ffmppeg_runners = []
for v in video_files:
    processor = FileProcessor(v, cfg)
    cmd = processor.process()
    if cmd is not None:
        ffmppeg_runners.append(FfmpegRunner(cmd, processor))

logger.info("{0} files queued for processing".format(len(ffmppeg_runners)))

for r in ffmppeg_runners:
    r.run()


"""
todo: make bit rate "minbitrate"
todo: add stream priority based on codec


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
