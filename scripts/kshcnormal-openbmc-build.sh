#!/usr/bin/env bash
set -Eeuo pipefail

root="$HOME/opizero-openbmc"
shared_src="$root/openbmc-src"
local_src="/tmp/${USER}-opizero-openbmc-src"
local_build="/tmp/${USER}-opizero-openbmc-build"
downloads="$root/yocto-downloads"
sstate="$root/yocto-sstate"
artifacts="$root/artifacts/orangepi-zero2-openbmc"
log="$root/openbmc-orangepi-image-kshcnormal.log"

mkdir -p "$root" "$downloads" "$sstate" "$artifacts"
exec > >(tee -a "$log") 2>&1
echo "job=${SLURM_JOB_ID:-unknown} host=$(hostname) start=$(date -Is)"

if [ -f "$local_src/setup" ] && [ -f "$local_src/meta-orangepi/conf/machine/orangepi-zero2.conf" ]; then
    echo "source_reuse=$(date -Is) target=$local_src"
else
    rm -rf "$local_src"
    mkdir -p "$local_src"
    echo "copy_start=$(date -Is) source=$shared_src target=$local_src"
    tar --no-xattrs --no-acls -C "$shared_src" -cf - . | tar --no-xattrs --no-acls -C "$local_src" -xf -
    echo "copy_done=$(date -Is)"
fi

if [ -r /etc/profile.d/modules.sh ]; then
    # Use the cluster's GCC 12 toolchain; the system compiler is GCC 7.
    source /etc/profile.d/modules.sh
    module load compiler/gcc/12.2.0
fi
export PATH="$root/chrpath-0.18/bin:$root/zstd-1.5.5/bin:$root/python-3.9.18/bin:$PATH"
python3 --version
cd "$local_src"
# OpenBMC's setup script probes ZSH_NAME without a default value.  Keep
# nounset for the build itself, but allow that compatibility probe to run.
set +u
. ./setup orangepi-zero2 "$local_build"
set -u

cat >> "$local_build/conf/local.conf" <<EOF
BB_NUMBER_THREADS = "16"
BB_NUMBER_PARSE_THREADS = "8"
PARALLEL_MAKE = "-j8"
PARALLEL_MAKE:pn-gcc-cross-aarch64 = "-j4"
TMPDIR = "$local_build/tmp"
DL_DIR = "$downloads"
SSTATE_DIR = "$sstate"
HOSTTOOLS:remove = " chrpath rpcgen"
HOSTTOOLS_NONFATAL:append = " chrpath rpcgen"
EOF

bitbake obmc-phosphor-image

if [ -d "$local_build/tmp/deploy/images/orangepi-zero2" ]; then
    cp -a "$local_build/tmp/deploy/images/orangepi-zero2/." "$artifacts/"
    (cd "$artifacts" && sha256sum * > SHA256SUMS)
fi
echo "job=${SLURM_JOB_ID:-unknown} host=$(hostname) end=$(date -Is)"
