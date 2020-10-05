# YouTube Dash DL
Tool to download VoD of an ongoing stream without any time limitations.

## How to use

### Install (Windows)
```shell
pip install -r requirements.txt
python download.py
```

### Install (Unix)
```shell
pip install -r requirements.txt
```
Make sure you have ffmpeg on path!!!

### Checking how much you can download back
```shell
python yt_ddl.py <URL>
```
This will get the YouTube DASH manifest and calculate how much time you can go backwards for download.

### Downloading the whole stream
```shell
python yt_ddl.py <URL> -o <OUTPUT>
```
This will get the stream from the beginning to the point of running the command and save it as OUTPUT (Use .mp4 file as output only!).

### Downloading specific part
```shell
python yt_ddl.py <URL> -o <OUTPUT> --start <START_TIME> --duration <DURATION>
# or
python yt_ddl.py <URL> -o <OUTPUT> --start <START_TIME> --end <END_TIME>

# e.g.
python yt_ddl.py https://www.youtube.com/watch?v=dQw4w9WgXcQ -o output.mp4 --start 2020-08-12T09:16 --duration 10m
# Will download 10 minute video starting 2020-08-12T09:16
```
Supp

`START_TIME` and `END_TIME` can be one of the following formats:
* `12:34`
* `12:34:56`
* `7.8 12:34`
* `7.8 12:34:56`
* `7.8.2009 12:34`
* `7.8.2009 12:34:56`
* `2009-08-07T12:34:56`

`DURATION` can be one of the following formats:
* `12h34m56s`
* `12h34m`
* `12h34s`
* `12m34s`
* `123h`
* `123m`
* `123s`

When the date part is omitted, today's date is assumed. 

The part of the video to be downloaded can be specified either by the start and end time, or by the start time and duration. 

Local timezone is used unless `--utc` switch is provided.

Only .mp4 output format is supported at the moment.

## Python compatibility
 * 3.7+

