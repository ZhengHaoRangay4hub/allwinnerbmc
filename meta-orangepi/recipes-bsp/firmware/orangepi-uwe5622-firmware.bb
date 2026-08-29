SUMMARY = "UWE5622 Wi-Fi firmware for Orange Pi Zero 2"
DESCRIPTION = "Pinned Orange Pi firmware and board calibration for the onboard UWE5622 SDIO radio."
HOMEPAGE = "https://github.com/orangepi-xunlong/firmware"
LICENSE = "CLOSED"

FIRMWARE_SRCREV = "db5e86200ae592c467c4cfa50ec0c66cbc40b158"
SRC_URI = " \
    https://raw.githubusercontent.com/orangepi-xunlong/firmware/${FIRMWARE_SRCREV}/wcnmodem.bin;name=wcnmodem \
    https://raw.githubusercontent.com/orangepi-xunlong/firmware/${FIRMWARE_SRCREV}/wifi_2355b001_1ant.ini;name=boardconfig \
    "
SRC_URI[wcnmodem.sha256sum] = "119b87ce30875734a67462f7293fb8fe85acf3270fe8b78c978ae24be7715a80"
SRC_URI[boardconfig.sha256sum] = "1f3c40ec245a8d0b99ad1c23706597d6dd5008ab80cefb7bcc1956efc4e938f7"

S = "${UNPACKDIR}"

COMPATIBLE_MACHINE = "orangepi-zero2"
PACKAGE_ARCH = "${MACHINE_ARCH}"

do_compile[noexec] = "1"

do_install() {
    install -d ${D}${nonarch_base_libdir}/firmware
    install -m 0644 ${UNPACKDIR}/wcnmodem.bin \
        ${D}${nonarch_base_libdir}/firmware/wcnmodem.bin
    install -m 0644 ${UNPACKDIR}/wifi_2355b001_1ant.ini \
        ${D}${nonarch_base_libdir}/firmware/wifi_2355b001_1ant.ini
}

FILES:${PN} = "${nonarch_base_libdir}/firmware/wcnmodem.bin \
               ${nonarch_base_libdir}/firmware/wifi_2355b001_1ant.ini"
