FILESEXTRAPATHS:prepend := "${THISDIR}/${BPN}:"

# Complete Simplified Chinese base translated by the Apache-2.0 licensed
# ocp-hm-openbmc-opf-ami/webui-vue project, pinned for reproducibility.
CHINESE_LOCALE_SRCREV = "c757b32cc2940f19429af1903d3d0bda9f20c150"
SRC_URI += " \
    https://raw.githubusercontent.com/ocp-hm-openbmc-opf-ami/webui-vue/${CHINESE_LOCALE_SRCREV}/src/locales/zh-CN.json;name=zhcn;downloadfilename=zh-CN-upstream.json \
    file://zh-CN-additions.json \
    file://merge-webui-locales.py \
    file://default-webui-language.py \
    "
SRC_URI[zhcn.sha256sum] = "3a2e77c4576902b83f6363c9ddf8f78e8cacbe8ca476da5ce1228c8a8949cf21"

do_compile:prepend() {
    ${PYTHON} ${UNPACKDIR}/default-webui-language.py ${S}
    ${PYTHON} ${UNPACKDIR}/merge-webui-locales.py \
        ${S}/src/locales/en-US.json \
        ${UNPACKDIR}/zh-CN-upstream.json \
        ${UNPACKDIR}/zh-CN-additions.json \
        ${S}/src/locales/zh-CN.json
}
