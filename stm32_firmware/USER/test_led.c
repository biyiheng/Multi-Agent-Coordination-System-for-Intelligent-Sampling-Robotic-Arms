/**
 * LED Blink Test Firmware for YH-K32
 * 
 * PB13 = LED (active low)
 * PA9  = UART1 TX
 * 
 * Strategy:
 * 1. Use startup_minimal.s (no SystemInit, no __libc_init_array)
 * 2. Don't touch clock - use bootloader's config (HSI 8MHz)
 * 3. Configure PB13 as output, blink LED
 * 4. Configure UART1 at 115200 8N1, send boot message
 */
#include "stm32f10x.h"

/* Simple delay */
void delay(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

/* Direct UART TX */
void uart_putc(char c) {
    while (!(USART1->SR & USART_SR_TXE));
    USART1->DR = c;
}

void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

int main(void) {
    uint32_t pclk2 = 8000000;  /* Bootloader uses HSI 8MHz */
    
    /* ---- 1. Enable GPIO clocks ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 2. Configure LED (PB13) - push-pull output ---- */
    GPIOB->CRH &= ~(0xF << 20);     /* Clear PB13 config */
    GPIOB->CRH |= (0x3 << 20);      /* 50MHz push-pull output */
    GPIOB->BSRR = GPIO_BSRR_BS13;   /* LED off (active low) */
    
    /* ---- 3. Configure UART1 TX (PA9) - AF push-pull ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);       /* 50MHz AF push-pull */
    
    /* ---- 4. Configure UART1 RX (PA10) - floating input ---- */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);       /* Floating input */
    
    /* ---- 5. UART1: 115200 baud @ 8MHz ---- */
    /* CRITICAL: Must disable USART before writing BRR! */
    USART1->CR1 &= ~USART_CR1_UE;
    USART1->BRR = 0x45;
    USART1->CR2 = 0;
    USART1->CR3 = 0;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
    
    /* ---- 6. Send boot message ---- */
    delay(500000);
    uart_puts("\r\n=== YH-K32 LED TEST ===\r\n");
    uart_puts("BOOT:OK\r\n");
    uart_puts("LED:BLINK_1HZ\r\n");
    uart_puts("=== READY ===\r\n");
    
    /* ---- 7. Main loop: blink LED 1Hz, heartbeat 2s ---- */
    uint32_t counter = 0;
    while (1) {
        /* Toggle LED every ~500ms */
        delay(500000);
        if (GPIOB->ODR & GPIO_ODR_ODR13) {
            GPIOB->BSRR = GPIO_BSRR_BR13;  /* LED ON */
        } else {
            GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED OFF */
        }
        
        /* Heartbeat every ~2s */
        counter++;
        if (counter % 4 == 0) {
            uart_puts("HB\r\n");
        }
    }
    
    return 0;
}