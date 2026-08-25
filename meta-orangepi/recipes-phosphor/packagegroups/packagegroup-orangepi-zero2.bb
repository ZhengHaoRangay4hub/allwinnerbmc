SUMMARY = "Orange Pi Zero 2 OpenBMC hardware integration"
DESCRIPTION = "GPIO tools and the MS2130 UVC capture service for Orange Pi Zero 2."
LICENSE = "Apache-2.0"

inherit packagegroup

RDEPENDS:${PN} = " \
    libgpiod-tools \
    v4l-utils \
    kernel-module-uvcvideo \
    orangepi-gpio-control \
    orangepi-ms2130-capture \
    "
