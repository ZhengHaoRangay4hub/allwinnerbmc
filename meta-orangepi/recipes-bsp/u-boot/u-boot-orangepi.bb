SUMMARY = "Orange Pi U-Boot for Allwinner H616"
DESCRIPTION = "U-Boot tree maintained by Orange Pi with the Orange Pi Zero 2 configuration."
HOMEPAGE = "https://github.com/orangepi-xunlong/u-boot-orangepi"
SECTION = "bootloaders"
LICENSE = "GPL-2.0-or-later"

PV = "2021.10+git${SRCPV}"
SRC_URI = ""
SRCREV = "0b91e222a025640182ea986f3c8e8db98cdc962a"

require ${COREBASE}/meta/recipes-bsp/u-boot/u-boot-common.inc
require ${COREBASE}/meta/recipes-bsp/u-boot/u-boot.inc

LIC_FILES_CHKSUM = "file://Licenses/README;md5=5a7450c57ffe5ae63fd732446b988025"

inherit externalsrc

COMPATIBLE_MACHINE = "orangepi-zero2"
UBOOT_ARCH = "arm"
UBOOT_BINARY = "u-boot-sunxi-with-spl.bin"
UBOOT_MAKE_TARGET = "all"
B = "${WORKDIR}/build"

EXTERNALSRC ?= "/public/home/acb2lyz1kv/opizero-openbmc/u-boot-orangepi"
EXTERNALSRC_BUILD ?= "${B}"

do_configure:append() {
    install -d ${B}/include/asm
    ln -sfn ${S}/arch/arm/include/asm/arch-sunxi ${B}/include/asm/arch
    ln -sfn arch-sunxi ${S}/arch/arm/include/asm/arch
}

do_deploy:append() {
    install -m 0644 ${B}/${UBOOT_BINARY} ${DEPLOYDIR}/${UBOOT_BINARY}
}
