SUMMARY = "Orange Pi Zero 2 kernel DTB with reliable TF-card probing"
DESCRIPTION = "Reuses the deployed kernel DTB while bypassing the unreliable PF6 card-detect signal."
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-2.0-only;md5=801f80980d171dd6425610833a22dbe6"

inherit deploy

DEPENDS = "dtc-native"
COMPATIBLE_MACHINE = "orangepi-zero2"
PACKAGE_ARCH = "${MACHINE_ARCH}"

S = "${WORKDIR}"
B = "${WORKDIR}/build"

ORANGEPI_BASE_DTB = "${DEPLOY_DIR_IMAGE}/sun50i-h616-orangepi-zero2.dtb"
ORANGEPI_FIXED_DTB = "sun50i-h616-orangepi-zero2-openbmc.dtb"
ORANGEPI_MMC_NODE = "/soc/mmc@4020000"

# Restore the unchanged kernel's deploy task from sstate, then alter only a
# copy of its DTB. This avoids invalidating the cached kernel compilation.
do_compile[depends] += "virtual/kernel:do_deploy"

do_compile() {
    test -s "${ORANGEPI_BASE_DTB}" || bbfatal "The deployed Orange Pi Zero 2 kernel DTB is missing"
    install -d ${B}
    install -m 0644 "${ORANGEPI_BASE_DTB}" "${B}/${ORANGEPI_FIXED_DTB}"

    ${STAGING_BINDIR_NATIVE}/fdtput -d "${B}/${ORANGEPI_FIXED_DTB}" \
        "${ORANGEPI_MMC_NODE}" cd-gpios
    ${STAGING_BINDIR_NATIVE}/fdtput -p "${B}/${ORANGEPI_FIXED_DTB}" \
        "${ORANGEPI_MMC_NODE}" broken-cd

    if ${STAGING_BINDIR_NATIVE}/fdtget "${B}/${ORANGEPI_FIXED_DTB}" \
        "${ORANGEPI_MMC_NODE}" cd-gpios >/dev/null 2>&1; then
        bbfatal "The fixed kernel DTB still contains the unreliable PF6 card-detect GPIO"
    fi
    ${STAGING_BINDIR_NATIVE}/fdtget -p "${B}/${ORANGEPI_FIXED_DTB}" \
        "${ORANGEPI_MMC_NODE}" | grep -qx broken-cd || \
        bbfatal "The fixed kernel DTB is missing broken-cd"
}

do_deploy() {
    install -d ${DEPLOYDIR}
    install -m 0644 "${B}/${ORANGEPI_FIXED_DTB}" \
        "${DEPLOYDIR}/${ORANGEPI_FIXED_DTB}"
}

addtask deploy after do_compile before do_build
