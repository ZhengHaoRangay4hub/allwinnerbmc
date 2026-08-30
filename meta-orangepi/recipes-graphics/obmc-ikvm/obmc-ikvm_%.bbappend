FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://0001-support-video-only-UVC-MJPEG-devices.patch \
    file://obmc-ikvm.service \
    "

do_install:append() {
    install -Dm0644 ${UNPACKDIR}/obmc-ikvm.service \
        ${D}${systemd_system_unitdir}/obmc-ikvm.service
}

RDEPENDS:${PN}:append = " kmod"
