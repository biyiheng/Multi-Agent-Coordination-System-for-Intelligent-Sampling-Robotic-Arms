/****************************************************************************
 *	@笔者	：	Q
 *	@日期	：	2026年7月23日
 *	@所属	：	杭州友辉科技
 *	@功能	：	UART应用层实现
 *           管理三个串口:
 *           - UART1 (PA9/PA10): RPi 命令通信 (115200-8-N-1)
 *           - UART2 (PA2/PA3):   OpenMV 视觉数据 (115200-8-N-1)
 *           - UART3 (PB10/PB11): 总线舵机控制 (115200-8-N-1)
 *	@函数列表:
 *	1.	void app_uart_init(void) -- 初始化所有UART
 *	2.	void app_uart1_process(void) -- 处理UART1接收数据
 *	3.	void app_uart1_send_str(u8 *s) -- UART1发送字符串
 *	4.	void app_uart1_send_response(...) -- 发送响应帧
 *	5.	void app_uart2_send_str(u8 *s) -- UART2发送命令
 *	6.	void app_uart2_process(void) -- 处理UART2接收数据
 *	7.	void app_uart3_send_str(u8 *s) -- UART3发送舵机命令
 ****************************************************************************/

#include "app_uart.h"
#include "y_usart.h"
#include <string.h>
#include <stdio.h>

/* 全局变量定义 ------------------------------------------------------------*/
u8  app_uart1_rx_buf[UART1_RX_BUF_SIZE];     /* UART1应用层接收缓冲 */
u8  app_uart2_rx_buf[UART2_RX_BUF_SIZE];     /* UART2应用层接收缓冲 */
u16 app_uart1_rx_len = 0;                    /* UART1接收数据长度 */
u16 app_uart2_rx_len = 0;                    /* UART2接收数据长度 */

/* 私有变量 ----------------------------------------------------------------*/
static u8  uart2_tx_buf[UART2_RX_BUF_SIZE];  /* UART2发送缓冲 */
static u8  uart3_tx_buf[UART3_TX_BUF_SIZE];  /* UART3发送缓冲 */

/**
  * @brief  初始化所有UART
  * @param  无
  * @返回值 无
  * @说明   依次初始化UART1/2/3，清空接收缓冲
  */
void app_uart_init(void)
{
    /* 初始化UART1 (RPi通信) - 已在 uart1_init() 中完成 */
    uart1_init(UART1_BAUDRATE);

    /* 初始化UART2 (OpenMV通信) */
    /* 注: 如uart2_init()未在驱动中实现，此处使用寄存器直接配置 */
    /* 实际工程中应在 y_usart.c 中添加 uart2_init() */

    /* 初始化UART3 (舵机通信) - 已在 uart3_init() 中完成 */
    uart3_init(UART3_BAUDRATE);

    /* 清空接收缓冲 */
    memset(app_uart1_rx_buf, 0, UART1_RX_BUF_SIZE);
    memset(app_uart2_rx_buf, 0, UART2_RX_BUF_SIZE);
    app_uart1_rx_len = 0;
    app_uart2_rx_len = 0;

    memset(uart2_tx_buf, 0, UART2_RX_BUF_SIZE);
    memset(uart3_tx_buf, 0, UART3_TX_BUF_SIZE);
}

/**
  * @brief  处理UART1接收数据
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，检查是否有完整命令帧（以'!'结尾）
  *         有完整帧时复制到应用层缓冲，交由协议解析器处理
  *         使用驱动层 uart_receive_buf 和 uart1_get_ok 标记
  */
void app_uart1_process(void)
{
    u16 len;

    /* 检查驱动层是否收到完整帧 (uart1_get_ok 最高位为1) */
    if ((uart1_get_ok & 0x8000) == 0)
    {
        return;  /* 没有完整帧 */
    }

    /* 获取接收长度 */
    len = uart1_get_ok & 0x3FFF;

    /* 复制到应用层缓冲 */
    if (len > 0 && len < UART1_RX_BUF_SIZE)
    {
        memcpy(app_uart1_rx_buf, uart_receive_buf, len);
        app_uart1_rx_len = len;
        app_uart1_rx_buf[len] = '\0';  /* 确保字符串结束 */
    }

    /* 清除驱动层接收标记，准备接收下一帧 */
    uart1_get_ok = 0;
    memset(uart_receive_buf, 0, UART_BUF_SIZE);
}

/**
  * @brief  UART1发送字符串
  * @param  s: 待发送字符串指针
  * @返回值 无
  */
void app_uart1_send_str(u8 *s)
{
    if (s == NULL) return;
    uart1_send_str(s);
}

/**
  * @brief  发送格式化的响应帧
  * @param  cmd: 命令名称 (如 "ARM", "STATUS")
  * @param  status: 状态 (如 "OK", "ERR")
  * @param  data: 附加数据 (可为NULL)
  * @返回值 无
  * @说明   格式: #<CMD>:<STATUS>[,<DATA>]!\r\n
  */
void app_uart1_send_response(const char *cmd, const char *status, const char *data)
{
    char buf[UART1_RX_BUF_SIZE];

    if (cmd == NULL || status == NULL) return;

    if (data != NULL)
    {
        snprintf(buf, sizeof(buf), "#%s:%s,%s!\r\n", cmd, status, data);
    }
    else
    {
        snprintf(buf, sizeof(buf), "#%s:%s!\r\n", cmd, status);
    }

    uart1_send_str((u8 *)buf);
}

/**
  * @brief  UART2发送命令到OpenMV
  * @param  s: 待发送字符串指针
  * @返回值 无
  * @说明   OpenMV接收格式: #<CMD>!\r\n
  *         注: 需要在 y_usart.c 中实现 uart2_send_str()
  */
void app_uart2_send_str(u8 *s)
{
    if (s == NULL) return;

    /* 构建命令帧: #<CMD>!\r\n */
    snprintf((char *)uart2_tx_buf, sizeof(uart2_tx_buf), "#%s!\r\n", s);

    /* 发送到UART2 (PA2 TX) */
    /* 实际工程中调用 uart2_send_str(uart2_tx_buf) */
    /* 此处使用直接寄存器操作作为示例 */
    u8 *p = uart2_tx_buf;
    while (*p)
    {
        /* 等待发送完成 */
        while (USART_GetFlagStatus(USART2, USART_FLAG_TXE) == RESET);
        USART_SendData(USART2, *p++);
    }
}

/**
  * @brief  处理UART2接收数据
  * @param  无
  * @返回值 无
  * @说明   从OpenMV接收视觉数据，格式: #<CMD>:<JSON_DATA>!\r\n
  *         接收完成后转发给协议解析器
  */
void app_uart2_process(void)
{
    /* UART2接收在USART2_IRQHandler中处理 */
    /* 此处检查是否有完整帧并转发 */

    /* 注: 实际实现需在 y_usart.c 中添加UART2接收中断处理 */
    /* 类似于UART1的接收逻辑，使用独立缓冲 */
}

/**
  * @brief  UART3发送舵机命令
  * @param  s: 待发送舵机命令字符串
  * @返回值 无
  * @说明   直接调用驱动层 uart3_send_str()
  *         舵机命令格式: #XXXPYYYYTZZZZ!
  */
void app_uart3_send_str(u8 *s)
{
    if (s == NULL) return;
    uart3_send_str(s);
}

/**
  * @brief  检查UART1是否有数据等待处理
  * @param  无
  * @返回值 1: 有数据, 0: 无数据
  */
u8 app_uart1_data_ready(void)
{
    return (app_uart1_rx_len > 0) ? 1 : 0;
}

/**
  * @brief  检查UART2是否有数据等待处理
  * @param  无
  * @返回值 1: 有数据, 0: 无数据
  */
u8 app_uart2_data_ready(void)
{
    return (app_uart2_rx_len > 0) ? 1 : 0;
}

/**
  * @brief  清空UART1接收缓冲
  * @param  无
  * @返回值 无
  */
void app_uart1_flush(void)
{
    memset(app_uart1_rx_buf, 0, UART1_RX_BUF_SIZE);
    app_uart1_rx_len = 0;
}

/**
  * @brief  清空UART2接收缓冲
  * @param  无
  * @返回值 无
  */
void app_uart2_flush(void)
{
    memset(app_uart2_rx_buf, 0, UART2_RX_BUF_SIZE);
    app_uart2_rx_len = 0;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/