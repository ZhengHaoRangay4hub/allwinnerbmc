SUMMARY = "Orange Pi Zero 2 OpenBMC hardware integration"
DESCRIPTION = "GPIO, onboard UWE5622 Wi-Fi, MS2130 UVC capture, and CH340-attached CH32V307 HID support for Orange Pi Zero 2."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

inherit packagegroup

RDEPENDS:${PN} = " \
    u-boot-orangepi \
    libgpiod-tools \
    v4l-utils \
    kernel-module-uvcvideo \
    kernel-module-ch341 \
    kernel-module-uwe5622-bsp-sdio \
    kernel-module-sprdwl-ng \
    kernel-module-cfg80211 \
    kernel-module-rfkill \
    orangepi-uwe5622-firmware \
    orangepi-wifi-support \
    iw \
    rfkill \
    wireless-regdb-static \
    wpa-supplicant \
    wpa-supplicant-cli \
    wpa-supplicant-passphrase \
    orangepi-gpio-control \
    orangepi-ms2130-capture \
    "
