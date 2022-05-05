import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from distutils.version import LooseVersion
from io import BytesIO
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool

import av                                               # av
import click                                            # click
import pkg_resources                                    # setuptools
from lxml import etree                                  # lxml
from lxml.etree import QName, SubElement                # lxml
import lxml.html                                        # lxml
import requests                                         # requests
from requests.adapters import HTTPAdapter               # requests
from requests.packages.urllib3.util.retry import Retry  # requests
from tqdm import tqdm                                   # tqdm

s = requests.Session()
retry = Retry(connect=5, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
s.mount('http://', adapter)
s.mount('https://', adapter)
get = s.get

av.logging.set_level(av.logging.PANIC)


class Stream:
    def __init__(self, stream_type, bitrate, codec, quality, base_url):
        self.stream_type = stream_type
        self.bitrate = bitrate
        self.codec = codec
        self.quality = quality
        self.base_url = base_url

    def __str__(self):
        return f"{self.quality:{' '}{'>'}{9}} Bitrate: {self.bitrate:{' '}{'>'}{8}} Codec: {self.codec}"


class Segment:
    def __init__(self, stream, seg_num):
        self.url = stream.base_url + str(seg_num)
        self.seg_num = seg_num
        self.data = BytesIO()
        self.success = False


def local_to_utc(dt):
    if time.localtime().tm_isdst:
        return dt + timedelta(seconds=time.altzone)
    else:
        return dt + timedelta(seconds=time.timezone)


def get_mpd_data(video_url):
    req = get(video_url)
    if 'dashManifestUrl\\":\\"' in req.text:
        mpd_link = req.text.split('dashManifestUrl\\":\\"')[-1].split('\\"')[0].replace("\/", "/")
    elif 'dashManifestUrl":"' in req.text:
        mpd_link = req.text.split('dashManifestUrl":"')[-1].split('"')[0].replace("\/", "/")
    else:
        doc = lxml.html.fromstring(req.content)
        form = doc.xpath('//form[@action="https://consent.youtube.com/s"]')
        if len(form) > 0:
            print("Consent check detected. Will try to pass...")
            params = form[0].xpath('.//input[@type="hidden"]')
            pars = {}
            for par in params:
                pars[par.attrib['name']] = par.attrib['value']
            s.post("https://consent.youtube.com/s", data=pars)
            return get_mpd_data(video_url)
        return None
    return get(mpd_link).text


def process_mpd(mpd_data):
    tree = etree.parse(BytesIO(mpd_data.encode()))
    root = tree.getroot()
    nsmap = {(k or "def"): v for k, v in root.nsmap.items()}
    time = root.attrib[QName(nsmap["yt"], "mpdResponseTime")]
    d_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f")
    total_seg = (
        int(root.attrib[QName(nsmap["yt"], "earliestMediaSequence")])
        + len(tree.findall(".//def:S", nsmap))
        - 1
    )
    # Float stupidity for now cause Python doesnt know how to parse this
    # TODO: Make segments actually work without these workarounds
    seg_len = int(float(root.attrib["minimumUpdatePeriod"][2:-1]))
    attribute_sets = tree.findall(".//def:Period/def:AdaptationSet", nsmap)
    v_streams = []
    a_streams = []
    for a in attribute_sets:
        stream_type = a.attrib["mimeType"].split('/')[0]
        for r in a.findall(".//def:Representation", nsmap):
            bitrate = int(r.attrib["bandwidth"])
            codec = r.attrib["codecs"]
            base_url = r.find(".//def:BaseURL", nsmap).text + "sq/"
            if stream_type == "audio":
                quality = r.attrib["audioSamplingRate"]
                a_streams.append(Stream(stream_type, bitrate, codec, quality, base_url))
            elif stream_type == "video":
                quality = f"{r.attrib['width']}x{r.attrib['height']}"
                v_streams.append(Stream(stream_type, bitrate, codec, quality, base_url))
    a_streams.sort(key=lambda x: x.bitrate, reverse=True)
    v_streams.sort(key=lambda x: x.bitrate, reverse=True)
    return a_streams, v_streams, total_seg, d_time, seg_len


def info(a, v, m, s):
    print(f"You can go back {int(m*2/3600)} hours and {int(m*2%3600/60)} minutes...")
    print(f"Download avaliable from {datetime.today() - timedelta(seconds=m*2)}")
    print("\nAudio stream ids")
    for i in range(len(a)):
        print(f"{i}:  {str(a[i])}")

    print("\nVideo stream ids")
    for i in range(len(v)):
        print(f"{i}:  {str(v[i])}")


def download_func(seg):
    while True:
        req = get(seg.url)
        if req.status_code == 200:
            break
        time.sleep(1)
    return req.content


def download(stream, seg_range, threads=1):
    segments = []
    for seg in seg_range:
        segments.append(Segment(stream, seg))

    results = ThreadPool(threads).imap(download_func, segments)
    combined_file = BytesIO()
    segs_downloaded = 0
    for res in tqdm(results, total=len(segments), unit="seg"):
        combined_file.write(res)

    return combined_file


def mux_to_file(output, aud, vid):
    # seek 0: https://github.com/PyAV-Org/PyAV/issues/508#issuecomment-488710828
    vid.seek(0)
    aud.seek(0)
    video = av.open(vid, "r")
    audio = av.open(aud, "r")
    output = av.open(output, "w")
    v_in = video.streams.video[0]
    a_in = audio.streams.audio[0]

    video_p = video.demux(v_in)
    audio_p = audio.demux(a_in)

    output_video = output.add_stream(template=v_in)
    output_audio = output.add_stream(template=a_in)

    last_pts = 0
    for packet in video_p:
        if packet.dts is None:
            continue

        packet.dts = last_pts
        packet.pts = last_pts
        last_pts += packet.duration

        packet.stream = output_video
        output.mux(packet)

    last_pts = 0
    for packet in audio_p:
        if packet.dts is None:
            continue

        packet.dts = last_pts
        packet.pts = last_pts
        last_pts += packet.duration

        packet.stream = output_audio
        output.mux(packet)

    output.close()
    audio.close()
    video.close()


def check_if_exists(output):
    if os.path.exists(output):
        yn = input(f"File '{output}' already exists. Overwrite? [y/N] ").lower()
        if yn and yn[0] == "y":
            os.remove(output)
            return True
        else:
            return False
    else:
        return True


def parse_datetime(inp, utc=True):
    formats = ["%Y-%m-%dT%H:%M", "%d.%m.%Y %H:%M", "%d.%m %H:%M", "%H:%M"]
    for fmt in formats:
        try:
            d_time = datetime.strptime(inp, fmt)
            today = datetime.today()
            if not ('d' in fmt):
                d_time = d_time.replace(year=today.year, month=today.month,day=today.day)
            if not ('Y' in fmt):
                d_time = d_time.replace(year=today.year)
            if utc:
                return d_time
            return local_to_utc(d_time)
        except ValueError:
            pass
    return -1


def parse_duration(inp):
    x = re.findall("([0-9]+[hmsHMS])", inp)
    if not x:
        try:
            number = int(inp)
        except:
            return -1
        return number
    else:
        total_seconds = 0
        for chunk in x:
            if chunk[-1] == "h":
                total_seconds += int(chunk[:-1]) * 3600
            elif chunk[-1] == "m":
                total_seconds += int(chunk[:-1]) * 60
            elif chunk[-1] == "s":
                total_seconds += int(chunk[:-1])
        return total_seconds

def check_for_update():
    # Ugly code... if you have a better idea please help
    try:
        local_version = LooseVersion(pkg_resources.get_distribution("youtube_dash_dl").version)
    except:
        return
    try:
        req = get("https://pypi.org/pypi/youtube-dash-dl/json")
        online_version = LooseVersion(json.loads(req.text)['info']['version'])
    except:
        return

    if online_version > local_version:
        print(f"Update avaliable!\nYou should probably update with 'pip install --upgrade youtube_dash_dl'\nLocal version: {local_version} | Online version: {online_version}\n")


@click.command()
@click.argument("url")
@click.option("-l", "--list-formats", is_flag=True, help="List info about stream ids")
@click.option("-af", default=0, help="Select audio stream id.")
@click.option("-vf", default=0, help="Select video stream id.")
@click.option("--utc", is_flag=True, help="Use UTC time instead of local.")
@click.option("-s", "--start", help="Start time of the download.")
@click.option("-e", "--end", help="End time of the download.")
@click.option("--download-threads", type=int, help="Set amount of download threads.")
@click.option("-d", "--duration", help="Duration of the download.")
@click.option("-o", "--output", help="Output file path.")
def main(**kwargs):
    check_for_update()

    mpd_data = get_mpd_data(kwargs["url"])
    if mpd_data is None:
        print("Error: Couldn't get MPD data!")
        return 0
    a, v, m, s, l = process_mpd(mpd_data)

    if kwargs["list_formats"]:
        info(a, v, m, s)
        return 0

    if kwargs["output"] is None:
        print("Error: Missing option '-o' / '--output'!")
        return 0

    if not kwargs["output"].endswith((".mp4", ".mkv")):
        print("Error: Unsupported output file format!")
        return 0

    start_time = (
        s - timedelta(seconds=m * l)
        if kwargs["start"] is None
        else parse_datetime(kwargs["start"], kwargs["utc"])
    )

    if start_time == -1:
        print("Error: Couldn't parse start date!")
        return 0

    if kwargs["duration"] is None and kwargs["end"] is None:
        duration = m * l
    else:
        if kwargs["duration"] is None:
            e_dtime = parse_datetime(kwargs["end"], kwargs["utc"])
            s_dtime = s if kwargs["start"] is None else parse_datetime(kwargs["start"], kwargs["utc"])
            duration = (e_dtime - s_dtime).total_seconds()
        else:
            duration =  parse_duration(kwargs["duration"])

    if duration == -1:
        print("Error: Couldn't parse duration or end date!")
        return 0

    start_segment = m - round((s - start_time).total_seconds() / l)
    if start_segment < 0:
        start_segment = 0

    end_segment = start_segment + round(duration / l)
    if end_segment > m:
        print("Error: You are requesting segments that dont exist yet!")
        return 0

    download_threads = cpu_count() if kwargs['download_threads'] is None else kwargs['download_threads']
    if download_threads > 4:
        # This is here until we figure out how to use youtube cookies as to not get blocked
        download_threads = 4

    
    if check_if_exists(kwargs["output"]):
        print("Downloading segments...")
        v_data = download(v[kwargs["vf"]], range(start_segment, end_segment), download_threads)
        a_data = download(a[kwargs["af"]], range(start_segment, end_segment), download_threads)
        print("Muxing into file...")
        mux_to_file(kwargs["output"], a_data, v_data)


if __name__ == "__main__":
    main()
