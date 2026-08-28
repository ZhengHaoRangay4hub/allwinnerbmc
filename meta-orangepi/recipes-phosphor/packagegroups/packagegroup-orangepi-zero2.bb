SUMMARY = "Orange Pi Zero 2 OpenBMC hardware integration"
DESCRIPTION = "GPIO tools and the MS2130 UVC capture service for Orange Pi Zero 2."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

inherit packagegroup

RDEPENDS:${PN} = " \
    u-boot-orangepi \
    libgpiod-tools \
    v4l-utils \
    kernel-module-uvcvideo \
    orangepi-gpio-control \
    orangepi-ms2130-capture \
    "
