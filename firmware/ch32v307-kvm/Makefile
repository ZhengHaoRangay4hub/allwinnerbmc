THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
WCH_EVT ?= $(abspath $(THIS_DIR)/../../../../WCH/CH32V307EVT-3.1/EVT)
WCH_COMMON := $(WCH_EVT)/EXAM/SRC
WCH_EXAMPLE := $(WCH_EVT)/EXAM/USB/USBHS/DEVICE/CompositeKM/User

TOOLCHAIN_DIR ?= /Applications/MounRiver Studio 2.app/Contents/Resources/app/resources/darwin/components/WCH/Toolchain/RISC-V Embedded GCC/bin
CC := $(TOOLCHAIN_DIR)/riscv-none-embed-gcc
OBJCOPY := $(TOOLCHAIN_DIR)/riscv-none-embed-objcopy
SIZE := $(TOOLCHAIN_DIR)/riscv-none-embed-size

BUILD := build
TARGET := $(BUILD)/ch32v307-kvm

INCLUDES := \
	-I$(THIS_DIR)/src \
	-I$(WCH_EXAMPLE) \
	-I$(WCH_COMMON)/Core \
	-I$(WCH_COMMON)/Debug \
	-I$(WCH_COMMON)/Peripheral/inc

ARCH_FLAGS := -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore
CFLAGS := $(ARCH_FLAGS) -DCH32V30x_D8C -Os -g3 -std=gnu99 \
	-ffunction-sections -fdata-sections -fno-common -fsigned-char \
	-Wall -Wextra -Werror=implicit-function-declaration \
	-include $(THIS_DIR)/src/usbd_desc_override.h $(INCLUDES)
ASFLAGS := $(ARCH_FLAGS) -DCH32V30x_D8C -g3 -x assembler-with-cpp \
	-I$(WCH_COMMON)/Startup
LDFLAGS := $(ARCH_FLAGS) -T$(WCH_COMMON)/Ld/Link.ld -nostartfiles \
	-Wl,--gc-sections -Wl,-Map,$(TARGET).map --specs=nano.specs \
	--specs=nosys.specs

LOCAL_OBJS := \
	$(BUILD)/main.o \
	$(BUILD)/kvm_bridge.o \
	$(BUILD)/usbd_desc.o

VENDOR_USER_OBJS := \
	$(BUILD)/vendor_ch32v30x_it.o \
	$(BUILD)/vendor_ch32v30x_usbhs_device.o \
	$(BUILD)/vendor_system_ch32v30x.o

COMMON_OBJS := \
	$(BUILD)/core_riscv.o \
	$(BUILD)/debug.o \
	$(BUILD)/startup_ch32v30x_D8C.o

PERIPHERAL_NAMES := adc bkp can crc dac dbgmcu dma dvp eth exti flash fsmc \
	gpio i2c iwdg misc opa pwr rcc rng rtc sdio spi tim usart wwdg
PERIPHERAL_OBJS := $(addprefix $(BUILD)/ch32v30x_,$(addsuffix .o,$(PERIPHERAL_NAMES)))
OBJS := $(LOCAL_OBJS) $(VENDOR_USER_OBJS) $(COMMON_OBJS) $(PERIPHERAL_OBJS)

.PHONY: all clean check-sdk

all: check-sdk $(TARGET).elf $(TARGET).hex $(TARGET).bin
	@"$(SIZE)" $(TARGET).elf

check-sdk:
	@test -f "$(WCH_EXAMPLE)/ch32v30x_usbhs_device.c" || \
		{ echo "WCH EVT SDK not found: $(WCH_EVT)"; exit 1; }
	@test -x "$(CC)" || { echo "WCH compiler not found: $(CC)"; exit 1; }

$(BUILD):
	@mkdir -p $@

$(BUILD)/%.o: src/%.c | $(BUILD)
	@"$(CC)" $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/vendor_%.o: $(WCH_EXAMPLE)/%.c | $(BUILD)
	@"$(CC)" $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/core_riscv.o: $(WCH_COMMON)/Core/core_riscv.c | $(BUILD)
	@"$(CC)" $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/debug.o: $(WCH_COMMON)/Debug/debug.c | $(BUILD)
	@"$(CC)" $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/ch32v30x_%.o: $(WCH_COMMON)/Peripheral/src/ch32v30x_%.c | $(BUILD)
	@"$(CC)" $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/startup_ch32v30x_D8C.o: $(WCH_COMMON)/Startup/startup_ch32v30x_D8C.S | $(BUILD)
	@"$(CC)" $(ASFLAGS) -MMD -MP -c $< -o $@

$(TARGET).elf: $(OBJS)
	@"$(CC)" $(LDFLAGS) -o $@ $(OBJS) -lm

$(TARGET).hex: $(TARGET).elf
	@"$(OBJCOPY)" -O ihex $< $@

$(TARGET).bin: $(TARGET).elf
	@"$(OBJCOPY)" -O binary $< $@

clean:
	@rm -rf $(BUILD)

-include $(OBJS:.o=.d)
