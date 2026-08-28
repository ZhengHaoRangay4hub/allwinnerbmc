SUMMARY = "H616 BL31 firmware for the Orange Pi Zero 2 boot chain"
DESCRIPTION = "Trusted Firmware-A EL3 and PSCI runtime, included inside the TF-card image."
HOMEPAGE = "https://trustedfirmware-a.readthedocs.io/"
LICENSE = "BSD-2-Clause & BSD-3-Clause & MIT & Apache-2.0"
LIC_FILES_CHKSUM = "file://docs/license.rst;md5=6ed7bace7b0bc63021c6eba7b524039e"

# The upstream GitHub mirror exposes lts-v2.14.2 as a tag, not an LTS branch.
SRC_URI = "git://github.com/ARM-software/arm-trusted-firmware.git;protocol=https;nobranch=1"
SRCREV = "aa1793fff49a1b5a6a877c278a0df0a188e2b1f2"
# OE-Core sets both S and the Git checkout suffix from BP. Do not restore
# the legacy /git override: current do_qa_unpack rejects it explicitly.
B = "${WORKDIR}/build"

COMPATIBLE_MACHINE = "orangepi-zero2"
PACKAGE_ARCH = "${MACHINE_ARCH}"
DEPENDS += "dtc-native"

inherit deploy

do_configure[noexec] = "1"
do_compile() {
    unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS AS LD
    oe_runmake -C ${S} BUILD_BASE=${B} PLAT=sun50i_h616 \
        CROSS_COMPILE="${TARGET_PREFIX}" CC="${TARGET_PREFIX}gcc" \
        LD="${TARGET_PREFIX}ld" HOSTCC="${BUILD_CC}" \
        V=1 E=0 DEBUG=0 bl31
}

# Stage BL31 through the recipe sysroot so U-Boot's DEPENDS is sufficient.
do_install() {
    install -Dm0644 ${B}/sun50i_h616/release/bl31.bin \
        ${D}${datadir}/trusted-firmware-a/orangepi-zero2/bl31.bin
}

do_deploy() {
    install -Dm0644 ${B}/sun50i_h616/release/bl31.bin \
        ${DEPLOYDIR}/bl31-orangepi-zero2.bin
}
addtask deploy after do_compile before do_build

FILES:${PN} = "${datadir}/trusted-firmware-a"
