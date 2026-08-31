#include "ch32v30x_usbhs_device.h"
#include "kvm_bridge.h"
#include "kvm_protocol.h"

int main(void)
{
    SystemCoreClockUpdate();
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    Delay_Init();

    USART_Printf_Init(115200);
    printf("OpenBMC CH32V307 KVM HID bridge\r\n");
    printf("SystemClk:%lu ChipID:%08lx\r\n", (unsigned long)SystemCoreClock,
           (unsigned long)DBGMCU_GetCHIPID());

    KVM_Bridge_Init(KVM_UART_BAUDRATE);
    KVM_Timer_Init();

    USBHS_RCC_Init();
    USBHS_Device_Init(ENABLE);

    while (1)
    {
        KVM_Bridge_Poll();
    }
}
