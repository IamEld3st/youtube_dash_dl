from requests import get
from zipfile import ZipFile
from io import BytesIO
import os
import sys

if not os.path.exists("./bin/ffmpeg.exe"):
    if not os.path.exists("./bin"):
        os.mkdir("./bin")
    zip_data = BytesIO()
    res = get("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", stream=True)
    total_length = res.headers.get('content-length')
    if total_length == None:
        zip_data.write(res.content)
    else:
        dl = 0
        total_length = int(total_length)
        for data in res.iter_content(chunk_size=65536):
            dl += len(data)
            zip_data.write(data)
            done = int(50 * dl / total_length)
            sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50-done)) )    
            sys.stdout.flush()
    zf = ZipFile(zip_data)
    for zipped_file in zf.filelist:
        if "bin/ffmpeg.exe" in zipped_file.filename:
            with zf.open(zipped_file) as ffmpeg:
                with open("bin/ffmpeg.exe", "wb") as f:
                    f.write(ffmpeg.read())

