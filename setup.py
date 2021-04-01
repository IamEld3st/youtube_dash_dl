from setuptools import setup, find_packages
from io import open
from os import path

import pathlib

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text(encoding="utf-8")

# automatically captured required modules for install_requires in requirements.txt
with open(path.join(HERE, "requirements.txt"), encoding="utf-8") as f:
    all_reqs = f.read().split("\n")

install_requires = [
    x.strip()
    for x in all_reqs
    if ("git+" not in x) and (not x.startswith("#")) and (not x.startswith("-"))
]
dependency_links = [x.strip().replace("git+", "") for x in all_reqs if "git+" not in x]
setup(
    name="youtube_dash_dl",
    description="Tool to download VoD of an ongoing stream without any time limitations.",
    version="1.0.7",
    packages=find_packages(),
    install_requires=install_requires,
    python_requires=">=3.6",
    entry_points = {
        'console_scripts': ['yt_ddl=yt_ddl.yt_ddl:main'],
    },
    author="IamEld3st",
    keyword="youtube, download, mpeg-dash, stream, live",
    license="MIT",
    url="https://github.com/IamEld3st/youtube_dash_dl",
    dependency_links=dependency_links,
    author_email="iameld3st@gmail.com",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
    ],
)