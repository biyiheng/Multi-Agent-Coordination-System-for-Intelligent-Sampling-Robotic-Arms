/**
 * Direct register-level test firmware for YH-K32 board
 * Uses HSI only (64MHz), direct UART1 register config at 115200 baud
 * No library dependencies for USART init
 */
#include "stm32f10x.h"

uint32_t SystemCoreClock = 64000000;
volatile uint32_t g_systick = 0;

/* Direct UART send using registers */
void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(const char *s) {
    while (*s) {
        uart_send_char(*s++);
    }
}

/* Hex byte to ASCII */
void uart_send_hex8(uint8_t val) {
    const char hex[] = "0123456789ABCDEF";
    uart_send_char(hex[val >> 4]);
    uart_send_char(hex[val & 0xF]);
}

void uart_send_hex32(uint32_t val) {
    uart_send_str("0x");
    for (int i = 28; i >= 0; i -= 4) {
        uart_send_char("0123456789ABCDEF"[(val >> i) & 0xF]);
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

/* HardFault handler */
void HardFault_Handler(void) {
    /* Fast blink LED */
    while (1) {
        GPIOB->BSRR = GPIO_BSRR_BR13;  /* LED on */
        for (volatile uint32_t i = 0; i < 200000; i++);
        GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED off */
        for (volatile uint32_t i = 0; i < 200000; i++);
    }
}

/* Minimal SystemInit - HSI only, 64MHz */
void SystemInit(void) {
    /* Enable HSI */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);

    /* Reset CFGR */
    RCC->CFGR = 0x00000000;

    /* FLASH: 2 wait states for >48MHz */
    FLASH->ACR |= FLASH_ACR_LATENCY_2;

    /* HCLK = SYSCLK, PCLK2 = HCLK, PCLK1 = HCLK/2 */
    RCC->CFGR |= RCC_CFGR_HPRE_DIV1 | RCC_CFGR_PPRE2_DIV1 | RCC_CFGR_PPRE1_DIV2;

    /* PLL: HSI/2 * 16 = 64MHz */
    RCC->CFGR &= ~(RCC_CFGR_PLLSRC | RCC_CFGR_PLLXTPRE | RCC_CFGR_PLLMULL);
    RCC->CFGR |= RCC_CFGR_PLLSRC_HSI_DIV2 | RCC_CFGR_PLLMULL16;

    /* Enable PLL */
    RCC->CR |= RCC_CR_PLLON;
    while ((RCC->CR & RCC_CR_PLLRDY) == 0);

    /* Switch to PLL */
    RCC->CFGR &= ~RCC_CFGR_SW;
    RCC->CFGR |= RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL);

    SystemCoreClock = 64000000;
}

int main(void) {
    /* ---- 1. SysTick (1ms) ---- */
    SysTick_Config(SystemCoreClock / 1000);

    /* ---- 2. Enable clocks ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;

    /* ---- 3. LED (PB13) - Push-pull output ---- */
    /* CRH: bits 23-20 for PB13, set to 0b0011 (50MHz push-pull) */
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);  /* 50MHz output */
    GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED off (active low) */

    /* ---- 4. UART1 TX (PA9) - Alternate function push-pull, 50MHz ---- */
    /* CRH: bits 7-4 for PA9, set to 0b1011 (50MHz AF push-pull) */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);

    /* ---- 5. UART1 RX (PA10) - Floating input ---- */
    /* CRH: bits 11-8 for PA10, set to 0b0100 (floating input) */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);

    /* ---- 6. UART1: 115200 baud, 8N1 ---- */
    /* Baud rate = PCLK2 / (16 * USARTDIV) */
    /* USARTDIV = 64000000 / (16 * 115200) = 34.72 */
    /* DIV_Mantissa = 34 = 0x22, DIV_Fraction = 0.72 * 16 = 11.5 ~= 12 = 0xC */
    /* BRR = 0x22C */
    USART1->BRR = 0x22C;  /* 34.75 -> 115200 @ 64MHz */

    /* Enable USART, TX, RX */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;

    /* ---- 7. Wait for UART to stabilize ---- */
    for (volatile uint32_t i = 0; i < 100000; i++);

    /* ---- 8. Send boot message ---- */
    uart_send_str("\r\n");
    uart_send_str("=== YH-K32 TEST FIRMWARE ===\r\n");
    uart_send_str("BOOT:OK\r\n");
    uart_send_str("CLOCK:HSI_64MHZ\r\n");
    uart_send_str("BAUD:115200\r\n");
    uart_send_str("UART:USART1_PA9_PA10\r\n");

    /* Verify clock by reading RCC_CFGR */
    uint32_t cfgr = RCC->CFGR;
    uart_send_str("CFGR=");
    uart_send_hex32(cfgr);
    uart_send_str("\r\n");

    uint32_t sws = (cfgr & RCC_CFGR_SWS) >> 2;
    uart_send_str("SWS=");
    uart_send_hex8(sws);
    uart_send_str(" (0=HSI,4=HSE,8=PLL)\r\n");

    /* Verify BRR */
    uint32_t brr = USART1->BRR;
    uart_send_str("BRR=");
    uart_send_hex32(brr);
    uart_send_str("\r\n");

    uart_send_str("=== READY ===\r\n");

    /* ---- 9. Main loop ---- */
    uint32_t last_blink = 0;
    uint32_t last_msg = 0;

    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            /* Toggle PB13 */
            if (GPIOB->ODR & GPIO_ODR_ODR13) {
                GPIOB->BSRR = GPIO_BSRR_BR13;  /* LED on */
            } else {
                GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED off */
            }
        }

        /* Echo received data */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            uart_send_char(c);
        }

        /* Heartbeat every 2 seconds */
        if ((g_systick - last_msg) >= 2000) {
            last_msg = g_systick;
            uart_send_str("HB:");
            uint32_t sec = g_systick / 1000;
            uart_send_hex32(sec);
            uart_send_str("\r\n");
        }
    }
}