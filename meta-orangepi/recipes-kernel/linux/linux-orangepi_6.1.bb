SUMMARY = "Linux kernel for Orange Pi Zero 2 H616"
DESCRIPTION = "Orange Pi's Linux 6.1 H616 kernel with the Orange Pi Zero 2 device tree."
HOMEPAGE = "https://github.com/orangepi-xunlong/linux-orangepi"
SECTION = "kernel"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

LINUX_VERSION = "6.1"
PV = "6.1+git${SRCPV}"
SRC_URI = " \
    git://github.com/orangepi-xunlong/linux-orangepi.git;protocol=https;branch=orange-pi-6.1-sun50iw9 \
    file://0001-uwe5622-fix-out-of-tree-include-paths.patch \
    file://0002-sun50i-cpufreq-nvmem-use-opp-token-type.patch \
    file://0003-realtek-fix-separate-build-include-paths.patch \
    file://defconfig \
    "
SRCREV = "71144529b0334d1488624c41d0d3ba0cb03dd4c1"
BB_GIT_SHALLOW = "1"
BB_GIT_SHALLOW_DEPTH = "1"

inherit kernel

# kernel.bbclass otherwise sets S to the not-yet-populated shared directory.
# Its do_symlink_kernsrc task moves this fetched source into that shared tree.
S = "${UNPACKDIR}/${BP}"

COMPATIBLE_MACHINE = "orangepi-zero2"
KERNEL_IMAGETYPE = "Image"
KERNEL_DEVICETREE = "allwinner/sun50i-h616-orangepi-zero2.dtb"
KERNEL_VERSION_SANITY_SKIP = "1"
KERNEL_LOCALVERSION = "-orangepi-openbmc"
B = "${WORKDIR}/build"

do_configure:prepend() {
    grep -qx 'CONFIG_ARM64=y' ${UNPACKDIR}/defconfig || \
        bbfatal "Generate the Orange Pi defconfig before running BitBake (see the workflow)"
}

do_configure:append() {
    # No initramfs or NLS module package: both partitions must mount unaided.
    for option in ARM64 MMC MMC_BLOCK MMC_SUNXI EXT4_FS DEVTMPFS DEVTMPFS_MOUNT \
                  MSDOS_PARTITION VFAT_FS NLS_CODEPAGE_437 NLS_ISO8859_1 NLS_UTF8; do
        grep -qx "CONFIG_$option=y" ${B}/.config || \
            bbfatal "TF-card boot requires CONFIG_$option=y"
    done
}

# Explicit CI preflight only: do not replace the normal kernel/modules build.
# These objects exercise the vendor include paths and OPP API using the real
# Yocto compiler, without waiting for a complete kernel to link first.
do_board_preflight() {
    unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS MACHINE
    targets="drivers/cpufreq/sun50i-cpufreq-nvmem.o
             drivers/net/wireless/uwe5622/unisocwcn/wcn_bus.o"
    for driver in rtl8189es rtl8189fs rtl8192eu rtl8723ds rtl8723du \
                  rtl8811cu rtl8812au rtl88x2cs; do
        targets="$targets drivers/net/wireless/$driver/core/rtw_cmd.o"
    done
    oe_runmake -C ${S} O=${B} ${PARALLEL_MAKE} ${KERNEL_EXTRA_ARGS} $targets
}
do_board_preflight[dirs] = "${B}"
do_board_preflight[nostamp] = "1"
addtask board_preflight after do_configure
