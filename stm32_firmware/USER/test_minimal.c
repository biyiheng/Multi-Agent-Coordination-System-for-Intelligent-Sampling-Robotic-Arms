/**
 * Minimal test firmware for YH-K32 board
 * Uses HSI only (no HSE dependency), UART1 at 115200 baud
 * LED blink (PB13) + UART heartbeat
 */
#include "stm32f10x.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"
#include "stm32f10x_usart.h"

uint32_t SystemCoreClock = 64000000;
volatile uint32_t g_systick = 0;

/* Simple UART send using registers (bypasses library baud calc) */
void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(const char *s) {
    while (*s) {
        uart_send_char(*s++);
    }
}

/* Delay using SysTick */
void delay_ms(uint32_t ms) {
    uint32_t start = g_systick;
    while ((g_systick - start) < ms);
}

/* SysTick handler */
void SysTick_Handler(void) {
    g_systick++;
}

/* HardFault handler - blink LED rapidly */
void HardFault_Handler(void) {
    while (1) {
        /* Fast blink to indicate fault */
        GPIO_ResetBits(GPIOB, GPIO_Pin_13);
        for (volatile uint32_t i = 0; i < 200000; i++);
        GPIO_SetBits(GPIOB, GPIO_Pin_13);
        for (volatile uint32_t i = 0; i < 200000; i++);
    }
}

/* Minimal SystemInit - force HSI only */
void SystemInit(void) {
    /* Reset RCC */
    RCC->CR |= (uint32_t)0x00000001;
    RCC->CFGR &= (uint32_t)0xF8FF0000;
    RCC->CR &= (uint32_t)0xFEF6FFFF;
    RCC->CIR = 0x009F0000;

    /* FLASH 2 wait states (for >48MHz) */
    FLASH->ACR |= FLASH_ACR_LATENCY_2;

    /* HCLK = SYSCLK, PCLK2 = HCLK, PCLK1 = HCLK/2 */
    RCC->CFGR |= (uint32_t)(RCC_CFGR_HPRE_DIV1 | RCC_CFGR_PPRE2_DIV1 | RCC_CFGR_PPRE1_DIV2);

    /* Use HSI only: PLL source = HSI/2, multiplier = x16 -> 64MHz */
    RCC->CFGR &= ~((uint32_t)(RCC_CFGR_PLLSRC | RCC_CFGR_PLLXTPRE | RCC_CFGR_PLLMULL));
    RCC->CFGR |= (uint32_t)(RCC_CFGR_PLLSRC_HSI_DIV2 | RCC_CFGR_PLLMULL16);

    /* Enable PLL */
    RCC->CR |= RCC_CR_PLLON;
    while ((RCC->CR & RCC_CR_PLLRDY) == 0);

    /* Select PLL as system clock */
    RCC->CFGR &= ~((uint32_t)RCC_CFGR_SW);
    RCC->CFGR |= (uint32_t)RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & (uint32_t)RCC_CFGR_SWS) != (uint32_t)0x08);

    SystemCoreClock = 64000000;
}

int main(void) {
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef usart;

    /* ---- 1. SysTick (1ms) ---- */
    SysTick_Config(SystemCoreClock / 1000);

    /* ---- 2. Enable clocks ---- */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB |
                           RCC_APB2Periph_USART1 | RCC_APB2Periph_AFIO, ENABLE);

    /* ---- 3. LED (PB13) ---- */
    gpio.GPIO_Pin = GPIO_Pin_13;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOB, &gpio);
    GPIO_SetBits(GPIOB, GPIO_Pin_13);  /* LED off */

    /* ---- 4. UART1 TX (PA9) ---- */
    gpio.GPIO_Pin = GPIO_Pin_9;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &gpio);

    /* ---- 5. UART1 RX (PA10) ---- */
    gpio.GPIO_Pin = GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &gpio);

    /* ---- 6. UART1 @ 115200 ---- */
    usart.USART_BaudRate = 115200;
    usart.USART_WordLength = USART_WordLength_8b;
    usart.USART_StopBits = USART_StopBits_1;
    usart.USART_Parity = USART_Parity_No;
    usart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    usart.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &usart);
    USART_Cmd(USART1, ENABLE);

    /* ---- 7. Boot message ---- */
    delay_ms(100);  /* Wait for UART to stabilize */

    uart_send_str("\r\n#TEST:BOOT,OK! CLK=");

    /* Send SystemCoreClock as hex */
    uint32_t clk = SystemCoreClock;
    const char hex[] = "0123456789ABCDEF";
    for (int i = 28; i >= 0; i -= 4) {
        uart_send_char(hex[(clk >> i) & 0xF]);
    }
    uart_send_str("\r\n");

    uart_send_str("#TEST:FIRMWARE=MINIMAL,BAUD=115200,HSI=ONLY\r\n");

    /* ---- 8. Main loop ---- */
    uint32_t last_blink = 0;
    uint32_t last_msg = 0;

    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            if (GPIO_ReadOutputDataBit(GPIOB, GPIO_Pin_13)) {
                GPIO_ResetBits(GPIOB, GPIO_Pin_13);  /* LED on */
            } else {
                GPIO_SetBits(GPIOB, GPIO_Pin_13);    /* LED off */
            }
        }

        /* Echo any received data */
        if (USART_GetFlagStatus(USART1, USART_FLAG_RXNE) != RESET) {
            char c = (char)USART_ReceiveData(USART1);
            /* Echo back */
            uart_send_char(c);
        }

        /* Heartbeat every 2 seconds */
        if ((g_systick - last_msg) >= 2000) {
            last_msg = g_systick;
            uart_send_str("#TEST:HEARTBEAT! UPTIME=");
            /* Simple uptime in seconds */
            uint32_t sec = g_systick / 1000;
            char buf[16];
            int pos = 0;
            if (sec == 0) {
                buf[pos++] = '0';
            } else {
                char tmp[16];
                int tpos = 0;
                while (sec > 0) {
                    tmp[tpos++] = '0' + (sec % 10);
                    sec /= 10;
                }
                while (tpos > 0) buf[pos++] = tmp[--tpos];
            }
            buf[pos] = '\0';
            uart_send_str(buf);
            uart_send_str("\r\n");
        }
    }
}