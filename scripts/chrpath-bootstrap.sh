#!/usr/bin/env bash
set -Eeuo pipefail

root="$HOME/opizero-openbmc"
source_tar="$root/tools/chrpath_0.18.orig.tar.gz"
source_dir="/tmp/${USER}-chrpath-0.18"
prefix="$root/chrpath-0.18"

if [ ! -x "$prefix/bin/chrpath" ]; then
    rm -rf "$source_dir"
    mkdir -p "$source_dir"
    tar -xzf "$source_tar" -C "$source_dir" --strip-components=1

    if [ -r /etc/profile.d/modules.sh ]; then
        source /etc/profile.d/modules.sh
        module load compiler/gcc/12.2.0
    fi
    export PATH="/public/software/compiler/gcc-12.2.0/bin:$PATH"

    cd "$source_dir"
    autoreconf -fi
    ./configure --prefix="$prefix"
    make -j4
    make install
fi

"$prefix/bin/chrpath" --version
