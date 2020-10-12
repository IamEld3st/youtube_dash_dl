from requests import get, Session # requests
import sys #
from bs4 import BeautifulSoup # beautifulsoup4 / lxml
import urllib.parse #
import os #
from mpegdash.parser import MPEGDASHParser # mpegdash
from datetime import datetime, timezone
from tqdm import tqdm # tqdm
import platform
import shutil
import re
import argparse
import asyncio
import aiohttp
import random
import subprocess
import multiprocessing

async def fetch(session, url, i, folder, pbar, sem):
    async with sem, session.get(url) as response:
        resp = await response.read()
        with open(os.path.join(folder, f"{str(i)}.ts"), "wb") as f:
            f.write(resp)
        pbar.update()

async def get_segments(total_segments, video_base, audio_base, tempdir):
    pbar = tqdm(total=2*len(total_segments), desc="Downloading segments")
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(12)
        tasks = []
        for i in total_segments:
            tasks.append(asyncio.create_task(fetch(session, f"{video_base}/{i}", i, os.path.join(tempdir, "temp-video"), pbar, sem)))
            tasks.append(asyncio.create_task(fetch(session, f"{audio_base}/{i}", i, os.path.join(tempdir, "temp-audio"), pbar, sem)))
        await asyncio.wait(tasks)
    pbar.close()

def process_segments(params):
    ffmpeg_executable = params[0]
    tempdir = params[1]
    i = params[2]
    cmd_avseg = [
        ffmpeg_executable,
        "-y",
        "-i",
        f"{os.path.join(tempdir, 'temp-video', f'{i}.ts')}",
        "-i",
        f"{os.path.join(tempdir, 'temp-audio', f'{i}.ts')}",
        "-c",
        "copy",
        f"{os.path.join(tempdir, 'avseg')}/{i}.ts"
    ]
    proc = subprocess.Popen(cmd_avseg, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    proc.communicate()

def get_mpd_data(video_url):
    with Session() as s:
        raw_page = s.get(video_url)
        soup = BeautifulSoup(raw_page.text, 'lxml')
        script_obj = str(soup(id="player-wrap")[0].find_all("script")[1]).split("\\\"")
        for i in range(len(script_obj)):
            if script_obj[i] == "dashManifestUrl":
                mpd_url = script_obj[i+2]
                break
        mpd_url = urllib.parse.unquote(mpd_url).replace("\/", "/")
        mpd_file_content = s.get(mpd_url)
    return mpd_file_content.text

def get_best_representation(mpd_data):
    best_video = None
    best_video_res = 0
    best_audio = None
    best_audio_sample = 0
    mpd = MPEGDASHParser.parse(mpd_data)
    for period in mpd.periods:
        for adaptationset in period.adaptation_sets:
            for rep in adaptationset.representations:
                if rep.height == None:
                    if int(rep.audio_sampling_rate) >= best_audio_sample:
                        best_audio = rep
                        best_audio_sample = int(rep.audio_sampling_rate)
                else:
                    if int(rep.height) >= best_video_res:
                        best_video = rep
                        best_video_res = int(rep.height)
    return best_video, best_audio

def parse_datetime(s):
    def try_strptime(s, fmt):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            return None
    dt = try_strptime(s, '%H:%M')
    if dt:
        today = datetime.today()
        return dt.replace(year=today.year, month=today.month, day=today.day)
    dt = try_strptime(s, '%H:%M:%S')
    if dt:
        today = datetime.today()
        return dt.replace(year=today.year, month=today.month, day=today.day)
    dt = try_strptime(s, '%d.%m %H:%M')
    if dt:
        return dt.replace(year=datetime.today().year)
    dt = try_strptime(s, '%d.%m.%Y %H:%M')
    if dt:
        return dt
    dt = try_strptime(s, '%d.%m %H:%M:%S')
    if dt:
        return dt.replace(year=datetime.today().year)
    dt = try_strptime(s, '%d.%m.%Y %H:%M:%S')
    if dt:
        return dt
    dt = try_strptime(s, '%Y-%m-%dT%H:%M:%S')
    if dt:
        return dt
    return None

def parse_duration(s):
    m = re.match(r'^((?P<h>\d+)h)?((?P<m>\d+)m)?((?P<s>\d+)s)?$', s)
    if not m:
        return None
    h, m, s = m.groupdict().values()
    if not h and not m and not s:
        return None
    secs = 0
    if h:
        secs += int(h) * 3600
    if m:
        secs += int(m) * 60
    if s:
        secs += int(s)
    return secs

def main(ffmpeg_executable):
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', metavar='OUTPUT_FILE', action='store', help='The output filename')
    parser.add_argument('-s', '--start', metavar='START_TIME', action='store', help='The start time (possible formats = "12:34", "12:34:56", "7.8.2009 12:34:56", "2009-08-07T12:34:56")')
    parser.add_argument('-e', '--end', metavar='END_TIME', action='store', help='The end time (same format as start time)')
    parser.add_argument('-d', '--duration', action='store', help='The duration (possible formats = "12h34m56s", "12m34s", "123s", "123m", "123h", ...)')
    parser.add_argument('-u', '--utc', action='store_true', help='Use UTC instead of local time for start and end time', default=False)
    parser.add_argument('-y', '--overwrite', action='store_true', help='Overwrite file without asking', default=False)
    parser.add_argument('url', metavar='URL', action='store', help='The URL of the YouTube stream')
    args = parser.parse_args()
    url = args.url
    output_path = args.output
    start_time = None
    duration_secs = None

    def arg_fail(message):
        print(message, file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    if args.start:
        start_time = parse_datetime(args.start)
        if not start_time:
            arg_fail('Invalid start time format')
        start_time = start_time.replace(tzinfo=timezone.utc if args.utc else None).astimezone()

    if args.duration and args.end:
        arg_fail('Specify end time or duration, not both')

    if args.duration:
        duration_secs = parse_duration(args.duration)
        if not duration_secs:
            arg_fail('Invalid duration format')
        if duration_secs == 0:
            arg_fail('Duration cannot be 0')

    if args.end:
        end_time = parse_datetime(args.end)
        if not end_time:
            arg_fail('Invalid end time format!')
        end_time = end_time.replace(tzinfo=timezone.utc if args.utc else None).astimezone()
        duration_secs = (end_time - start_time).total_seconds()
        if duration_secs == 0:
            arg_fail('Duration cannot be 0')

    data = get_mpd_data(url)
    video, audio = get_best_representation(data)

    video_base = video.base_urls[0].base_url_value + "/".join(video.segment_lists[0].segment_urls[0].media.split('/')[:-3])
    audio_base = audio.base_urls[0].base_url_value + "/".join(audio.segment_lists[0].segment_urls[0].media.split('/')[:-3])
    max_seg = int(video.segment_lists[0].segment_urls[-1].media.split('/')[-3])

    if not output_path:
        print(f"You can go back {int(max_seg*2/60/60)} hours and {int(max_seg*2/60%60)} minutes back...")
        exit(0)

    if os.path.exists(output_path):
        if args.overwrite:
            os.remove(output_path)
        else:
            while True:
                print(f'File "{output_path}" already exists! Overwrite? [y/N] ', end='')
                yn = input().lower()
                if yn == '' or yn == 'n':
                    sys.exit(0)
                else:
                    os.remove(output_path)
                    break

    if start_time:
        req_time = datetime.strptime(data.split("yt:mpdRequestTime=\"")[-1].split("\"")[0], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone()
        segments_back = round((req_time - start_time).total_seconds() / 2)
        segments_back = segments_back if segments_back < max_seg else max_seg
        dur_segments = round(duration_secs / 2)
        start_segment = max_seg - segments_back
        end_segment = start_segment + dur_segments
        total_segments = range(start_segment, end_segment)
    else:
        total_segments = range(max_seg)

    # make a temporary directory in the output file's directory
    tempdir_parent = os.path.dirname(os.path.abspath(os.path.realpath(output_path)))
    tempdir = ".temp-" + str(random.randint(1000,9999))
    while os.path.exists(tempdir):
        tempdir = ".temp-" + str(random.randint(1000,9999))
    tempdir = os.path.join(tempdir_parent, tempdir)
    os.mkdir(tempdir)

    os.mkdir(os.path.join(tempdir, "temp-video"))
    os.mkdir(os.path.join(tempdir, "temp-audio"))

    # get video and audio segments asynchronously
    asyncio.get_event_loop().run_until_complete(get_segments(total_segments, video_base, audio_base, tempdir))

    # merge video and audio segments each into its file
    os.mkdir(os.path.join(tempdir, "avseg"))
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        params = ((ffmpeg_executable, tempdir, i) for i in total_segments)
        list(tqdm(pool.imap_unordered(process_segments, params), total=len(total_segments), desc="Merging segments"))
        pool.close()
        pool.join()
    
    with open(os.path.join(tempdir, "avseg.txt"), "w+") as avseg:
        for i in total_segments:
            avseg.write(f"file '{os.path.join(tempdir, 'avseg', f'{i}.ts')}'\n")

    shutil.rmtree(os.path.join(tempdir, "temp-video"), ignore_errors=True)
    shutil.rmtree(os.path.join(tempdir, "temp-audio"), ignore_errors=True)

    size_avseg_total = sum(os.path.getsize(os.path.join(tempdir, "avseg", f)) for f in os.listdir(os.path.join(tempdir, "avseg")) if os.path.isfile(os.path.join(tempdir, "avseg", f)))//1024
    cmd_final = [
        ffmpeg_executable,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        f"{os.path.join(tempdir, 'avseg.txt')}",
        "-c",
        "copy",
        output_path
    ]
    process_final = subprocess.Popen(cmd_final, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    pbar_final = tqdm(total=size_avseg_total, desc="Merging final")

    while True:
        line_avseg = process_final.stdout.readline()
        if not line_avseg: break

        match_avseg = re.match(r".*size= *(\d+)", line_avseg)
        if match_avseg is not None:
            size_avseg = int(match_avseg[1])
            pbar_final.update(size_avseg - pbar_final.n)

    pbar_final.update(size_avseg_total - pbar_final.n)
    pbar_final.close()

    shutil.rmtree(tempdir, ignore_errors=True)

if __name__ == "__main__":
    plt = platform.system()
    if plt == "Windows":
        if not (os.path.exists("./bin/ffmpeg.exe") or shutil.which("ffmpeg")):
            print("Run 'python download.py' first!")
            exit(1)
        elif os.path.exists("./bin/ffmpeg.exe"):
            main(".\\bin\\ffmpeg.exe")
        else:
            main("ffmpeg")
    elif plt == "Linux" or plt == "Darwin":
        if not shutil.which("ffmpeg"):
            print("Install ffmpeg to path!")
            exit(1)
        else:
            main("ffmpeg")
