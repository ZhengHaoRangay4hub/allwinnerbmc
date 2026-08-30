SUMMARY = "MS2130 USB UVC frame capture service"
DESCRIPTION = "Captures MJPEG frames from an MS2130-compatible USB video device."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://ms2130-capture.c \
    file://ms2130-capture.service \
    "
S = "${UNPACKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "ms2130-capture.service"
SYSTEMD_AUTO_ENABLE = "disable"

do_compile() {
    ${CC} ${CFLAGS} ${LDFLAGS} -std=c11 -D_FILE_OFFSET_BITS=64 \
        -Wall -Wextra -Werror -o ms2130-capture ms2130-capture.c
}

do_install() {
    install -Dm0755 ${S}/ms2130-capture ${D}${bindir}/ms2130-capture
    install -Dm0644 ${S}/ms2130-capture.service \
        ${D}${systemd_system_unitdir}/ms2130-capture.service
}

RDEPENDS:${PN} = "kmod v4l-utils"
