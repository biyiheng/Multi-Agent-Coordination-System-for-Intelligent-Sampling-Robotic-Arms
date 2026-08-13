/**
 * YH-K32 机械臂固件 V2 - 稳定版
 * 
 * 配置: HSI 8MHz, UART 38400 8N1
 * 不使用 SysTick (避免崩溃), 不使用标准库字符串函数
 * 手动实现所有解析逻辑
 */
#include "stm32f10x.h"

/* ================================================================
 * 硬件抽象层
 * ================================================================ */

/* 忙等待延时 @ 8MHz */
void delay_loops(uint32_t count) {
    for (volatile uint32_t i = 0; i < count; i++);
}

/* ~1ms 延时 (校准值 @ 8MHz) */
void delay_ms(uint32_t ms) {
    while (ms--) {
        delay_loops(1600);  /* ~1600 cycles/ms @ 8MHz */
    }
}

/* UART 发送单字符 */
void uart_putc(char c) {
    while (!(USART1->SR & USART_SR_TXE));
    USART1->DR = c;
}

/* UART 发送字符串 */
void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

/* UART 发送十进制数字 */
void uart_putdec(uint32_t n) {
    char buf[12];
    int i = 10;
    buf[11] = '\0';
    if (n == 0) { uart_putc('0'); return; }
    while (n > 0 && i >= 0) {
        buf[i--] = '0' + (n % 10);
        n /= 10;
    }
    uart_puts(&buf[i+1]);
}

/* ================================================================
 * 初始化
 * ================================================================ */

void clock_init(void) {
    /* 设置向量表偏移到 Flash */
    *(volatile uint32_t *)0xE000ED08 = 0x08000000;
    
    /* 确保 HSI 启用 */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);
    
    /* 切换到 HSI */
    RCC->CFGR &= ~RCC_CFGR_SW;
    while ((RCC->CFGR & RCC_CFGR_SWS) != 0x00);
    
    /* 禁用 PLL 和 HSE */
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON);
    
    /* APB2 = HCLK = 8MHz, APB1 = HCLK/2 = 4MHz */
    RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);
    RCC->CFGR |= RCC_CFGR_PPRE1_DIV2;
}

void uart_init(void) {
    /* 使能 GPIOA, USART1, AFIO */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* PA9: TX - AF 推挽, 50MHz */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);
    
    /* PA10: RX - 浮空输入 */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    
    /* UART: 38400 8N1 @ 8MHz */
    /* BRR = 8MHz/(16*38400) = 13.02 → mantissa=13, fraction=0 → BRR=0xD0 */
    USART1->CR1 &= ~USART_CR1_UE;  /* 必须先禁用 USART */
    USART1->BRR = 0xD0;
    USART1->CR2 = 0;
    USART1->CR3 = 0;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE;  /* 8N1 + RXNE 中断 */
    
    /* NVIC 使能 USART1 中断 (IRQ=37 → ISER1 bit 5) */
    *(volatile uint32_t *)0xE000E104 = (1 << 5);
}

void led_init(void) {
    RCC->APB2ENR |= RCC_APB2ENR_IOPBEN;
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);
    GPIOB->BSRR = GPIO_BSRR_BS13;  /* PB13 灭 */
}

/* ================================================================
 * 协议解析 (手动实现，不依赖 string.h/stdio.h)
 * ================================================================ */

#define CMD_BUF_SIZE 256
static char cmd_buf[CMD_BUF_SIZE];
static uint16_t cmd_len = 0;
static volatile uint8_t cmd_ready = 0;  /* 命令就绪标志 */
static uint8_t in_multi = 0;            /* 是否在多位机命令 { } 中 */

/* UART RXNE 中断处理 */
void USART1_IRQHandler(void) {
    if (USART1->SR & USART_SR_RXNE) {
        char c = (char)(USART1->DR & 0xFF);
        
        /* 忽略换行符 */
        if (c == '\r' || c == '\n') return;
        
        if (c == '!') {
            /* 帧结束 */
            if (cmd_len < CMD_BUF_SIZE - 1) {
                cmd_buf[cmd_len++] = c;
                cmd_buf[cmd_len] = '\0';
            }
            if (!in_multi) {
                cmd_ready = 1;  /* 单命令: 立即触发处理 */
            }
        }
        else if (c == '{') {
            in_multi = 1;
            cmd_len = 0;
        }
        else if (c == '}') {
            /* 多命令结束，批量触发处理 */
            in_multi = 0;
            if (cmd_len > 0) {
                cmd_buf[cmd_len] = '\0';
                cmd_ready = 1;
            }
        }
        else {
            if (cmd_len < CMD_BUF_SIZE - 1) {
                cmd_buf[cmd_len++] = c;
            }
        }
    }
}

/* 字符串比较 (限制长度) */
int str_match(const char *a, const char *b, int maxlen) {
    int i = 0;
    while (i < maxlen && a[i] && b[i]) {
        if (a[i] != b[i]) return 0;
        i++;
    }
    return (i == maxlen) ? 1 : (a[i] == b[i]);
}

/* 字符串长度 */
int str_len(const char *s) {
    int i = 0;
    while (s[i]) i++;
    return i;
}

/* 解析整数 (从字符串中提取) */
int parse_int(const char *s, int *pos, int *value) {
    int v = 0;
    int started = 0;
    while (s[*pos] >= '0' && s[*pos] <= '9') {
        v = v * 10 + (s[*pos] - '0');
        (*pos)++;
        started = 1;
    }
    *value = v;
    return started;
}

/* 解析舵机命令 #NNNPNNNNTNNNN! */
void handle_servo_cmd(const char *cmd) {
    int pos = 1;  /* skip '#' */
    int id, target, time_ms;
    
    if (!parse_int(cmd, &pos, &id)) return;
    if (cmd[pos] != 'P') return;
    pos++;
    if (!parse_int(cmd, &pos, &target)) return;
    if (cmd[pos] != 'T') return;
    pos++;
    if (!parse_int(cmd, &pos, &time_ms)) return;
    if (cmd[pos] != '!') return;
    
    /* 响应 */
    uart_puts("#SERVO:");
    uart_putdec(id);
    uart_puts(",POS=");
    uart_putdec(target);
    uart_puts(",TIME=");
    uart_putdec(time_ms);
    uart_puts(",OK!\r\n");
}

/* 解析系统命令 */
void handle_sys_cmd(const char *cmd) {
    if (str_match(cmd, "#SYS:BOOT!", 10)) {
        uart_puts("#SYS:BOOT,OK!\r\n");
    }
    else if (str_match(cmd, "#SYS:INFO!", 10)) {
        uart_puts("#SYS:INFO,NAME=YH-K32_ARM,VER=2.0,CLK=HSI_8MHz,UART=38400_8N1!\r\n");
    }
    else if (str_match(cmd, "#SYS:PING!", 10)) {
        uart_puts("#SYS:PONG!\r\n");
    }
    else if (str_match(cmd, "#SYS:STATUS!", 12)) {
        uart_puts("#SYS:STATUS,OK!\r\n");
    }
    else {
        uart_puts("#ERR:UNKNOWN_CMD!\r\n");
    }
}

/* 处理接收到的完整命令 */
void process_command(const char *cmd) {
    if (cmd[0] == '\0') return;
    
    /* 去除尾部 \r\n */
    int len = str_len(cmd);
    while (len > 0 && (cmd[len-1] == '\r' || cmd[len-1] == '\n')) {
        len--;
    }
    if (len == 0) return;
    
    if (cmd[0] == '#') {
        if (cmd[1] == 'S' && cmd[2] == 'Y' && cmd[3] == 'S' && cmd[4] == ':') {
            handle_sys_cmd(cmd);
        } else if (cmd[1] >= '0' && cmd[1] <= '9') {
            handle_servo_cmd(cmd);
        } else {
            uart_puts("#ERR:UNKNOWN!\r\n");
        }
    } else if (cmd[0] == '$') {
        if (str_match(cmd, "$DST!", 5)) {
            uart_puts("#SYS:STOP,OK!\r\n");
        } else if (str_match(cmd, "$RST!", 5)) {
            uart_puts("#SYS:RESET,OK!\r\n");
        } else {
            uart_puts("#ERR:UNKNOWN_SYS!\r\n");
        }
    }
}

/* ================================================================
 * 主函数
 * ================================================================ */

int main(void) {
    /* 1. 硬件初始化 */
    clock_init();
    led_init();
    uart_init();
    
    /* 2. 延时等待硬件稳定 */
    delay_loops(500000);
    
    /* 3. LED 闪烁 3 次 */
    for (int i = 0; i < 3; i++) {
        GPIOB->BSRR = GPIO_BSRR_BR13;  /* 亮 */
        delay_ms(200);
        GPIOB->BSRR = GPIO_BSRR_BS13;  /* 灭 */
        delay_ms(200);
    }
    
    /* 4. 发送启动消息 */
    uart_puts("\r\n=== YH-K32 ARM CONTROLLER V2.0 ===\r\n");
    uart_puts("#SYS:BOOT,OK!\r\n");
    uart_puts("#SYS:INFO,CLK=HSI_8MHz,UART=38400_8N1!\r\n");
    uart_puts("=== READY ===\r\n");
    
    /* 5. 主循环 */
    uint32_t ticks = 0;
    uint32_t led_state = 0;
    
    while (1) {
        /* 约 1ms 延时作为基本节拍 */
        delay_loops(1600);
        ticks++;
        
        /* LED 心跳 1Hz (500 ticks = 500ms @ 1ms/tick) */
        if (ticks % 500 == 0) {
            led_state = !led_state;
            if (led_state) {
                GPIOB->BSRR = GPIO_BSRR_BR13;
            } else {
                GPIOB->BSRR = GPIO_BSRR_BS13;
            }
        }
        
        /* 心跳消息 每 5s (5000 ticks) */
        if (ticks % 5000 == 0) {
            uart_puts("#SYS:HB,");
            uart_putdec(ticks / 1000);
            uart_puts("s!\r\n");
        }
        
        /* 中断驱动的命令处理 (RXNE 中断自动缓冲字符) */
        if (cmd_ready) {
            /* 临界区: 禁用 RXNE 中断，防止缓冲区被修改 */
            USART1->CR1 &= ~USART_CR1_RXNEIE;
            cmd_ready = 0;
            
            /* 处理单命令或多命令缓冲区 (以 '!' 分隔) */
            int i = 0;
            while (cmd_buf[i]) {
                if (cmd_buf[i] == '#' || cmd_buf[i] == '$') {
                    int start = i;
                    while (cmd_buf[i] && cmd_buf[i] != '!') i++;
                    if (cmd_buf[i] == '!') {
                        i++;
                        char save = cmd_buf[i];
                        cmd_buf[i] = '\0';
                        process_command(&cmd_buf[start]);
                        cmd_buf[i] = save;
                    }
                } else {
                    i++;
                }
            }
            cmd_len = 0;
            
            /* 重新启用 RXNE 中断 */
            USART1->CR1 |= USART_CR1_RXNEIE;
        }
    }
    
    return 0;
}