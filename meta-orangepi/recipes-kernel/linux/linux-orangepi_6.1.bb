SUMMARY = "Linux kernel for Orange Pi Zero 2 H616"
DESCRIPTION = "Orange Pi's Linux 6.1 H616 kernel with the Orange Pi Zero 2 device tree."
HOMEPAGE = "https://github.com/orangepi-xunlong/linux-orangepi"
SECTION = "kernel"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

LINUX_VERSION = "6.1"
PV = "6.1+git${SRCPV}"
SRC_URI = "file://defconfig"
SRCREV = "71144529b0334d1488624c41d0d3ba0cb03dd4c1"

inherit kernel externalsrc

COMPATIBLE_MACHINE = "orangepi-zero2"
KERNEL_IMAGETYPE = "Image"
KERNEL_DEVICETREE = "allwinner/sun50i-h616-orangepi-zero2.dtb"
KERNEL_VERSION_SANITY_SKIP = "1"
KERNEL_LOCALVERSION = "-orangepi-openbmc"
B = "${WORKDIR}/build"

EXTERNALSRC ?= "/public/home/acb2lyz1kv/opizero-openbmc/linux-orangepi"
EXTERNALSRC_BUILD ?= "${B}"
