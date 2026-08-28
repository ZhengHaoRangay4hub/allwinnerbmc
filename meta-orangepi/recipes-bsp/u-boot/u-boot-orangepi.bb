SUMMARY = "Orange Pi U-Boot for Allwinner H616"
DESCRIPTION = "U-Boot tree maintained by Orange Pi with the Orange Pi Zero 2 configuration."
HOMEPAGE = "https://github.com/orangepi-xunlong/u-boot-orangepi"
SECTION = "bootloaders"
LICENSE = "GPL-2.0-or-later"

PV = "2021.10+git${SRCPV}"
SRC_URI = " \
    git://github.com/orangepi-xunlong/u-boot-orangepi.git;protocol=https;branch=v2021.10-sunxi \
    file://0001-pylibfdt-use-setuptools-on-modern-python.patch \
    file://0002-pylibfdt-use-portable-swig-appendoutput.patch \
    file://0003-binman-use-standard-library-python-apis.patch \
    file://fw_env.config \
    file://fw-env-mounts.conf \
    "
SRCREV = "0b91e222a025640182ea986f3c8e8db98cdc962a"
BB_GIT_SHALLOW = "1"
BB_GIT_SHALLOW_DEPTH = "1"

LIC_FILES_CHKSUM = "file://Licenses/README;md5=5a7450c57ffe5ae63fd732446b988025"

PROVIDES = "virtual/bootloader"
# The userspace environment utilities come from real libubootenv binaries.
RDEPENDS:${PN} += "libubootenv-bin"

inherit deploy python3native

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
UBOOT_ENV_SIZE = "0x20000"
B = "${WORKDIR}/build"

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
        BL31="${UBOOT_BL31}" ${UBOOT_MAKE_TARGET} u-boot-initial-env
    test -s "${B}/${UBOOT_BINARY}" || bbfatal "The combined SPL/U-Boot image was not produced"
    grep -qx 'CONFIG_ENV_IS_IN_FAT=y' ${B}/.config || bbfatal "Expected FAT-backed U-Boot environment"
    grep -qx 'CONFIG_ENV_SIZE=${UBOOT_ENV_SIZE}' ${B}/.config || bbfatal "Unexpected U-Boot environment size"
    ${B}/tools/mkenvimage -s ${UBOOT_ENV_SIZE} -o ${B}/uboot.env ${B}/u-boot-initial-env
}

do_install() {
    install -Dm0644 ${UNPACKDIR}/fw_env.config ${D}${sysconfdir}/fw_env.config
    install -Dm0644 ${B}/u-boot-initial-env ${D}${sysconfdir}/u-boot-initial-env
    # Older OpenBMC services use /sbin while libubootenv installs in /usr/bin.
    install -d ${D}${base_sbindir}
    ln -s ${bindir}/fw_printenv ${D}${base_sbindir}/fw_printenv
    ln -s ${bindir}/fw_setenv ${D}${base_sbindir}/fw_setenv
    for unit in trace-enable clear-once; do
        install -Dm0644 ${UNPACKDIR}/fw-env-mounts.conf \
            ${D}${systemd_system_unitdir}/$unit.service.d/10-fw-env-mounts.conf
    done
}

FILES:${PN} += "${systemd_system_unitdir}/trace-enable.service.d \
                ${systemd_system_unitdir}/clear-once.service.d"

do_deploy() {
    install -d ${DEPLOYDIR}
    install -m 0644 ${B}/${UBOOT_BINARY} ${DEPLOYDIR}/${UBOOT_BINARY}
    install -m 0644 ${B}/uboot.env ${DEPLOYDIR}/uboot.env
}

addtask deploy after do_compile before do_build
