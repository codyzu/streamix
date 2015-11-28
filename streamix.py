import json
import logging
import logging.config
import pathlib
import os
import pexpect
import yaml
import io

__version__ = "2.4"
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


class FileState:
    Ignore = "File will be ignored: extension does not match"
    Skip = "File will be skipped"
    Remap = "File will be remapped"
    Convert = "File will be converted"
    Unknown = "File does not match any given rules"


class FileProcessor(object):
    """Determines if a file should be processed and builds the ffmpeg command to process the file"""
    # SKIP = "skip"
    # REMAP = "remap"
    # CONVERT = "convert"
    # UNKNOWN = "unknown"
    # IGNORED_EXTENSION = "ignored extension"

    def __init__(self, file_path: pathlib.Path):
        self.dry_run = cfg.get("dry-run", False)
        self.extensions = cfg.get('extensions', [])
        self.safe_codecs = cfg.get('safe_codecs', [])
        self.codec_priority = cfg.get('audio_codec_priority', [])
        self.min_bit_rate = cfg.get("audio_min_bitrate", 320000)
        self.file_path = file_path

        # initialize the state to empty values
        self.raw_streams = []
        self.file_streams = FileStreams([], self.safe_codecs, self.codec_priority)
        self.state = FileState.Unknown

        # load the file info and re-initialize the state
        self.file_info = self._read_file_info()
        self._file_info_loaded()

    def _file_info_loaded(self):
        self.raw_streams = self.file_info.get("streams", [])
        self.file_streams = FileStreams(self.raw_streams, self.safe_codecs, self.codec_priority)
        self.state = self._get_file_state()

    def needs_processing(self):
        return self.state == FileState.Remap or self.state == FileState.Convert

    def print_file_header(self):
        log_level = logging.INFO if self.needs_processing() else logging.DEBUG
        header = """
********************************************************
*
* File: {filename}
*
* Action: {state}
*
********************************************************
"""
        logger.log(log_level, header.format(filename=self.file_path, state=self.state))

    def _get_command(self):
        logger.info(self.state)

        if self.state == FileState.Remap:
            return self._remap_command()

        if self.state == FileState.Convert:
            return self._convert_command()

        return None

    def _remap_command(self):
        new_stream_order = self._remap_stream_order()

        in_params = []
        for s in new_stream_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index, s in enumerate(new_stream_order):
            out_params.append("-c:{0} copy".format(s["index"]))

        return self._build_ffmpeg_command(in_params, out_params)

    def _build_ffmpeg_command(self, ins, outs):
        return ("ffmpeg -i \"{input}\" {ins} {outs} {extra} \"{output}\""
                .format(input=str(self.file_path),
                        ins=" ".join(ins),
                        outs=" ".join(outs),
                        extra=cfg.get("extra_encode_params", ""),
                        output=self.temp_file_name))

    def _remap_stream_order(self):
        new_first = self.file_streams.first_safe_eng()
        current_first = self.file_streams.first_audio()

        new_stream_order = []

        for s in self.file_streams.streams:
            # when we reach the new first audio, skip it
            if s.raw == new_first.raw:
                continue

            # when we reach the current first audio, add the new first audio, just before
            if s.raw == current_first.raw:
                new_stream_order.append(new_first.raw)

            # add the stream if it is not subs or if is english
            if not s.is_sub() or s.is_eng():
                new_stream_order.append(s.raw)

        return new_stream_order

    def _convert_command(self):
        selected_stream = self._select_stream()
        fist_audio_stream = self.file_streams.audio[0]
        new_order = []
        conversion_index = 0

        for index, s in enumerate(self.raw_streams):
            if s == fist_audio_stream.raw:
                # note the index for when we build the ffmpeg params
                conversion_index = index
                # insert the selected stream first
                new_order.append(selected_stream.raw)

            # only add streams that are not subs or are english subs
            stream = Stream.from_raw_stream(s)
            if not stream.is_sub() or stream.is_eng():
                new_order.append(s)

        in_params = []
        for s in new_order:
            in_params.append("-map 0:{0}".format(s["index"]))

        out_params = []
        for index, s in enumerate(new_order):
            if index != conversion_index:
                out_params.append("-c:{0} copy".format(index))
            else:
                bitrate = max([self.min_bit_rate, Stream(s, []).get_bitrate()])
                out_params.append("-c:{index} aac -b:{index} {bitrate}".format(index=index, bitrate=bitrate))

        return self._build_ffmpeg_command(in_params, out_params)

    def _select_stream(self):
        highest_priority_streams = self.file_streams.select_eng_by_priority()
        if len(highest_priority_streams) > 0:
            if len(highest_priority_streams) == 1:
                return highest_priority_streams[0]
            highest_bitrate = self.file_streams.highest_bitrate(highest_priority_streams)

            if highest_bitrate != self.file_streams.EMPTY_STREAM:
                return highest_bitrate

            return highest_priority_streams[0]

        highest_bitrate = self.file_streams.select_eng_by_bitrate()
        if highest_bitrate != self.file_streams.EMPTY_STREAM:
            return highest_bitrate

        return self.file_streams.english_audio[0]

    def _read_file_info(self):
        try:
            ffprobe_cmd = "ffprobe -v quiet -print_format json -show_format -show_streams \"{0}\"".format(
                self.file_path)

            ffprobe_json, code = pexpect.runu(ffprobe_cmd, timeout=30, withexitstatus=True)
            return json.loads(ffprobe_json)
        except Exception:
            logger.exception("Error reading file info")
            return {}

    def _get_file_state(self):
        if self.file_path.suffix.lstrip(".") not in self.extensions:
            return FileState.Ignore

        first = self.file_streams.first_audio()

        if first is None:
            return FileState.Unknown

        if first.is_eng() and first.is_safe():
            return FileState.Skip

        if not self.file_streams.has_eng():
            return FileState.Skip

        if self.file_streams.has_safe_eng():
            return FileState.Remap

        if self.file_streams.has_eng():
            return FileState.Convert

    @property
    def temp_file_name(self):
        return self.file_path.with_suffix(".tmp{0}".format(self.file_path.suffix))

    def run(self):
        timeout_sec = cfg.get("encode_timeout_mins", None)
        if timeout_sec is not None:
            timeout_sec *= 60

        cmd = self._get_command()

        logger.info("Executing: {0}".format(cmd))

        # stop now if dry run set
        if self.dry_run:
            logger.warning("Execution skipping (dry-run)!")
            return

        try:
            output, code = pexpect.runu(cmd, timeout=timeout_sec, withexitstatus=True)
        except Exception as exc:
            logger.exception("Failed to encode file: {0}".format(self.file_path))

            # delete any temp file
            if self.temp_file_name.is_file():
                logger.warning("Cleaning up file: {0}".format(self.temp_file_name))
                os.remove(str(self.temp_file_name))

            raise exc
        else:
            if code != 0:
                logger.error("ffmpeg returned an error: {0}".format(output))
                return
            else:
                logger.debug(output)

            os.rename(str(self.temp_file_name), str(self.file_path))
            logger.info("Successfully re-encoded: {0}".format(self.file_path))


class Stream:
    def __init__(self, raw_stream, safe_codecs):
        self.raw = raw_stream
        self.safe_codecs = safe_codecs

    def is_safe(self):
        return self.get_codec() in self.safe_codecs

    def is_eng(self):
        return self.raw.get("tags", {}).get("language", "").lower() == "eng"

    def is_audio(self):
        return self.raw.get("codec_type", "").lower() == "audio"

    def get_codec(self):
        return self.raw.get("codec_name", "").lower()

    def get_bitrate(self):
        bitrate = self.raw.get("bit_rate", 0)

        try:
            return int(bitrate)
        except ValueError:
            raise Exception("Unable to parse the bitrate '{0}'".format(bitrate))

    def is_sub(self):
        return self.raw.get("codec_type", "").lower() == "subtitle"

    @classmethod
    def from_raw_stream(cls, raw_stream):
        return cls(raw_stream, [])



class FileStreams:
    EMPTY_STREAM = Stream({}, [])

    def __init__(self, raw_streams, safe_codecs, codec_priority):
        self.safe_codecs = safe_codecs
        self.codec_priority = codec_priority
        self.streams = [Stream(s, self.safe_codecs) for s in raw_streams]
        self.audio = [s for s in self.streams if s.is_audio()]
        self.english_audio = [s for s in self.audio if s.is_eng()]

    def first_audio(self):
        return next((s for s in self.audio), None)

    def has_eng(self):
        return len(self.english_audio) > 0

    def first_safe_eng(self):
        return next((s for s in self.english_audio if s.is_safe()), None)

    def has_safe_eng(self):
        return self.first_safe_eng() is not None

    def select_eng_by_priority(self):
        selected_streams = []

        for c in self.codec_priority:
            for s in self.english_audio:
                if s.get_codec() == c:
                    selected_streams.append(s)
            if len(selected_streams) > 0:
                break

        return selected_streams

    def select_eng_by_bitrate(self):
        return self.highest_bitrate(self.english_audio)

    @staticmethod
    def highest_bitrate(streams):
        """
        :param list[Stream] streams: list of streams
        """
        selected_stream = streams[0] if len(streams) > 0 else FileStreams.EMPTY_STREAM

        for s in streams:
            if s.get_bitrate() > selected_stream.get_bitrate():
                selected_stream = s

        return selected_stream


def main():
    load_config()
    configure_logging()

    try:
        video_files = collect_candidate_files()
        logging.root.info("""


********************************************************
*
* START
*
* Checking {0} files
*
********************************************************
""".format(len(video_files)))

        processors = []
        for f in video_files:
            try:
                processors.append(FileProcessor(f))
            except Exception:
                logger.exception("Error reading file: {0}".format(f))

        count = 0
        for p in processors:
            p.print_file_header()

            if p.needs_processing():
                try:
                    p.run()
                    count += 1
                except Exception:
                    logger.exception("Error processing file: {0}".format(p.file_path))

        logger.info("""
********************************************************
*
* END
*
* Processed {0} files
*
********************************************************


""".format(count))
    except Exception:
        logger.exception("FATAL ERROR")

if __name__ == "__main__":
    main()

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
