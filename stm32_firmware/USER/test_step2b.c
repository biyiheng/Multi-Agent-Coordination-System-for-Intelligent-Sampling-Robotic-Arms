/**
 * test_step2b: HSI 8MHz + UART 38400 + boot message (NO SysTick)
 * Same as test_step2 but without SysTick_Config
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
    /* ---- 1. Clock: HSI 8MHz ---- */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);
    RCC->CFGR &= ~RCC_CFGR_SW;
    while ((RCC->CFGR & RCC_CFGR_SWS) != 0x00);
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON);
    RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);
    RCC->CFGR |= RCC_CFGR_PPRE1_DIV2;
    
    /* ---- 2. GPIOA, USART1 ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 3. PA9 TX, PA10 RX ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    
    /* ---- 4. UART: 38400 8N1 ---- */
    USART1->CR1 &= ~USART_CR1_UE;
    USART1->BRR = 0xD0;
    USART1->CR2 = 0;
    USART1->CR3 = 0;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
    
    /* ---- 5. Small delay ---- */
    delay(500000);
    
    /* ---- 6. Boot message ---- */
    uart_puts("\r\n=== YH-K32 V1.0 ===\r\n");
    uart_puts("#SYS:BOOT,OK!\r\n");
    uart_puts("=== READY ===\r\n");
    
    /* ---- 7. Main loop ---- */
    uint32_t counter = 0;
    while (1) {
        delay(500000);  /* ~500ms @ 8MHz */
        counter++;
        
        /* Heartbeat every 10 iterations (~5s) */
        if (counter % 10 == 0) {
            uart_puts("HB\r\n");
        }
        
        /* Echo */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            uart_putc(c);
        }
    }
    
    return 0;
}