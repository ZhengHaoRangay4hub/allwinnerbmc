#ifndef __USBD_DESC_H
#define __USBD_DESC_H

#include <stdint.h>

#define DEF_FILE_VERSION 0x01
#define DEF_USB_VID 0x1A86
#define DEF_USB_PID 0xFE10
#define DEF_IC_PRG_VER DEF_FILE_VERSION

#define DEF_USBD_UEP0_SIZE 64
#define DEF_USBD_HS_PACK_SIZE 512
#define DEF_USBD_HS_ISO_PACK_SIZE 1024
#define DEF_USBD_FS_PACK_SIZE 64
#define DEF_USBD_FS_ISO_PACK_SIZE 1023
#define DEf_USBD_LS_UEP0_SIZE 8
#define DEF_USBD_LS_PACK_SIZE 64

#define DEF_USB_EP1_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP2_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP3_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP4_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP5_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP6_HS_SIZE DEF_USBD_HS_PACK_SIZE
#define DEF_USB_EP1_FS_SIZE DEF_USBD_FS_PACK_SIZE
#define DEF_USB_EP2_FS_SIZE DEF_USBD_FS_PACK_SIZE
#define DEF_USB_EP3_FS_SIZE DEF_USBD_FS_PACK_SIZE
#define DEF_USB_EP4_FS_SIZE DEF_USBD_FS_PACK_SIZE
#define DEF_USB_EP5_FS_SIZE DEF_USBD_FS_PACK_SIZE
#define DEF_USB_EP6_FS_SIZE DEF_USBD_FS_PACK_SIZE

#define DEF_USBD_DEVICE_DESC_LEN ((uint16_t)MyDevDescr[0])
#define DEF_USBD_CONFIG_DESC_LEN \
    ((uint16_t)MyCfgDescr[2] + ((uint16_t)MyCfgDescr[3] << 8))
#define DEF_USBD_REPORT_DESC_LEN_KB 62u
#define DEF_USBD_REPORT_DESC_LEN_MS 76u
#define DEF_USBD_LANG_DESC_LEN ((uint16_t)MyLangDescr[0])
#define DEF_USBD_MANU_DESC_LEN ((uint16_t)MyManuInfo[0])
#define DEF_USBD_PROD_DESC_LEN ((uint16_t)MyProdInfo[0])
#define DEF_USBD_SN_DESC_LEN ((uint16_t)MySerNumInfo[0])
#define DEF_USBD_QUALFY_DESC_LEN ((uint16_t)MyQuaDesc[0])
#define DEF_USBD_BOS_DESC_LEN 0
#define DEF_USBD_FS_OTH_DESC_LEN 0
#define DEF_USBD_HS_OTH_DESC_LEN 0

extern const uint8_t MyDevDescr[];
extern const uint8_t MyCfgDescr[];
extern const uint8_t KeyRepDesc[];
extern const uint8_t MouseRepDesc[];
extern const uint8_t MyQuaDesc[];
extern const uint8_t MyLangDescr[];
extern const uint8_t MyManuInfo[];
extern const uint8_t MyProdInfo[];
extern const uint8_t MySerNumInfo[];

#endif
