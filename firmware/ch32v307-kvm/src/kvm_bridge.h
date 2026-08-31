#ifndef OPENBMC_KVM_BRIDGE_H
#define OPENBMC_KVM_BRIDGE_H

#include <stdint.h>

void KVM_Bridge_Init(uint32_t baudrate);
void KVM_Bridge_Poll(void);
void KVM_Timer_Init(void);

#endif
