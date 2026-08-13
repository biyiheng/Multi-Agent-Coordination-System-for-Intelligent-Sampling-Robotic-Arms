/**
 * Minimal test: HSI 8MHz + UART 38400 8N1
 * Just sends 'U' repeatedly - no string functions, no SysTick
 */
#include "stm32f10x.h"

void delay(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

int main(void) {
    /* ---- 1. Enable HSI (should already be on from bootloader) ---- */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);
    
    /* ---- 2. Switch system clock to HSI ---- */
    RCC->CFGR &= ~RCC_CFGR_SW;
    while ((RCC->CFGR & RCC_CFGR_SWS) != 0x00);
    
    /* ---- 3. Disable PLL and HSE ---- */
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON);
    
    /* ---- 4. Set APB2 = HCLK (no prescaler), APB1 = HCLK/2 ---- */
    RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);
    RCC->CFGR |= RCC_CFGR_PPRE1_DIV2;
    
    /* ---- 5. Enable GPIOA, USART1, AFIO ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 6. PA9: TX - AF push-pull, 50MHz ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);
    
    /* ---- 7. PA10: RX - floating input ---- */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    
    /* ---- 8. UART: 38400 8N1 @ 8MHz ---- */
    USART1->CR1 &= ~USART_CR1_UE;  /* Disable USART first */
    USART1->BRR = 0xD0;            /* BRR = 13.0 → 8MHz/(16*13) = 38461 */
    USART1->CR2 = 0;               /* 1 stop bit */
    USART1->CR3 = 0;               /* No flow control */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;  /* 8N1, enable */
    
    /* ---- 9. Small delay ---- */
    delay(500000);
    
    /* ---- 10. Main loop: send 'U' every ~500ms ---- */
    while (1) {
        /* Send 'U' */
        while (!(USART1->SR & USART_SR_TXE));
        USART1->DR = 'U';
        
        delay(500000);
    }
    
    return 0;
}