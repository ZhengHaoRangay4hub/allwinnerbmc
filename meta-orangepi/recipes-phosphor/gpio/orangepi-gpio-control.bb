SUMMARY = "Basic GPIO control helper for Orange Pi Zero 2"
DESCRIPTION = "A small libgpiod command wrapper using the modern GPIO character device API."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://orangepi-gpioctl"
S = "${UNPACKDIR}"

do_install() {
    install -Dm0755 ${UNPACKDIR}/orangepi-gpioctl ${D}${bindir}/orangepi-gpioctl
}

RDEPENDS:${PN} = "libgpiod-tools"
