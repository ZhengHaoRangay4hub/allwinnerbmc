FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
WKS_SEARCH_PATH:append := ":${THISDIR}/files/wic"

IMAGE_INSTALL:append:orangepi-zero2 = " packagegroup-orangepi-zero2"
