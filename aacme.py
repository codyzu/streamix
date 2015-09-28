import json
import logging
import logging.config
import pathlib
import os
import pexpect
import yaml
import io
import enum

__version__ = "1.0"
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


def collect_candidate_files():
    """Scan the directories for all matchig files"""
    directories = [pathlib.Path(d) for d in cfg.get("directories", [])]

    matching_files = []
    for directory in directories:
        logging.info("Searching directory: {0}".format(directory))
        matching_files.extend(directory.rglob('*'))

    # sort the file list so it looks logical in the logs
    return sorted(matching_files)


class StreamChooser:
    def __init__(self, streams):
        self.streams = streams
        self.finder = StreamFinder(streams)
        self.codec_priority = cfg.get("audio_codec_priority", [])

    def choose(self):
        """Select the most desirable audio stream"""

        # collect the audio streams
        audio_streams = self.finder.all_audio()

        # of all the english streams, choose the best candidate (based on the priority in the config file)
        eng_streams = self.finder.find(StreamFinder.is_audio, StreamFinder.is_eng)
        s = self._choose_by_priority(eng_streams)
        if s is not None:
            return s

        # no english streams? choose the best candidate (based on the priority in the config file)
        return self._choose_by_priority(audio_streams)

    def _choose_by_priority(self, streams):
        for c in self.codec_priority:
            stream = next((s for s in streams if s.get("codec_name", "").lower() == c.lower()), None)
            if stream is not None:
                return stream

        return streams[0] if len(streams) > 0 else None


class FileState(enum.Enum):
    Ignore = 1
    Skip = 2
    Remap = 3
    Convert = 4
    Unknown = 5

class FileProcessor(object):
    """Determines if a file should be processed and builds the ffmpeg command to process the file"""
    # SKIP = "skip"
    # REMAP = "remap"
    # CONVERT = "convert"
    # UNKNOWN = "unknown"
    # IGNORED_EXTENSION = "ignored extension"

    def __init__(self, file_path: pathlib.Path):
        self.extensions = cfg.get('extensions', [])
        self.safe_codecs = cfg.get('safe_codecs', [])
        self.file_path = file_path
        self.file_info = self._read_file_info()
        self.raw_streams = self.file_info.get("streams", [])
        self.finder = StreamFinder(self.raw_streams, self.safe_codecs)
        self.streams = FileStreams(self.raw_streams, self.safe_codecs)
        self.state = self._get_file_state()

    def process(self) -> str:
        """Read the file streams and build the ffmpeg command to transform the file (if required)"""
        logger.debug("Reading: {0}".format(self.file_path))
        file_info = self._read_file_info()
        self.streams = file_info.get("streams", [])
        self.finder.streams = self.streams
        selected_stream = StreamChooser(self.streams).choose()

        # stop now if ffmpeg is not required
        if not self._requires_ffmpeg(selected_stream):
            logger.debug("no need to execute ffmpeg")
            return

        logger.debug("queued for processing")
        new_stream_order = self._create_new_stream_order(selected_stream)
        return self._build_ffmpeg_params(new_stream_order, selected_stream)

    def get_command(self):
        logger.info("File will be {0}".format(self.state))

        if self.state == FileState.Remap:
            return self._remap_command()

        if self.state == FileState.Convert:
            return self._convert_command()

    def _remap_command(self):
        new_stream_order = self._remap_stream_order()

        in_params = []
        for s in new_stream_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index, s in enumerate(new_stream_order):
            out_params.append("-c:{0} copy".format(s["index"]))

    def _build_ffmpeg_command(self, ins, outs):
        return ("ffmpeg -i \"{input}\" {ins} {outs} {extra} \"{output}\""
            .format(input=str(self.file_path),
                    ins=" ".join(ins),
                    outs=" ".join(outs),
                    extra=cfg.get("extra_encode_params", ""),
                    output=self.temp_file_name))


    def _remap_stream_order(self):
        new_first = self.streams.first_safe_eng()
        current_first = self.streams.first_audio()

        new_stream_order = []

        for s in self.streams.raw_streams:
            # when we reach the new first audio, skip it
            if s == new_first.raw:
                continue

            # when we reach the current first audio, add the new first audio, just before
            if s == current_first.raw:
                new_stream_order.append(new_first.raw)

            # add the stream
            new_stream_order.append(s)

        return new_stream_order

    def _convert_command(self):
        pass

    def _read_file_info(self):
        try:
            ffprobe_cmd = "ffprobe -v quiet -print_format json -show_format -show_streams \"{0}\"".format(self.file_path)

            ffprobe_json, code = pexpect.runu(ffprobe_cmd, timeout=30, withexitstatus=True)
            return json.loads(ffprobe_json)
        except Exception as exc:
            logger.exception("Error reading file info")
            return {}

    def _get_file_state(self):
        if self.file_path.suffix not in self.extensions:
            return FileState.Ignore

        first = self.streams.first_audio()

        if first is None:
            return FileState.Unknown

        if first.is_eng() and first.is_safe():
            return FileState.skip

        if not self.streams.has_eng():
            return FileState.skip

        if self.streams.has_safe_eng():
            return FileState.Remap

        if self.streams.has_eng():
            return FileState.Convert

    def _requires_ffmpeg(self, selected_stream):
        # if no stream was selected, it indicates no audio streams were found
        if selected_stream is None:
            logger.debug("no audio streams found")
            return False

        # if the stream is the first AND already aac, we don't need to execute ffmpeg
        if selected_stream == self.finder.find(StreamFinder.is_audio)[0] and StreamFinder.is_aac(selected_stream):
            logger.debug("the chosen stream is already the first audio stream and encoded in aac")
            return False

        return True

    def _requires_encode(self, selected_stream):
        return not self.finder.is_aac(selected_stream)

    def _create_new_stream_order(self, selected_stream):

        all_audio_streams = self.finder.find(StreamFinder.is_audio)
        will_encode = self._requires_encode(selected_stream)
        current_first_audio_stream = all_audio_streams[0]
        new_stream_order = []

        for s in self.streams:
            # when we reach the current first audio, add the new first audio, just before
            if s == current_first_audio_stream:
                new_stream_order.append(selected_stream)

            # when we reach the selected stream, skip it if we are reordering the streams
            if s == selected_stream and not will_encode:
                continue

            # add the stream
            new_stream_order.append(s)

        return new_stream_order

    def _out_param_for_stream(self, streams, selected_stream_index, index):
        # for the stream that was selected, if it is NOT aac, we will re-encode
        current_stream = streams[index]

        if index == selected_stream_index and self._requires_encode(current_stream):
            # use the larger of the min bit rate set in the config or the current bit rate
            min_bit_rate = cfg.get("audio_min_bitrate", 320000)
            current_bit_rate = int(current_stream.get("bit_rate", "0"))
            new_bit_rate = max([min_bit_rate, current_bit_rate])
            return "-c:{index} aac -b:{index} {bitrate}".format(index=index, bitrate=new_bit_rate)

        # for all other streams, just copy
        else:
            return "-c:{index} copy".format(index=index)

    def _build_ffmpeg_params(self, new_stream_order, selected_stream):
        # find the first index of the selected stream (it may exist in the order twice if we are re-encoding)
        selected_stream_index = new_stream_order.index(selected_stream)

        in_params = []
        for s in new_stream_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index in range(len(new_stream_order)):
            out_params.append(self._out_param_for_stream(new_stream_order, selected_stream_index, index))

        return ("ffmpeg -i \"{input}\" {ins} {outs} {extra} \"{output}\""
                .format(input=str(self.file_path),
                        ins=" ".join(in_params),
                        outs=" ".join(out_params),
                        extra=cfg.get("extra_encode_params", ""),
                        output=self.temp_file_name))

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


class Stream:
    def __init__(self, raw_stream, safe_codecs):
        self.raw = raw_stream
        self.safe_codecs = safe_codecs

    def is_safe(self):
        return self.get_codec() in self.safe_codecs

    # def is_aac(self):
    #     return self.stream.get("codec_name", "").lower() == "aac"

    def is_eng(self):
        return self.raw.get("tags", {}).get("language", "").lower() == "eng"

    # def is_video(self):
    #     return self.stream.get("codec_type", "").lower() == "video"

    def is_audio(self):
        return self.raw.get("codec_type", "").lower() == "audio"

    # @staticmethod
    # def is_not(f):
    #     return lambda s: not f(s)

    def get_codec(self):
        return self.raw.get("codec_type", "").lower()


class FileStreams:
    def __init__(self, streams, safe_codecs):
        self.safe_codecs = safe_codecs
        self.raw_streams = [Stream(s, self.safe_codecs) for s in streams]
        self.audio = [s for s in self.raw_streams if s.is_audio()]

    def first_audio(self):
        return next((s for s in self.audio), None)

    def has_eng(self):
        return next((s for s in self.audio if s.is_eng()), None) is not None

    def first_safe_eng(self):
        return next((s for s in self.audio if s.is_safe() and s.is_eng()), None)

    def has_safe_eng(self):
        return self.first_safe_eng() is not None



class StreamFinder:
    def __init__(self, streams, safe_codecs):
        self.safe_codecs = safe_codecs
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
    def is_english_audio(stream):
        if not StreamFinder.is_audio(stream):
            return False

        return StreamFinder.is_eng(stream)

    @staticmethod
    def is_aac(stream):
        return stream.get("codec_name", "").lower() == "aac"

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

    @staticmethod
    def get_codec(stream):
        return stream.get("codec_type", "").lower()


load_config()
configure_logging()

video_files = collect_candidate_files()
logging.root.debug("Checking {0} files".format(len(video_files)))

files = [FileProcessor(f) for f in video_files]

for

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
