#!/usr/bin/env bash
# ত্রুটি ঘটলে স্ক্রিপ্ট থামিয়ে দেওয়ার জন্য
set -o errexit

# Python প্যাকেজ ইনস্টল
pip install -r requirements.txt

# FFmpeg স্ট্যাটিক বাইনারি ডাউনলোড ও আনপ্যাক
mkdir -p ffmpeg_bin
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ -C ffmpeg_bin --strip-components 1

# এক্সিকিউটেবল পারমিশন নিশ্চিত করা
chmod +x ffmpeg_bin/ffmpeg
chmod +x ffmpeg_bin/ffprobe
