/**
 * Test firmware for YH-K32 board
 * 
 * Strategy: 
 * 1. Detect or configure system clock (bootloader leaves it at 72MHz HSE+PLL)
 * 2. Configure UART1: 8N1, 115200 baud based on actual clock
 * 3. Sends boot message, echoes received data, blinks LED
 * 
 * Uses startup_minimal.s which skips SystemInit and __libc_init_array,
 * so we must configure the clock ourselves in main().
 */
#include "stm32f10x.h"

uint32_t SystemCoreClock = 72000000;  /* Default: bootloader HSE+PLL 72MHz */
volatile uint32_t g_systick = 0;

/* ---- UART helpers ---- */
void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(const char *s) {
    while (*s) uart_send_char(*s++);
}

void uart_send_hex32(uint32_t val) {
    uart_send_str("0x");
    for (int i = 28; i >= 0; i -= 4) {
        uart_send_char("0123456789ABCDEF"[(val >> i) & 0xF]);
    }
}

/* ---- SysTick ---- */
void SysTick_Handler(void) {
    g_systick++;
}

/* ---- SystemInit: called by startup (but startup_minimal.s skips it) ---- */
void SystemInit(void) {
    /* No-op: startup_minimal.s skips this, we configure clock in main() */
}

/* ---- main ---- */
int main(void) {
    uint32_t pclk2;
    uint32_t sw;
    
    /* ---- 1. Detect clock source from bootloader ---- */
    sw = (RCC->CFGR & RCC_CFGR_SWS) >> 2;  /* SWS bits [3:2] */
    
    /* Determine PCLK2 (USART1 clock) based on clock source */
    /* 0x00 = HSI (8MHz), 0x04 = HSE (8MHz), 0x08 = PLL (72MHz or 64MHz) */
    if (sw == 0x00) {
        /* HSI: 8MHz, no prescalers */
        pclk2 = 8000000;
        SystemCoreClock = 8000000;
    } else if (sw == 0x04) {
        /* HSE: 8MHz (external crystal) */
        pclk2 = 8000000;
        SystemCoreClock = 8000000;
    } else {
        /* PLL: check PLL source and multiplier */
        uint32_t pllsrc = (RCC->CFGR & RCC_CFGR_PLLSRC) >> 16;
        uint32_t pllmul = ((RCC->CFGR & RCC_CFGR_PLLMULL) >> 18) + 2;
        uint32_t pll_in;
        
        if (pllsrc == 0) {
            /* PLL source = HSI/2 = 4MHz */
            pll_in = 4000000;
        } else {
            /* PLL source = HSE = 8MHz (or HSE/2 if PREDIV used) */
            uint32_t pllxtpre = (RCC->CFGR & RCC_CFGR_PLLXTPRE) >> 17;
            if (pllxtpre == 0) {
                pll_in = 8000000;  /* HSE not divided */
            } else {
                pll_in = 4000000;  /* HSE/2 */
            }
        }
        
        pclk2 = pll_in * pllmul;
        SystemCoreClock = pclk2;
        
        /* Check APB2 prescaler */
        uint32_t ppre2 = (RCC->CFGR & RCC_CFGR_PPRE2) >> 11;
        if (ppre2 >= 0x04) {
            /* APB2 divided: PCLK2 = HCLK / (2^(ppre2-3)) */
            pclk2 = pclk2 >> (ppre2 - 3);
        }
    }
    
    /* ---- 2. SysTick @ 1ms ---- */
    SysTick_Config(SystemCoreClock / 1000);
    
    /* ---- 3. Enable peripheral clocks ---- */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* ---- 4. Configure LED (PB13) - push-pull output ---- */
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);   /* 50MHz push-pull output */
    GPIOB->BSRR = GPIO_BSRR_BS13; /* LED off (active low) */
    
    /* ---- 5. Configure UART1 TX (PA9) - AF push-pull, 50MHz ---- */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);    /* 50MHz AF push-pull */
    
    /* ---- 6. Configure UART1 RX (PA10) - floating input ---- */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);    /* Floating input */
    
    /* ---- 7. UART1: STM32 spec requires disable-before-config sequence ---- */
    /* Step 7a: Disable USART first (required by STM32 reference manual) */
    USART1->CR1 &= ~USART_CR1_UE;  /* UE = 0 */
    
    /* Step 7b: Calculate BRR based on actual PCLK2 */
    /* Correct formula: USARTDIV = PCLK2 / (16 * Baud) */
    /* BRR = (Mantissa << 4) | Fraction, where USARTDIV = Mantissa + Fraction/16 */
    /* Simplified: div = PCLK2 / Baud, Mantissa = div/16, Fraction = div%16 */
    uint32_t div = (pclk2 + (115200 / 2)) / 115200;  /* rounded PCLK2/Baud */
    uint32_t mantissa = div / 16;
    uint32_t fraction = div % 16;
    USART1->BRR = (mantissa << 4) | fraction;
    
    /* Step 7c: Clear CR2 and CR3 (remove bootloader's parity/stop settings) */
    USART1->CR2 = 0;
    USART1->CR3 = 0;
    
    /* Step 7d: Configure CR1: 8N1, TX+RX enabled, USART still disabled */
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE;  /* 8 bit, no parity, USART disabled */
    
    /* Step 7e: Enable USART */
    USART1->CR1 |= USART_CR1_UE;  /* UE = 1 */
    
    /* ---- 8. Wait for UART to stabilize ---- */
    for (volatile uint32_t i = 0; i < 100000; i++);
    
    /* ---- 9. Send boot message ---- */
    uart_send_str("\r\n=== YH-K32 TEST FIRMWARE ===\r\n");
    uart_send_str("BOOT:OK\r\n");
    
    uart_send_str("CLK_SRC=");
    uart_send_hex32(sw);
    if (sw == 0x00) uart_send_str("(HSI)\r\n");
    else if (sw == 0x04) uart_send_str("(HSE)\r\n");
    else if (sw == 0x08) uart_send_str("(PLL)\r\n");
    else uart_send_str("(UNKNOWN)\r\n");
    
    uart_send_str("SYSCLK=");
    uart_send_hex32(SystemCoreClock);
    uart_send_str("\r\n");
    
    uart_send_str("PCLK2=");
    uart_send_hex32(pclk2);
    uart_send_str("\r\n");
    
    uart_send_str("BRR=");
    uart_send_hex32(USART1->BRR);
    uart_send_str("\r\n");
    
    uart_send_str("=== READY ===\r\n");
    
    /* ---- 10. Main loop ---- */
    uint32_t last_blink = 0;
    uint32_t last_msg = 0;
    
    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
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
            uart_send_hex32(g_systick / 1000);
            uart_send_str("s\r\n");
        }
    }
}