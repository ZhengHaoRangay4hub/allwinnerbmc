#!/usr/bin/env bash
set -Eeuo pipefail

root="$HOME/opizero-openbmc"
tools="$root/tools"
source_tar="$tools/Python-3.9.18.tgz"
source_dir="/tmp/${USER}-Python-3.9.18"
prefix="$root/python-3.9.18"

mkdir -p "$tools"
if [ ! -s "$source_tar" ]; then
    curl -fL --retry 3 --connect-timeout 15 --max-time 600 \
        -o "$source_tar" \
        https://repo.huaweicloud.com/python/3.9.18/Python-3.9.18.tgz
fi

if [ ! -x "$prefix/bin/python3" ]; then
    rm -rf "$source_dir"
    mkdir -p "$source_dir"
    tar -xzf "$source_tar" -C "$source_dir" --strip-components=1

    if [ -r /etc/profile.d/modules.sh ]; then
        source /etc/profile.d/modules.sh
        module load compiler/devtoolset/7.3.1
    fi
    export PATH="/opt/rh/devtoolset-7/root/usr/bin:/usr/bin:/bin:$PATH"

    cd "$source_dir"
    ./configure --prefix="$prefix" --with-ensurepip=install
    make -j8
    make install
fi

"$prefix/bin/python3" --version
"$prefix/bin/python3" -c 'import sys, json, hashlib, gzip; print(sys.executable); print(sys.version)'
