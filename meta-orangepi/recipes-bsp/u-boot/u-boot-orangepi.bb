SUMMARY = "Orange Pi U-Boot for Allwinner H616"
DESCRIPTION = "U-Boot tree maintained by Orange Pi with the Orange Pi Zero 2 configuration."
HOMEPAGE = "https://github.com/orangepi-xunlong/u-boot-orangepi"
SECTION = "bootloaders"
LICENSE = "GPL-2.0-or-later"

PV = "2021.10+git${SRCPV}"
SRC_URI = ""
SRCREV = "0b91e222a025640182ea986f3c8e8db98cdc962a"

LIC_FILES_CHKSUM = "file://Licenses/README;md5=5a7450c57ffe5ae63fd732446b988025"

PROVIDES = "virtual/bootloader"
ALLOW_EMPTY:${PN} = "1"
RPROVIDES:${PN} += "u-boot-fw-utils"

inherit externalsrc deploy python3native

# U-Boot's Kconfig parser and pylibfdt binding are generated during the
# build. These tools must come from the BitBake native sysroot, including
# the Python interpreter used by pylibfdt, rather than only the CI host.
DEPENDS += "bison-native flex-native swig-native python3-setuptools-native \
            python3-pyelftools-native openssl-native trusted-firmware-a-orangepi"

COMPATIBLE_MACHINE = "orangepi-zero2"
PACKAGE_ARCH = "${MACHINE_ARCH}"
UBOOT_ARCH = "arm"
UBOOT_BINARY = "u-boot-sunxi-with-spl.bin"
UBOOT_MAKE_TARGET = "all"
B = "${WORKDIR}/build"

EXTERNALSRC ?= "/public/home/acb2lyz1kv/opizero-openbmc/u-boot-orangepi"
EXTERNALSRC_BUILD ?= "${B}"

# Match the native sysroot used by Python/SWIG and host image tools.
EXTRA_OEMAKE += 'CROSS_COMPILE="${TARGET_PREFIX}"'
EXTRA_OEMAKE += 'CC="${TARGET_PREFIX}gcc ${TOOLCHAIN_OPTIONS}"'
EXTRA_OEMAKE += 'HOSTCC="${BUILD_CC} ${BUILD_CFLAGS} ${BUILD_LDFLAGS}"'
EXTRA_OEMAKE += 'HOSTLDFLAGS="${BUILD_LDFLAGS}" PYTHON3="${PYTHON}"'
UBOOT_BL31 = "${RECIPE_SYSROOT}${datadir}/trusted-firmware-a/orangepi-zero2/bl31.bin"

do_configure() {
    install -d ${B}/include/asm
    ln -sfn ${S}/arch/arm/include/asm/arch-sunxi ${B}/include/asm/arch
    ln -sfn arch-sunxi ${S}/arch/arm/include/asm/arch
    oe_runmake -C ${S} O=${B} ARCH=${UBOOT_ARCH} ${UBOOT_MACHINE}
}

do_compile() {
    unset LDFLAGS CFLAGS CPPFLAGS
    test -s "${UBOOT_BL31}" || bbfatal "H616 BL31 firmware is missing from the recipe sysroot"
    oe_runmake -C ${S} O=${B} ARCH=${UBOOT_ARCH} \
        BL31="${UBOOT_BL31}" ${UBOOT_MAKE_TARGET}
    test -s "${B}/${UBOOT_BINARY}" || bbfatal "The combined SPL/U-Boot image was not produced"
}

do_install[noexec] = "1"

do_deploy() {
    install -d ${DEPLOYDIR}
    install -m 0644 ${B}/${UBOOT_BINARY} ${DEPLOYDIR}/${UBOOT_BINARY}
}

addtask deploy after do_compile before do_build
