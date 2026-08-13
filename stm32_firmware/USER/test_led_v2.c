/**
 * LED Blink Test Firmware v2 for YH-K32
 * 
 * Uses EXACT SAME UART config as bootloader:
 * - 115200 baud, 8 data bits, EVEN parity, 1 stop bit (8E1)
 * - HSI 8MHz clock
 * 
 * PB13 = LED (active low)
 * PA9  = UART1 TX
 * PA10 = UART1 RX
 */
#include "stm32f10x.h"

void delay(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

void uart_putc(char c) {
    while (!(USART1->SR & USART_SR_TXE));
    USART1->DR = c;
}

void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

int main(void) {
    /* ---- 1. Enable GPIO and UART clocks ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 2. Configure LED (PB13) - push-pull output ---- */
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);      /* 50MHz push-pull output */
    GPIOB->BSRR = GPIO_BSRR_BS13;   /* LED off */
    
    /* ---- 3. Configure UART1 TX (PA9) - AF push-pull ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);       /* 50MHz AF push-pull */
    
    /* ---- 4. Configure UART1 RX (PA10) - floating input ---- */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);       /* Floating input */
    
    /* ---- 5. UART1: 115200 8E1 @ 8MHz ---- */
    /* CRITICAL: Must disable USART before writing BRR! */
    USART1->CR1 &= ~USART_CR1_UE;  /* UE = 0, disable USART */
    
    /* BRR = 0x45 for 115200 @ 8MHz */
    USART1->BRR = 0x45;
    
    /* CR2: 1 stop bit (default) */
    USART1->CR2 = 0;
    
    /* CR3: no flow control */
    USART1->CR3 = 0;
    
    /* CR1: UE + TE + RE + PCE (even parity) + M (8 bits) */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE | USART_CR1_PCE;
    
    /* ---- 6. Small delay then send boot message ---- */
    delay(500000);
    
    /* First blink LED 3 times quickly to confirm firmware is running */
    for (int i = 0; i < 3; i++) {
        GPIOB->BSRR = GPIO_BSRR_BR13;  /* LED ON */
        delay(200000);
        GPIOB->BSRR = GPIO_BSRR_BS13;  /* LED OFF */
        delay(200000);
    }
    
    uart_puts("\r\n=== YH-K32 LED TEST V2 ===\r\n");
    uart_puts("BOOT:OK\r\n");
    uart_puts("LED:3BLINK_DONE\r\n");
    uart_puts("UART:8E1_115200\r\n");
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
        
        /* Heartbeat every 2s */
        counter++;
        if (counter % 4 == 0) {
            uart_puts("HB\r\n");
        }
        
        /* Echo received data */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            uart_putc(c);  /* Echo */
        }
    }
    
    return 0;
}