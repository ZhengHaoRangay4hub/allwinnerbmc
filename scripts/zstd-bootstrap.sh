#!/usr/bin/env bash
set -Eeuo pipefail

root="$HOME/opizero-openbmc"
source_tar="$root/tools/zstd-v1.5.5.tar.gz"
source_dir="/tmp/${USER}-zstd-1.5.5"
prefix="$root/zstd-1.5.5"

if [ ! -d "$source_dir" ]; then
    rm -rf "$source_dir"
    mkdir -p "$source_dir"
    tar -xzf "$source_tar" -C "$source_dir" --strip-components=1
fi

if [ ! -x "$prefix/bin/zstd" ]; then
    if [ -r /etc/profile.d/modules.sh ]; then
        source /etc/profile.d/modules.sh
        module load compiler/devtoolset/7.3.1
    fi
    export PATH="/opt/rh/devtoolset-7/root/usr/bin:/usr/bin:/bin:$PATH"

    make -C "$source_dir/programs" -j8
    make -C "$source_dir/programs" install PREFIX="$prefix"
fi

if [ ! -x "$prefix/bin/pzstd" ]; then
    if [ -r /etc/profile.d/modules.sh ]; then
        source /etc/profile.d/modules.sh
        module load compiler/devtoolset/7.3.1
    fi
    export PATH="/opt/rh/devtoolset-7/root/usr/bin:/usr/bin:/bin:$PATH"
    make -C "$source_dir/contrib/pzstd" -j8
    make -C "$source_dir/contrib/pzstd" install PREFIX="$prefix"
fi

for tool in zstd pzstd unzstd; do
    test -x "$prefix/bin/$tool"
done
"$prefix/bin/zstd" --version
