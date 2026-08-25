SUMMARY = "MS2130 USB UVC frame capture service"
DESCRIPTION = "Captures MJPEG frames from an MS2130-compatible USB video device."
LICENSE = "Apache-2.0"

SRC_URI = " \
    file://ms2130-capture.c \
    file://ms2130-capture.service \
    "
S = "${UNPACKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "ms2130-capture.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_compile() {
    ${CC} ${CFLAGS} ${LDFLAGS} -std=c11 -D_FILE_OFFSET_BITS=64 \
        -Wall -Wextra -Werror -o ms2130-capture ms2130-capture.c
}

do_install() {
    install -Dm0755 ${S}/ms2130-capture ${D}${bindir}/ms2130-capture
    install -Dm0644 ${S}/ms2130-capture.service \
        ${D}${systemd_system_unitdir}/ms2130-capture.service
}

RDEPENDS:${PN} = "v4l-utils"
