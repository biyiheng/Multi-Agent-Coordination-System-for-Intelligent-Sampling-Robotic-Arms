/**
 * Test firmware: HSI 8MHz only (same as bootloader), no PLL
 * UART1 at 115200 baud using direct register access
 */
#include "stm32f10x.h"

uint32_t SystemCoreClock = 8000000;
volatile uint32_t g_systick = 0;

void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(const char *s) {
    while (*s) uart_send_char(*s++);
}

void SysTick_Handler(void) {
    g_systick++;
}

/* Minimal SystemInit: HSI only, 8MHz, NO PLL */
void SystemInit(void) {
    /* Enable HSI */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);

    /* Reset CFGR to defaults (HSI as system clock) */
    RCC->CFGR = 0x00000000;

    /* FLASH: 0 wait states for <= 24MHz */
    FLASH->ACR &= ~FLASH_ACR_LATENCY;
    FLASH->ACR |= FLASH_ACR_LATENCY_0;

    /* HCLK = SYSCLK, PCLK2 = HCLK, PCLK1 = HCLK */
    RCC->CFGR |= RCC_CFGR_HPRE_DIV1 | RCC_CFGR_PPRE2_DIV1 | RCC_CFGR_PPRE1_DIV1;

    /* Ensure HSI is system clock */
    RCC->CFGR &= ~RCC_CFGR_SW;
    RCC->CFGR |= RCC_CFGR_SW_HSI;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_HSI);

    SystemCoreClock = 8000000;
}

int main(void) {
    /* ---- 1. SysTick (1ms) ---- */
    SysTick_Config(SystemCoreClock / 1000);

    /* ---- 2. Enable GPIOA, GPIOB, USART1, AFIO ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;

    /* ---- 3. LED (PB13) ---- */
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);  /* 50MHz push-pull */
    GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED off */

    /* ---- 4. UART1 TX (PA9): AF push-pull, 50MHz ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);

    /* ---- 5. UART1 RX (PA10): Floating input ---- */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);

    /* ---- 6. UART1: 115200 baud @ 8MHz ---- */
    /* USARTDIV = 8000000 / (16 * 115200) = 4.340 */
    /* Mantissa = 4, Fraction = 0.340 * 16 = 5.44 ~= 5 */
    /* BRR = 0x45 */
    USART1->BRR = 0x45;

    /* Enable USART, TX, RX */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;

    /* Wait for UART to stabilize */
    for (volatile uint32_t i = 0; i < 50000; i++);

    /* ---- 7. Boot message ---- */
    uart_send_str("\r\n=== HSI_8MHZ_TEST ===\r\n");
    uart_send_str("BOOT:OK\r\n");
    uart_send_str("CLK=HSI_8MHZ\r\n");
    uart_send_str("BAUD=115200\r\n");
    uart_send_str("BRR=0x45\r\n");
    uart_send_str("=== READY ===\r\n");

    /* ---- 8. Main loop: blink LED + heartbeat ---- */
    uint32_t last_blink = 0;
    uint32_t last_msg = 0;

    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            if (GPIOB->ODR & GPIO_ODR_ODR13) {
                GPIOB->BSRR = GPIO_BSRR_BR13;
            } else {
                GPIOB->BSRR = GPIO_BSRR_BS13;
            }
        }

        /* Echo */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            uart_send_char(c);
        }

        /* Heartbeat every 2s */
        if ((g_systick - last_msg) >= 2000) {
            last_msg = g_systick;
            uart_send_str("HB:");
            char buf[16];
            uint32_t sec = g_systick / 1000;
            int pos = 0;
            do {
                buf[pos++] = '0' + (sec % 10);
                sec /= 10;
            } while (sec > 0);
            while (pos > 0) uart_send_char(buf[--pos]);
            uart_send_str("s\r\n");
        }
    }
}