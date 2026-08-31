#include "ch32v30x_usbhs_device.h"
#include "kvm_bridge.h"
#include "kvm_protocol.h"

int main(void)
{
    SystemCoreClockUpdate();
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    Delay_Init();

    KVM_Bridge_Init(KVM_UART_BAUDRATE);
    KVM_Timer_Init();

    USBHS_RCC_Init();
    USBHS_Device_Init(ENABLE);

    while (1)
    {
        KVM_Bridge_Poll();
    }
}
