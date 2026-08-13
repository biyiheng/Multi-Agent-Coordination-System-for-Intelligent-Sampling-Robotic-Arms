/****************************************************************************
 *	@笔者	：	Q
 *	@日期	：	2026年7月24日
 *	@所属	：	杭州友辉科技
 *	@功能	：	UART底层驱动 - 提供各串口的初始化、收发缓冲管理
 *           UART1: RPi 命令通信
 *           UART2: OpenMV 视觉数据
 *           UART3: 总线舵机控制
 *	@函数列表:
 *	1.	void uart1_init(uint32_t baudrate) -- 初始化UART1
 *	2.	void uart3_init(uint32_t baudrate) -- 初始化UART3
 *	3.	void uart1_receive_run(void) -- UART1接收处理
 ****************************************************************************/

#include "y_usart.h"
#include "app_uart.h"
#include <string.h>

/* UART接收缓冲区大小 */
#define UART_BUF_SIZE  256

/* 全局变量定义 ------------------------------------------------------------*/
u8  uart_receive_buf[UART_BUF_SIZE];     /* UART驱动层接收缓冲区 */
u16 uart1_get_ok = 0;                     /* UART1接收状态标记 (bit15=完成, bit13-0=长度) */

/**
  * @brief  初始化UART1 (RPi通信)
  * @param  baudrate: 波特率
  * @返回值 无
  */
void uart1_init(uint32_t baudrate)
{
    USART_InitTypeDef USART_InitStructure;

    /* 使能UART1时钟 */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);

    /* 配置UART1参数 */
    USART_InitStructure.USART_BaudRate            = baudrate;
    USART_InitStructure.USART_WordLength          = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits            = USART_StopBits_1;
    USART_InitStructure.USART_Parity              = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode                = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &USART_InitStructure);

    /* 使能UART1接收中断 */
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

    /* 使能UART1 */
    USART_Cmd(USART1, ENABLE);

    /* 清空接收缓冲 */
    memset(uart_receive_buf, 0, UART_BUF_SIZE);
    uart1_get_ok = 0;
}

/**
  * @brief  初始化UART3 (舵机通信)
  * @param  baudrate: 波特率
  * @返回值 无
  */
void uart3_init(uint32_t baudrate)
{
    USART_InitTypeDef USART_InitStructure;

    /* 使能UART3时钟 */
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);

    /* 配置UART3参数 */
    USART_InitStructure.USART_BaudRate            = baudrate;
    USART_InitStructure.USART_WordLength          = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits            = USART_StopBits_1;
    USART_InitStructure.USART_Parity              = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode                = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART3, &USART_InitStructure);

    /* 使能UART3 */
    USART_Cmd(USART3, ENABLE);
}