/**
  ******************************************************************************
  * @file    USER/stm32f10x_it.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   中断服务程序
  *          智能采样机械臂系统 - 所有外设和异常中断处理
  *          - UART1 IRQ: 接收树莓派命令数据
  *          - UART2 IRQ: 接收OpenMV视觉数据
  *          - UART3 IRQ: 接收总线舵机响应
  *          - SysTick IRQ: 1ms系统滴答
  *          - TIM2 IRQ: 舵机控制定时(20ms周期)
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "main.h"
#include "stm32f10x_it.h"

/* 外部变量声明 ----------------------------------------------------------------*/
extern volatile uint32_t g_systick;			/* 系统滴答计数器 */

/* 私有变量 --------------------------------------------------------------------*/

/* UART1接收缓冲区 */
static uint8_t uart1_rx_buf[512];				/* UART1接收缓冲区 */
static uint16_t uart1_rx_index = 0;				/* UART1接收索引 */
static uint8_t uart1_rx_complete = 0;			/* UART1接收完成标志 */

/* UART2接收缓冲区 */
static uint8_t uart2_rx_buf[256];				/* UART2接收缓冲区 */
static uint16_t uart2_rx_index = 0;				/* UART2接收索引 */
static uint8_t uart2_rx_complete = 0;			/* UART2接收完成标志 */

/* UART3接收缓冲区 */
static uint8_t uart3_rx_buf[128];				/* UART3接收缓冲区 */
static uint16_t uart3_rx_index = 0;				/* UART3接收索引 */
static uint8_t uart3_rx_complete = 0;			/* UART3接收完成标志 */

/* 定时器变量 */
static volatile uint32_t tim2_counter = 0;		/* TIM2计数器 */

/* Cortex-M3处理器异常处理 ----------------------------------------------------*/

/**
  * @brief  NMI异常处理
  * @param  无
  * @返回值 无
  */
void NMI_Handler(void)
{
	/* 不可屏蔽中断处理 */
}

/**
  * @brief  硬件错误异常处理
  * @param  无
  * @返回值 无
  */
void HardFault_Handler(void)
{
	/* 硬件错误，进入死循环 */
	while (1)
	{
		/* 硬件错误指示: LED常亮 */
	}
}

/**
  * @brief  内存管理异常处理
  * @param  无
  * @返回值 无
  */
void MemManage_Handler(void)
{
	/* 内存管理错误，进入死循环 */
	while (1)
	{
	}
}

/**
  * @brief  总线错误异常处理
  * @param  无
  * @返回值 无
  */
void BusFault_Handler(void)
{
	/* 总线错误，进入死循环 */
	while (1)
	{
	}
}

/**
  * @brief  用法错误异常处理
  * @param  无
  * @返回值 无
  */
void UsageFault_Handler(void)
{
	/* 用法错误，进入死循环 */
	while (1)
	{
	}
}

/**
  * @brief  SVC异常处理
  * @param  无
  * @返回值 无
  */
void SVC_Handler(void)
{
	/* 系统服务调用 */
}

/**
  * @brief  调试监视器异常处理
  * @param  无
  * @返回值 无
  */
void DebugMon_Handler(void)
{
	/* 调试监视器 */
}

/**
  * @brief  PendSV异常处理
  * @param  无
  * @返回值 无
  */
void PendSV_Handler(void)
{
	/* 可挂起系统调用 */
}

/**
  * @brief  SysTick中断处理
  * @param  无
  * @返回值 无
  * @说明   1ms周期中断，用于系统计时
  */
void SysTick_Handler(void)
{
	/* 系统滴答计数器递增 */
	g_systick++;
}

/* STM32F10x外设中断处理 ------------------------------------------------------*/

/**
  * @brief  UART1中断处理 - 接收树莓派命令
  * @param  无
  * @返回值 无
  * @说明   接收数据，以'!'字符作为命令帧结束标志
  */
void USART1_IRQHandler(void)
{
	uint8_t data;

	/* 检查接收中断标志 */
	if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
	{
		/* 读取接收到的数据 */
		data = USART_ReceiveData(USART1);

		/* 检查是否为命令结束符 */
		if (data == '!')
		{
			/* 收到完整命令帧 */
			uart1_rx_buf[uart1_rx_index] = data;
			uart1_rx_index++;
			uart1_rx_complete = 1;
		}
		else if (uart1_rx_index < sizeof(uart1_rx_buf) - 1)
		{
			/* 存储数据 */
			uart1_rx_buf[uart1_rx_index] = data;
			uart1_rx_index++;
		}
		else
		{
			/* 缓冲区溢出，重置 */
			uart1_rx_index = 0;
		}

		/* 清除中断标志 */
		USART_ClearITPendingBit(USART1, USART_IT_RXNE);
	}

	/* 检查溢出错误 */
	if (USART_GetITStatus(USART1, USART_IT_ORE) != RESET)
	{
		/* 读取DR寄存器清除ORE标志 */
		USART_ReceiveData(USART1);
		USART_ClearITPendingBit(USART1, USART_IT_ORE);
	}
}

/**
  * @brief  UART2中断处理 - 接收OpenMV数据
  * @param  无
  * @返回值 无
  */
void USART2_IRQHandler(void)
{
	uint8_t data;

	/* 检查接收中断标志 */
	if (USART_GetITStatus(USART2, USART_IT_RXNE) != RESET)
	{
		/* 读取接收到的数据 */
		data = USART_ReceiveData(USART2);

		/* 检查是否为命令结束符 */
		if (data == '!')
		{
			uart2_rx_buf[uart2_rx_index] = data;
			uart2_rx_index++;
			uart2_rx_complete = 1;
		}
		else if (uart2_rx_index < sizeof(uart2_rx_buf) - 1)
		{
			uart2_rx_buf[uart2_rx_index] = data;
			uart2_rx_index++;
		}
		else
		{
			uart2_rx_index = 0;
		}

		USART_ClearITPendingBit(USART2, USART_IT_RXNE);
	}

	if (USART_GetITStatus(USART2, USART_IT_ORE) != RESET)
	{
		USART_ReceiveData(USART2);
		USART_ClearITPendingBit(USART2, USART_IT_ORE);
	}
}

/**
  * @brief  UART3中断处理 - 接收总线舵机响应
  * @param  无
  * @返回值 无
  */
void USART3_IRQHandler(void)
{
	uint8_t data;

	/* 检查接收中断标志 */
	if (USART_GetITStatus(USART3, USART_IT_RXNE) != RESET)
	{
		/* 读取接收到的数据 */
		data = USART_ReceiveData(USART3);

		/* 存储总线舵机响应数据 */
		if (data == '!')
		{
			uart3_rx_buf[uart3_rx_index] = data;
			uart3_rx_index++;
			uart3_rx_complete = 1;
		}
		else if (uart3_rx_index < sizeof(uart3_rx_buf) - 1)
		{
			uart3_rx_buf[uart3_rx_index] = data;
			uart3_rx_index++;
		}
		else
		{
			uart3_rx_index = 0;
		}

		USART_ClearITPendingBit(USART3, USART_IT_RXNE);
	}

	if (USART_GetITStatus(USART3, USART_IT_ORE) != RESET)
	{
		USART_ReceiveData(USART3);
		USART_ClearITPendingBit(USART3, USART_IT_ORE);
	}
}

/**
  * @brief  TIM2中断处理 - 舵机控制定时
  * @param  无
  * @返回值 无
  * @说明   20ms周期中断，用于舵机位置更新时序
  */
void TIM2_IRQHandler(void)
{
	/* 检查更新中断标志 */
	if (TIM_GetITStatus(TIM2, TIM_IT_Update) != RESET)
	{
		/* 清除中断标志 */
		TIM_ClearITPendingBit(TIM2, TIM_IT_Update);

		/* 舵机控制定时器计数 */
		tim2_counter++;
	}
}

/* UART接收数据获取函数 --------------------------------------------------------*/

/**
  * @brief  获取UART1接收数据
  * @param  buf: 输出缓冲区
  * @param  len: 输出数据长度
  * @返回值 0: 有数据, 1: 无数据
  */
uint8_t uart1_get_rx_data(char *buf, uint16_t *len)
{
	if (uart1_rx_complete)
	{
		/* 复制数据 */
		*len = uart1_rx_index;
		memcpy(buf, uart1_rx_buf, uart1_rx_index);

		/* 清除标志 */
		uart1_rx_complete = 0;
		uart1_rx_index = 0;

		return 0;
	}

	return 1;
}

/**
  * @brief  获取UART2接收数据
  * @param  buf: 输出缓冲区
  * @param  len: 输出数据长度
  * @返回值 0: 有数据, 1: 无数据
  */
uint8_t uart2_get_rx_data(char *buf, uint16_t *len)
{
	if (uart2_rx_complete)
	{
		*len = uart2_rx_index;
		memcpy(buf, uart2_rx_buf, uart2_rx_index);

		uart2_rx_complete = 0;
		uart2_rx_index = 0;

		return 0;
	}

	return 1;
}

/**
  * @brief  获取UART3接收数据
  * @param  buf: 输出缓冲区
  * @param  len: 输出数据长度
  * @返回值 0: 有数据, 1: 无数据
  */
uint8_t uart3_get_rx_data(char *buf, uint16_t *len)
{
	if (uart3_rx_complete)
	{
		*len = uart3_rx_index;
		memcpy(buf, uart3_rx_buf, uart3_rx_index);

		uart3_rx_complete = 0;
		uart3_rx_index = 0;

		return 0;
	}

	return 1;
}

/**
  * @brief  获取系统滴答计数
  * @param  无
  * @返回值 系统滴答值(ms)
  */
uint32_t get_systick(void)
{
	return g_systick;
}

#ifdef USE_FULL_ASSERT

/**
  * @brief  断言失败处理函数
  * @param  file: 源文件名
  * @param  line: 行号
  * @返回值 无
  */
void assert_failed(uint8_t* file, uint32_t line)
{
	/* 用户可以添加自己的实现来报告文件名和行号 */
	/* 例如: printf("参数错误: 文件 %s 第 %d 行\r\n", file, line) */

	/* 无限循环 */
	while (1)
	{
	}
}

#endif /* USE_FULL_ASSERT */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/