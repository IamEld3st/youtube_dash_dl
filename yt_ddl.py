from requests import get # requests
import sys #
from bs4 import BeautifulSoup # beautifulsoup4 / lxml
import urllib.parse #
import os #
from mpegdash.parser import MPEGDASHParser # mpegdash
import datetime #
from tqdm import tqdm # tqdm
import platform
import shutil


def get_mpd_data(videoURL):
    raw_page = get(sys.argv[1])
    soup = BeautifulSoup(raw_page.text, 'lxml')
    script_obj = str(soup(id="player-wrap")[0].find_all("script")[1]).split("\\\"")
    for i in range(len(script_obj)):
        if script_obj[i] == "dashManifestUrl":
            mpd_url = script_obj[i+2]
            break
    mpd_url = urllib.parse.unquote(mpd_url).replace("\/", "/")
    mpd_file_content = get(mpd_url)
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

def main(ffmpeg_executable):
    data = get_mpd_data(sys.argv[1])
    video, audio = get_best_representation(data)

    video_base = video.base_urls[0].base_url_value + "/".join(video.segment_lists[0].segment_urls[0].media.split('/')[:-3])
    audio_base = audio.base_urls[0].base_url_value + "/".join(audio.segment_lists[0].segment_urls[0].media.split('/')[:-3])
    max_seg = int(video.segment_lists[0].segment_urls[-1].media.split('/')[-3])

    if len(sys.argv) < 3:
        print(f"You can go back {int(max_seg*2/60/60)} hours and {int(max_seg*2/60%60)} minutes back...")
        exit(0)

    video_file = open("video.ts", "wb")
    audio_file = open("audio.ts", "wb")

    if len(sys.argv) > 3:
        req_time = datetime.datetime.strptime(data.split("yt:mpdRequestTime=\"")[-1].split("\"")[0], "%Y-%m-%dT%H:%M:%S.%f")
        start_time = datetime.datetime.strptime(sys.argv[3], "%Y-%m-%dT%H:%M")
        segments_back = round((req_time - start_time).seconds / 2)
        dur_segments = int(sys.argv[4]) * 30
        start_segment = max_seg - segments_back
        end_segment = start_segment + dur_segments
        total_segments = range(start_segment, end_segment)
    else:
        total_segments = range(max_seg)

    for i in tqdm(total_segments):
        video_file.write(get(f"{video_base}/{i}").content)
        audio_file.write(get(f"{audio_base}/{i}").content)

    video_file.close()
    audio_file.close()

    os.system(f"{ffmpeg_executable} -hide_banner -loglevel 0 -i audio.ts -i video.ts -c copy {sys.argv[2]}")
    os.remove("video.ts")
    os.remove("audio.ts")

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
    elif plt == "Linux":
        if not shutil.which("ffmpeg"):
            print("Install ffmpeg to path!")
            exit(1)
        else:
            main("ffmpeg")