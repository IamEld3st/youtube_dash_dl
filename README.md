# YouTube Dash DL

Tool to download VoD of an ongoing stream without any time limitations.

## How to use

### Install (pip)

```shell
pip install youtube_dash_dl
```

### Checking how much you can download back

```shell
yt_ddl <URL> -l
```

This will get the YouTube DASH manifest and calculate how much time you can go backwards for download. It will also give you all stream ids for download

### Downloading the whole stream

```shell
yt_ddl <URL> -o <OUTPUT>
```

This will get the stream from the beginning to the point of running the command and save it as OUTPUT (Use .mp4 file as output only!).

### Downloading specific part

```shell
yt_ddl <URL> -o <OUTPUT> --start <START_TIME> --duration <DURATION>
# or
yt_ddl <URL> -o <OUTPUT> --start <START_TIME> --end <END_TIME>

# e.g.
python yt_ddl.py https://www.youtube.com/watch?v=XXXXXXXXXXX -o output.mp4 --start 2020-08-12T09:16 --duration 10m
# Will download 10 minute video starting 2020-08-12T09:16
# Pay attention to the format of the url! exclude any other tags after the video id.
```

Yoou can also use:

-   \-s instead of --start
-   \-d instead of --duration
-   \-e instead of --end 

`START_TIME` and `END_TIME` can be one of the following formats:

-   `12:34`
-   `12:34:56`
-   `7.8 12:34`
-   `7.8 12:34:56`
-   `7.8.2009 12:34`
-   `7.8.2009 12:34:56`
-   `2009-08-07T12:34:56`

`DURATION` can be one of the following formats:

-   `12h34m56s`
-   `12h34m`
-   `12h34s`
-   `12m34s`
-   `123h`
-   `123m`
-   `123s`

When the date part is omitted, today's date is assumed. 

The part of the video to be downloaded can be specified either by the start and end time, or by the start time and duration. 

Local timezone is used unless `--utc` switch is provided.

Only .mp4 and .mkv output format is supported at the moment.

## Python compatibility

-   3.6+
