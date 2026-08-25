SUMMARY = "Orange Pi Zero 2 U-Boot boot files"
DESCRIPTION = "Deploys the extlinux configuration used by the Orange Pi Zero 2 SD image."
LICENSE = "Apache-2.0"

SRC_URI = "file://orangepi-zero2-extlinux.conf"
S = "${UNPACKDIR}"

inherit deploy

do_deploy() {
    install -Dm0644 ${UNPACKDIR}/orangepi-zero2-extlinux.conf \
        ${DEPLOYDIR}/orangepi-zero2-extlinux.conf
}

addtask deploy after do_compile before do_build
