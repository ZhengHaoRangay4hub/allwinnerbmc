SUMMARY = "Orange Pi Zero 2 Wi-Fi startup and network configuration"
DESCRIPTION = "Loads the onboard UWE5622 radio and starts wpa_supplicant for wlan0."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://orangepi-uwe5622.conf \
    file://orangepi-wifi.service \
    file://wpa_supplicant-wlan0.conf \
    file://80-wlan0.network \
    "

S = "${UNPACKDIR}"

inherit systemd

COMPATIBLE_MACHINE = "orangepi-zero2"
PACKAGE_ARCH = "${MACHINE_ARCH}"

do_compile[noexec] = "1"

do_install() {
    install -d ${D}${sysconfdir}/modules-load.d
    install -m 0644 ${UNPACKDIR}/orangepi-uwe5622.conf \
        ${D}${sysconfdir}/modules-load.d/orangepi-uwe5622.conf

    install -d ${D}${sysconfdir}/wpa_supplicant
    install -m 0600 ${UNPACKDIR}/wpa_supplicant-wlan0.conf \
        ${D}${sysconfdir}/wpa_supplicant/wpa_supplicant-wlan0.conf

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${UNPACKDIR}/orangepi-wifi.service \
        ${D}${systemd_system_unitdir}/orangepi-wifi.service

    install -d ${D}${systemd_unitdir}/network
    install -m 0644 ${UNPACKDIR}/80-wlan0.network \
        ${D}${systemd_unitdir}/network/80-wlan0.network
}

SYSTEMD_SERVICE:${PN} = "orangepi-wifi.service"
SYSTEMD_AUTO_ENABLE = "enable"

FILES:${PN} += "${systemd_unitdir}/network/80-wlan0.network"
