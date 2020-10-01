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
python yt_ddl.py <URL> <OUTPUT>
```
This will get the stream from the beginning to the point of running the command and save it as OUTPUT (Use .mp4 file as output only!).

### Downloading specific part
```shell
python yt_ddl.py <URL> <OUTPUT> <UTC_DATE> <DURATION>
python yt_ddl.py https://www.youtube.com/watch?v=dQw4w9WgXcQ output.mp4 2020-08-12T09:16 10
# Will download 10 minute video starting 2020-08-12T09:16
```
This will get only a specific part of the stream from the UTC_DATE (YYYY-MM-DDTHH:MM) and download only DURATION of minutes. File is saved as OUTPUT (Use .mp4 file as output only!).

## Python compatibility
 * 3.7+

