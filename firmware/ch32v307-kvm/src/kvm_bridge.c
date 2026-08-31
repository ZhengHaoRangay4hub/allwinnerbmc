#include "ch32v30x_usbhs_device.h"
#include "kvm_bridge.h"
#include "kvm_protocol.h"

#include <string.h>

volatile uint8_t KB_LED_Last_Status = 0;
volatile uint8_t KB_LED_Cur_Status = 0;

static volatile uint32_t bridgeMillis;
static volatile uint32_t lastValidFrameMillis;
static volatile uint8_t linkSeen;
static volatile uint8_t failsafeSent;

static volatile uint8_t keyboardPending;
static volatile uint8_t pointerPending;
static volatile uint8_t keyboardReport[KVM_KEYBOARD_REPORT_SIZE];
static volatile uint8_t pointerReport[KVM_POINTER_REPORT_SIZE];

typedef struct
{
    uint8_t state;
    uint8_t version;
    uint8_t type;
    uint8_t sequence;
    uint8_t length;
    uint8_t offset;
    uint8_t payload[KVM_MAX_PAYLOAD_SIZE];
    uint16_t crc;
    uint16_t receivedCrc;
} KvmParser;

static KvmParser parser;

void USART1_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM3_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));

static uint16_t crc16Update(uint16_t crc, uint8_t value)
{
    uint8_t bit;

    crc ^= (uint16_t)value << 8;
    for (bit = 0; bit < 8; ++bit)
    {
        crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                              : (uint16_t)(crc << 1);
    }
    return crc;
}

static void queueReleaseAll(void)
{
    memset((void*)keyboardReport, 0, sizeof(keyboardReport));
    memset((void*)pointerReport, 0, sizeof(pointerReport));
    keyboardPending = 1;
    pointerPending = 1;
}

static void acceptFrame(void)
{
    uint8_t i;

    if (parser.version != KVM_PROTOCOL_VERSION)
    {
        return;
    }

    if (parser.type == KVM_PACKET_KEYBOARD &&
        parser.length == KVM_KEYBOARD_REPORT_SIZE)
    {
        for (i = 0; i < KVM_KEYBOARD_REPORT_SIZE; ++i)
        {
            keyboardReport[i] = parser.payload[i];
        }
        keyboardPending = 1;
    }
    else if (parser.type == KVM_PACKET_POINTER &&
             parser.length == KVM_POINTER_REPORT_SIZE)
    {
        for (i = 0; i < KVM_POINTER_REPORT_SIZE; ++i)
        {
            pointerReport[i] = parser.payload[i];
        }
        pointerPending = 1;
    }
    else if (parser.type == KVM_PACKET_RELEASE_ALL && parser.length == 0)
    {
        queueReleaseAll();
    }
    else if (parser.type != KVM_PACKET_HEARTBEAT || parser.length != 0)
    {
        return;
    }

    lastValidFrameMillis = bridgeMillis;
    linkSeen = 1;
    failsafeSent = 0;
}

static void parseByte(uint8_t value)
{
    switch (parser.state)
    {
        case 0:
            if (value == KVM_FRAME_MAGIC0)
            {
                parser.state = 1;
            }
            break;
        case 1:
            if (value == KVM_FRAME_MAGIC1)
            {
                parser.state = 2;
                parser.crc = 0xFFFFu;
            }
            else
            {
                parser.state = (value == KVM_FRAME_MAGIC0) ? 1 : 0;
            }
            break;
        case 2:
            parser.version = value;
            parser.crc = crc16Update(parser.crc, value);
            parser.state = 3;
            break;
        case 3:
            parser.type = value;
            parser.crc = crc16Update(parser.crc, value);
            parser.state = 4;
            break;
        case 4:
            parser.sequence = value;
            parser.crc = crc16Update(parser.crc, value);
            parser.state = 5;
            break;
        case 5:
            parser.length = value;
            parser.offset = 0;
            parser.crc = crc16Update(parser.crc, value);
            if (value > KVM_MAX_PAYLOAD_SIZE)
            {
                parser.state = 0;
            }
            else
            {
                parser.state = (value == 0) ? 7 : 6;
            }
            break;
        case 6:
            parser.payload[parser.offset++] = value;
            parser.crc = crc16Update(parser.crc, value);
            if (parser.offset == parser.length)
            {
                parser.state = 7;
            }
            break;
        case 7:
            parser.receivedCrc = value;
            parser.state = 8;
            break;
        case 8:
            parser.receivedCrc |= (uint16_t)value << 8;
            if (parser.receivedCrc == parser.crc)
            {
                acceptFrame();
            }
            parser.state = 0;
            break;
        default:
            parser.state = 0;
            break;
    }
}

void KVM_Bridge_Init(uint32_t baudrate)
{
    GPIO_InitTypeDef gpio = {0};
    USART_InitTypeDef usart = {0};
    NVIC_InitTypeDef nvic = {0};

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_USART1,
                           ENABLE);

    gpio.GPIO_Pin = GPIO_Pin_9;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOA, &gpio);

    gpio.GPIO_Pin = GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &gpio);

    usart.USART_BaudRate = baudrate;
    usart.USART_WordLength = USART_WordLength_8b;
    usart.USART_StopBits = USART_StopBits_1;
    usart.USART_Parity = USART_Parity_No;
    usart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    usart.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &usart);

    nvic.NVIC_IRQChannel = USART1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 1;
    nvic.NVIC_IRQChannelSubPriority = 1;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);

    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
    USART_Cmd(USART1, ENABLE);
}

void KVM_Timer_Init(void)
{
    TIM_TimeBaseInitTypeDef timer = {0};
    NVIC_InitTypeDef nvic = {0};

    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3, ENABLE);
    timer.TIM_Period = 999;
    timer.TIM_Prescaler = (uint16_t)(SystemCoreClock / 1000000u - 1u);
    timer.TIM_ClockDivision = TIM_CKD_DIV1;
    timer.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseInit(TIM3, &timer);
    TIM_ClearITPendingBit(TIM3, TIM_IT_Update);
    TIM_ITConfig(TIM3, TIM_IT_Update, ENABLE);

    nvic.NVIC_IRQChannel = TIM3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 2;
    nvic.NVIC_IRQChannelSubPriority = 0;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);
    TIM_Cmd(TIM3, ENABLE);
}

void USART1_IRQHandler(void)
{
    if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
    {
        parseByte((uint8_t)USART_ReceiveData(USART1));
    }
}

void TIM3_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM3, TIM_IT_Update) != RESET)
    {
        ++bridgeMillis;
        TIM_ClearITPendingBit(TIM3, TIM_IT_Update);
    }
}

static void sendPendingKeyboard(void)
{
    uint8_t report[KVM_KEYBOARD_REPORT_SIZE];

    __disable_irq();
    if (!keyboardPending)
    {
        __enable_irq();
        return;
    }
    memcpy(report, (const void*)keyboardReport, sizeof(report));
    keyboardPending = 0;
    __enable_irq();

    if (USBHS_Endp_DataUp(DEF_UEP1, report, sizeof(report),
                          DEF_UEP_CPY_LOAD) != READY)
    {
        __disable_irq();
        if (!keyboardPending)
        {
            memcpy((void*)keyboardReport, report, sizeof(report));
            keyboardPending = 1;
        }
        __enable_irq();
    }
}

static void sendPendingPointer(void)
{
    uint8_t report[KVM_POINTER_REPORT_SIZE];

    __disable_irq();
    if (!pointerPending)
    {
        __enable_irq();
        return;
    }
    memcpy(report, (const void*)pointerReport, sizeof(report));
    pointerPending = 0;
    __enable_irq();

    if (USBHS_Endp_DataUp(DEF_UEP2, report, sizeof(report),
                          DEF_UEP_CPY_LOAD) != READY)
    {
        __disable_irq();
        if (!pointerPending)
        {
            memcpy((void*)pointerReport, report, sizeof(report));
            pointerPending = 1;
        }
        __enable_irq();
    }
}

void KVM_Bridge_Poll(void)
{
    uint32_t now = bridgeMillis;

    if (linkSeen && !failsafeSent &&
        (uint32_t)(now - lastValidFrameMillis) >= KVM_LINK_TIMEOUT_MS)
    {
        __disable_irq();
        queueReleaseAll();
        failsafeSent = 1;
        __enable_irq();
    }

    if (USBHS_DevEnumStatus)
    {
        sendPendingKeyboard();
        sendPendingPointer();
    }
}

void USB_Sleep_Wakeup_CFG(void)
{}

void MCU_Sleep_Wakeup_Operate(void)
{}
