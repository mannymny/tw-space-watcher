#!/bin/bash

echo "🚀 Starting Twitter Spaces Watcher"
cd "$(dirname "$0")"

pip install -q -r requirements.txt

python3 tw_space_watcher.py
