/**
 * Simplest possible firmware - uses bootloader's UART config as-is
 * 
 * Strategy:
 * - NO clock configuration
 * - NO UART configuration  
 * - NO GPIO configuration (except LED)
 * - Just use whatever the bootloader set up
 * - Blink LED + send 'U' via bootloader's UART
 */
#include "stm32f10x.h"

void delay(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

int main(void) {
    /* Wait for bootloader to fully release */
    delay(500000);
    
    /* Configure LED (PB13) - push-pull output */
    /* Only touch GPIOB, don't touch RCC - assume bootloader enabled clocks */
    RCC->APB2ENR |= RCC_APB2ENR_IOPBEN;
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);      /* 50MHz push-pull */
    GPIOB->BSRR = GPIO_BSRR_BS13;   /* LED off */
    
    /* Blink LED 3 times to confirm boot */
    for (int i = 0; i < 3; i++) {
        GPIOB->BSRR = GPIO_BSRR_BR13;  /* ON */
        delay(200000);
        GPIOB->BSRR = GPIO_BSRR_BS13;  /* OFF */
        delay(200000);
    }
    
    /* Main loop: LED blink + UART output */
    /* Use bootloader's UART config directly - do NOT reconfigure */
    uint32_t counter = 0;
    while (1) {
        /* Toggle LED every ~500ms */
        delay(500000);
        if (GPIOB->ODR & GPIO_ODR_ODR13) {
            GPIOB->BSRR = GPIO_BSRR_BR13;  /* ON */
        } else {
            GPIOB->BSRR = GPIO_BSRR_BS13;  /* OFF */
        }
        
        counter++;
        
        /* Send 'U' every ~1s */
        if (counter % 2 == 0) {
            /* Use bootloader's UART - just check TXE and send */
            while (!(USART1->SR & USART_SR_TXE));
            USART1->DR = 'U';
        }
    }
    
    return 0;
}