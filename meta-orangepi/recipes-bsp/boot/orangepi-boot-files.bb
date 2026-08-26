SUMMARY = "Orange Pi Zero 2 U-Boot boot files"
DESCRIPTION = "Deploys the extlinux configuration used by the Orange Pi Zero 2 SD image."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://orangepi-zero2-extlinux.conf"
S = "${UNPACKDIR}"

inherit deploy

do_deploy() {
    install -Dm0644 ${UNPACKDIR}/orangepi-zero2-extlinux.conf \
        ${DEPLOYDIR}/orangepi-zero2-extlinux.conf
}

addtask deploy after do_compile before do_build
