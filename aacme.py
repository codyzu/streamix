import json
import logging
import logging.config
import pathlib
import os
import pexpect
import yaml
import io

__version__ = "0.3"
__author__ = 'cody'

# http://ffmpeg.org/ffmpeg.html#Advanced-options
# https://trac.ffmpeg.org/wiki/How%20to%20use%20-map%20option

# global variables
cfg = {}
logger = logging.root


def load_config():
    try:
        with io.open("config.yml") as cfg_file:
            cfg.update(yaml.load(cfg_file))
    except Exception as e:
        print("Failed to load config: {0}".format(str(e)))


def configure_logging():
    if "logging" not in cfg:
        print("No logging configuration found")
        exit()
    else:
        try:
            logging.config.dictConfig(cfg["logging"])
        except Exception as e:
            print("Failed to configre logging: {0}".format(str(e)))
            exit()


def collect_canditate_files():
    """Scan the directories for all matchig files"""
    directories = [pathlib.Path(d) for d in cfg.get("directories", [])]
    globs = ["*.{0}".format(e) for e in cfg.get("extensions", [])]

    matching_files = []
    for directory in directories:
        logging.info("Searching directory: {0}".format(directory))
        for glob in globs:
            matching_files.extend(directory.rglob(glob))

    # sort the file list so it looks logical in the logs
    return sorted(matching_files)


class StreamChooser:
    def __init__(self, streams):
        self.streams = streams
        self.finder = StreamFinder(streams)
        self.codec_priority = cfg.get("audio_codec_priority", [])

    def choose(self):
        # collect the audio streams
        audio_streams = self.finder.all_audio()

        # search for the highest priority english stream
        eng_streams = self.finder.find(StreamFinder.is_audio, StreamFinder.is_eng)
        s = self._choose_by_priority(eng_streams)
        if s is not None:
            return s

        # search for the highest priority stream
        return self._choose_by_priority(audio_streams)

    def _choose_by_priority(self, streams):
        for c in self.codec_priority:
            stream = next((s for s in streams if s.get("codec_name", "").lower() == c.lower()), None)
            if stream is not None:
                return stream

        return streams[0] if len(streams) > 0 else None


class FileProcessor(object):
    """Determines if a file should be processed and builds the ffmpeg command to process the file"""

    def __init__(self, file_path: pathlib.Path):
        self.file_path = file_path
        self.streams = []
        self.finder = StreamFinder([])

    def process(self) -> str:
        """Read the file streams and build the ffmpeg command to transform the file (if required)
        """
        logger.debug("Reading: {0}".format(self.file_path))
        file_info = self.read_file_info()
        self.streams = file_info.get("streams", [])
        self.finder.streams = self.streams
        target_audio_stream = StreamChooser(self.streams).choose()
        new_stream_order = self._create_new_stream_order(target_audio_stream)

        # stop now if there is nothing to change
        if new_stream_order is None:
            return

        logger.debug("Queued for processing")
        return self._build_ffmpeg_params(new_stream_order, target_audio_stream)

    def read_file_info(self):
        ffprobe_cmd = "ffprobe -v quiet -print_format json -show_format -show_streams \"{0}\"".format(self.file_path)

        ffprobe_json, code = pexpect.runu(ffprobe_cmd, timeout=30, withexitstatus=True)
        return json.loads(ffprobe_json)

    def _create_new_stream_order(self, first_audio):
        if first_audio is None:
            logger.debug("no audio stream found")
            return

        all_audio_streams = self.finder.find(StreamFinder.is_audio)

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
        if current_stream == first_audio and not StreamFinder.is_aac_audio(first_audio):
            min_bit_rate = cfg.get("audio_min_bitrate", 320000)
            current_bit_rate = int(first_audio.get("bit_rate", "0"))
            new_bit_rate = max([min_bit_rate, current_bit_rate])
            return "-c:{index} aac -b:{index} {bitrate}".format(index=index, bitrate=new_bit_rate)
        else:
            return "-c:{index} copy".format(index=index)

    def _build_ffmpeg_params(self, new_stream_order, first_audio):
        in_params = []
        for s in new_stream_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index, s in enumerate(new_stream_order):
            out_params.append(self._out_param_for_stream(s, first_audio, index))

        return "ffmpeg -i \"{input}\" {ins} {outs} {extra} \"{output}\"".format(input=str(self.file_path),
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


class StreamFinder:
    def __init__(self, streams):
        self.streams = streams

    def find(self, *filters):
        return [s for s in self.streams if self._apply_filters(s, filters)]

    def first(self, *filters):
        filtered = self.find(*filters)
        return filtered[0] if len(filtered) > 0 else None

    def all_audio(self):
        return self.find(StreamFinder.is_audio)

    def first_audio(self):
        all_audio_streams = self.all_audio()
        return all_audio_streams[0] if len(all_audio_streams) > 0 else None

    @staticmethod
    def _apply_filters(stream, filters):
        for f in filters:
            if not f(stream):
                return False
        return True

    # Stream filters
    @staticmethod
    def is_aac_audio(stream):
        if not StreamFinder.is_audio(stream):
            return False

        if stream.get("codec_name", "").lower() == "aac":
            return True

        return False

    @staticmethod
    def is_english_audio(stream):
        if not StreamFinder.is_audio(stream):
            return False

        return StreamFinder.is_eng(stream)

    @staticmethod
    def is_eng(stream):
        return stream.get("tags", {}).get("language", "").lower() == "eng"

    @staticmethod
    def is_video(stream):
        return stream.get("codec_type", "").lower() == "video"

    @staticmethod
    def is_audio(stream):
        return stream.get("codec_type", "").lower() == "audio"

    @staticmethod
    def is_not(f):
        return lambda s: not f(s)


load_config()
configure_logging()

video_files = collect_canditate_files()

logging.root.debug("Checking {0} files".format(len(video_files)))

ffmppeg_runners = []
for v in video_files:
    processor = FileProcessor(v)
    cmd = processor.process()
    if cmd is not None:
        ffmppeg_runners.append(FfmpegRunner(cmd, processor))

logger.info("{0} files queued for processing".format(len(ffmppeg_runners)))

for r in ffmppeg_runners:
    r.run()


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

make bit rate "minbitrate"
add stream priority based on codec

"""
