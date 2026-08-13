/**
 * Step-by-step test: HSI 8MHz + UART 38400 + SysTick + boot message
 * No string functions (no scanf/printf/strcmp)
 */
#include "stm32f10x.h"

volatile uint32_t g_systick = 0;
uint32_t SystemCoreClock = 8000000;

void SysTick_Handler(void) {
    g_systick++;
}

void delay(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

void delay_ms(uint32_t ms) {
    uint32_t start = g_systick;
    while ((g_systick - start) < ms);
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
    
    /* ---- 2. SysTick 1ms ---- */
    SysTick_Config(SystemCoreClock / 1000);
    
    /* ---- 3. GPIOA, USART1 ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 4. PA9 TX, PA10 RX ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    
    /* ---- 5. UART: 38400 8N1 ---- */
    USART1->CR1 &= ~USART_CR1_UE;
    USART1->BRR = 0xD0;
    USART1->CR2 = 0;
    USART1->CR3 = 0;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
    
    /* ---- 6. Small delay ---- */
    delay(500000);
    
    /* ---- 7. Boot message ---- */
    uart_puts("\r\n=== YH-K32 V1.0 ===\r\n");
    uart_puts("#SYS:BOOT,OK!\r\n");
    uart_puts("=== READY ===\r\n");
    
    /* ---- 8. Main loop: heartbeat + echo ---- */
    uint32_t last_hb = 0;
    while (1) {
        /* Heartbeat every 5s */
        if ((g_systick - last_hb) >= 5000) {
            last_hb = g_systick;
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