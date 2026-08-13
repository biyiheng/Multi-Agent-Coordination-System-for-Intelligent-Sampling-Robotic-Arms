/**
  ******************************************************************************
  * @file    USER/main.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   主程序入口 - 智能采样机械臂系统
  *          基于STM32F103C8T6微控制器
  *
  *          系统架构:
  *          - UART1(PA9/PA10): 树莓派通信，接收高层命令
  *          - UART2(PA2/PA3):  OpenMV通信，视觉数据采集
  *          - UART3(PB10/PB11): 总线舵机控制
  *
  *          舵机配置:
  *          - ID0: 底盘(ZX20D)
  *          - ID1: 肩关节(ZX15D)
  *          - ID2: 肘关节1(ZX15D)
  *          - ID3: 肘关节2(ZX15D)
  *          - ID4: 腕关节(ZX15S)
  *          - ID5: 夹爪(ZX15S)
  *
  *          按键功能:
  *          - Key1(PA8): 紧急停止
  *          - Key2(PA11): 返回原点
  *
  *          LED(PB13):
  *          - 正常: 1Hz心跳闪烁
  *          - 警告: 5Hz快闪
  *          - 错误: 常亮
  *          - 急停: 快速双闪
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "main.h"
#include "stm32f10x_it.h"

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  系统滴答计数器(ms)
  *          由SysTick中断每1ms递增
  */
volatile uint32_t g_systick = 0;

/**
  * @brief  系统运行状态
  */
sys_state_t g_sys_state = SYS_STATE_INIT;

/* 私有变量 --------------------------------------------------------------------*/

/* 按键状态变量 */
static uint8_t key1_last_state = 1;			/* Key1上次状态(上拉=1) */
static uint8_t key2_last_state = 1;			/* Key2上次状态 */
static uint32_t key1_press_time = 0;		/* Key1按下时间 */
static uint32_t key2_press_time = 0;		/* Key2按下时间 */
static uint8_t key1_long_press = 0;			/* Key1长按标志 */
static uint8_t key2_long_press = 0;			/* Key2长按标志 */

/* LED心跳变量 */
static uint32_t led_heartbeat_time = 0;		/* LED心跳闪烁时间 */

/* 系统运行时间 */
static uint32_t system_start_time = 0;		/* 系统启动时间 */

/* 私有函数声明 ----------------------------------------------------------------*/
static void system_init(void);
static void led_heartbeat(void);
static void key_scan(void);
static void key_process(void);

/**
  * @brief  主函数
  * @param  无
  * @返回值 无
  * @说明   系统入口，初始化所有模块后进入主循环
  */
int main(void)
{
	/* 系统初始化 */
	system_init();

	/* 记录系统启动时间 */
	system_start_time = g_systick;

	/* 主循环 */
	while (1)
	{
		/* LED心跳指示 */
		led_heartbeat();

		/* 按键扫描 */
		key_scan();

		/* 按键处理 */
		key_process();

		/* 协议解析运行 */
		app_protocol_run();

		/* 机械臂控制运行 */
		app_arm_run();

		/* 动作组运行 */
		ag_run();

		/* 安全监控 */
		safety_monitor();

		/* 工业级升级模块: 编码器采样 + CAN 收发 (S1/S2) */
		io_upgrade_run();
	}
}

/**
  * @brief  系统初始化
  * @param  无
  * @返回值 无
  * @说明   按顺序初始化所有模块:
  *         时钟 -> SysTick -> GPIO -> 看门狗 -> 串口 -> 舵机 ->
  *         传感器 -> 安全 -> Flash -> 配置 -> 动作组 -> 协议 -> 机械臂
  */
static void system_init(void)
{
	/* 1. 系统时钟配置 (72MHz) - SystemInit()已在启动时完成 */
		/* 注: SystemInit() 使用长超时检测HSE, 比rcc_config()更可靠 */
		/*     如需重新配置时钟，使用 rcc_config() */

	/* 2. SysTick配置 (1ms中断) */
	SysTick_Config(SystemCoreClock / SYSTICK_FREQ_HZ);

	/* 3. NVIC中断优先级配置 */
	nvic_config();

	/* 4. GPIO初始化 */
	gpio_init();

	/* 5. LED初始化 */
	led_init();

	/* 6. 蜂鸣器初始化 */
	beep_init();

	/* 7. 按键初始化 */
	key_init();

	/* 8. 延时初始化 */
	delay_init();

	/* 9. 串口初始化 */
	uart_init();

	/* 10. 总线舵机初始化 */
	bus_servo_init();

	/* 11. 传感器初始化 */
	sensor_init();

	/* 12. 安全模块初始化 */
	safety_init();

	/* 13. Flash存储初始化 */
	flash_init();

	/* 14. 系统配置初始化 */
	app_config_init();

	/* 15. 动作组管理初始化 */
	ag_init();

	/* 16. 协议解析器初始化 */
	app_protocol_init();

	/* 17. 机械臂控制初始化 */
		app_arm_init();

	/* 18. 编码器初始化 (工业级升级 S1: AS5048 绝对值编码器, SPI1) */
		encoder_init();

	/* 19. CAN 通信层初始化 (工业级升级 S2: 1Mbps + CRC32 + 重发) */
		can_init();

	/* 更新系统状态 */
		g_sys_state = SYS_STATE_IDLE;

	/* 发送启动消息 */
		uart1_send_str("#SYS:BOOT,OK!\r\n");
}

/**
  * @brief  工业级升级模块周期运行
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用, 驱动编码器采样与 CAN 收发 (S1/S2)
  */
void io_upgrade_run(void)
{
	float joint_angle = 0.0f;
	uint32_t rx_id = 0;
	uint8_t  rx_data[CAN_MAX_DATA];
	uint8_t  rx_len = 0;

	/* 编码器闭环采样: 读取当前关节绝对角度 (若初始化成功) */
	if (encoder_get_data()->initialized)
	{
		encoder_read_angle(&joint_angle);
	}

	/* CAN 接收轮询 (非阻塞), 丢弃返回码以保持主循环非阻塞 */
	can_receive(&rx_id, rx_data, &rx_len);
}

/**
  * @brief  系统时钟配置
  * @param  无
  * @返回值 无
  * @说明   配置HSE外部晶振(8MHz) -> PLL x9 -> 72MHz系统时钟
  */
void rcc_config(void)
{
	ErrorStatus HSEStartUpStatus;

	/* 复位RCC寄存器 */
	RCC_DeInit();

	/* 使能HSE外部高速晶振 */
	RCC_HSEConfig(RCC_HSE_ON);

	/* 等待HSE就绪 */
	HSEStartUpStatus = RCC_WaitForHSEStartUp();

	/* 配置Flash预取缓冲和等待周期 */
	FLASH_PrefetchBufferCmd(FLASH_PrefetchBuffer_Enable);
	FLASH_SetLatency(FLASH_Latency_2);

	/* 配置AHB(HCLK) = SYSCLK */
	RCC_HCLKConfig(RCC_SYSCLK_Div1);

	/* 配置APB2(PCLK2) = HCLK */
	RCC_PCLK2Config(RCC_HCLK_Div1);

	/* 配置APB1(PCLK1) = HCLK/2 */
	RCC_PCLK1Config(RCC_HCLK_Div2);

	if (HSEStartUpStatus == SUCCESS)
		{
			/* HSE OK: PLL = HSE * 9 = 72MHz */
			RCC_PLLConfig(RCC_PLLSource_HSE_Div1, RCC_PLLMul_9);
			SystemCoreClock = 72000000;
		}
		else
		{
			/* HSE failed: fallback to HSI, PLL = HSI/2 * 16 = 64MHz */
			RCC_HSEConfig(RCC_HSE_OFF);
			RCC_PLLConfig(RCC_PLLSource_HSI_Div2, RCC_PLLMul_16);
			SystemCoreClock = 64000000;
		}

	/* 使能PLL */
	RCC_PLLCmd(ENABLE);

	/* 等待PLL就绪 */
	while (RCC_GetFlagStatus(RCC_FLAG_PLLRDY) == RESET)
	{
	}

	/* 选择PLL作为系统时钟源 */
	RCC_SYSCLKConfig(RCC_SYSCLKSource_PLLCLK);

	/* 等待切换完成 */
	while (RCC_GetSYSCLKSource() != 0x08)
	{
	}
}

/**
  * @brief  NVIC中断优先级配置
  * @param  无
  * @返回值 无
  */
void nvic_config(void)
{
	NVIC_InitTypeDef NVIC_InitStructure;

	/* 设置优先级分组: 2位抢占优先级, 2位子优先级 */
	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);

	/* 配置UART1中断 */
	NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	/* 配置UART2中断 */
	NVIC_InitStructure.NVIC_IRQChannel = USART2_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	/* 配置UART3中断 */
	NVIC_InitStructure.NVIC_IRQChannel = USART3_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	/* 配置TIM2中断 */
	NVIC_InitStructure.NVIC_IRQChannel = TIM2_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);
}

/**
  * @brief  GPIO初始化
  * @param  无
  * @返回值 无
  * @说明   初始化所有GPIO引脚:
  *         LED(PB13), 蜂鸣器(PB12), 按键(PA8/PA11)
  *         串口引脚, 传感器引脚
  */
void gpio_init(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	/* 使能GPIO时钟 */
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB |
	                       RCC_APB2Periph_GPIOC | RCC_APB2Periph_AFIO, ENABLE);

	/* 配置LED引脚(PB13) - 推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_13;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	/* 配置蜂鸣器引脚(PB12) - 推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_12;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	/* 配置按键引脚(PA8, PA11) - 上拉输入 */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_8 | GPIO_Pin_11;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_IPU;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* UART1引脚配置(PA9/TX, PA10/RX) */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_9;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_10;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* UART2引脚配置(PA2/TX, PA3/RX) */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_2;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_3;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* UART3引脚配置(PB10/TX, PB11/RX) */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_10;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_11;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	/* 初始输出状态 */
	GPIO_SetBits(GPIOB, GPIO_Pin_13);		/* LED初始灭 */
	GPIO_ResetBits(GPIOB, GPIO_Pin_12);		/* 蜂鸣器初始关 */
}

/**
  * @brief  LED初始化
  * @param  无
  * @返回值 无
  */
void led_init(void)
{
	/* 初始关闭LED */
	GPIO_SetBits(GPIOB, GPIO_Pin_13);
}

/**
  * @brief  LED控制
  * @param  state: 0=灭, 1=亮
  * @返回值 无
  */
void led_set(uint8_t state)
{
	if (state)
	{
		GPIO_ResetBits(GPIOB, GPIO_Pin_13);	/* 低电平点亮 */
	}
	else
	{
		GPIO_SetBits(GPIOB, GPIO_Pin_13);		/* 高电平熄灭 */
	}
}

/**
  * @brief  LED翻转
  * @param  无
  * @返回值 无
  */
void led_toggle(void)
{
	GPIO_WriteBit(GPIOB, GPIO_Pin_13,
		(BitAction)(1 - GPIO_ReadOutputDataBit(GPIOB, GPIO_Pin_13)));
}

/**
  * @brief  LED心跳闪烁
  * @param  无
  * @返回值 无
  * @说明   LED 1Hz心跳闪烁(500ms亮/500ms灭)
  *         仅在安全状态为OK时执行
  */
static void led_heartbeat(void)
{
	/* 只在安全模块不控制LED时执行心跳 */
	if (safety_get_status() == SAFETY_OK)
	{
		if ((g_systick - led_heartbeat_time) >= 500)
		{
			led_toggle();
			led_heartbeat_time = g_systick;
		}
	}
}

/**
  * @brief  蜂鸣器初始化
  * @param  无
  * @返回值 无
  */
void beep_init(void)
{
	/* 初始关闭蜂鸣器 */
	GPIO_ResetBits(GPIOB, GPIO_Pin_12);
}

/**
  * @brief  蜂鸣器控制
  * @param  state: 0=关, 1=开
  * @返回值 无
  */
void beep_set(uint8_t state)
{
	if (state)
	{
		GPIO_SetBits(GPIOB, GPIO_Pin_12);		/* 高电平开启 */
	}
	else
	{
		GPIO_ResetBits(GPIOB, GPIO_Pin_12);	/* 低电平关闭 */
	}
}

/**
  * @brief  按键初始化
  * @param  无
  * @返回值 无
  */
void key_init(void)
{
	/* 按键GPIO已在gpio_init()中配置 */
	/* 读取初始状态 */
	key1_last_state = GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_8);
	key2_last_state = GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_11);
}

/**
  * @brief  按键扫描
  * @param  无
  * @返回值 无
  * @说明   每10ms扫描一次按键状态，检测按下和释放
  */
void key_scan(void)
{
	uint8_t key1_state, key2_state;

	/* 读取按键当前状态 */
	key1_state = GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_8);
	key2_state = GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_11);

	/* Key1处理(PA8) - 紧急停止 */
	if (key1_state == 0 && key1_last_state == 1)
	{
		/* 按键按下 */
		key1_press_time = g_systick;
		key1_long_press = 0;
	}
	else if (key1_state == 0 && key1_last_state == 0)
	{
		/* 按键持续按下 */
		if (!key1_long_press && (g_systick - key1_press_time) >= 2000)
		{
			/* 长按2秒 */
			key1_long_press = 1;
		}
	}
	else if (key1_state == 1 && key1_last_state == 0)
	{
		/* 按键释放 */
		if (!key1_long_press)
		{
			/* 短按: 紧急停止 */
			safety_emergency_stop();
			g_sys_state = SYS_STATE_ESTOP;
		}
		else
		{
			/* 长按: 安全复位 */
			safety_reset();
			g_sys_state = SYS_STATE_IDLE;
		}
	}

	/* Key2处理(PA11) - 返回原点 */
	if (key2_state == 0 && key2_last_state == 1)
	{
		/* 按键按下 */
		key2_press_time = g_systick;
		key2_long_press = 0;
	}
	else if (key2_state == 0 && key2_last_state == 0)
	{
		/* 按键持续按下 */
		if (!key2_long_press && (g_systick - key2_press_time) >= 2000)
		{
			key2_long_press = 1;
		}
	}
	else if (key2_state == 1 && key2_last_state == 0)
	{
		/* 按键释放 */
		if (!key2_long_press)
		{
			/* 短按: 返回原点 */
			app_arm_origin();
		}
		else
		{
			/* 长按: 恢复出厂设置 */
			app_config_reset();
		}
	}

	/* 保存当前状态 */
	key1_last_state = key1_state;
	key2_last_state = key2_state;
}

/**
  * @brief  按键处理
  * @param  无
  * @返回值 无
  */
static void key_process(void)
{
	/* 预留按键处理扩展接口 */
}

/**
  * @brief  串口初始化
  * @param  无
  * @返回值 无
  * @说明   初始化UART1(115200, 树莓派), UART2(115200, OpenMV), UART3(115200, 舵机)
  */
void uart_init(void)
{
	USART_InitTypeDef USART_InitStructure;

	/* 使能USART时钟 */
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART2, ENABLE);
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);

	/* UART1配置 */
	USART_InitStructure.USART_BaudRate            = 115200;
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

	/* UART2配置 */
	USART_InitStructure.USART_BaudRate = 115200;
	USART_Init(USART2, &USART_InitStructure);

	/* 使能UART2接收中断 */
	USART_ITConfig(USART2, USART_IT_RXNE, ENABLE);

	/* 使能UART2 */
	USART_Cmd(USART2, ENABLE);

	/* UART3配置 */
	USART_InitStructure.USART_BaudRate = 115200;
	USART_Init(USART3, &USART_InitStructure);

	/* 使能UART3接收中断 */
	USART_ITConfig(USART3, USART_IT_RXNE, ENABLE);

	/* 使能UART3 */
	USART_Cmd(USART3, ENABLE);
}

/**
  * @brief  串口数据处理
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，处理各串口接收数据
  */
void uart_run(void)
{
	/* 串口接收在中断中处理，此处可扩展 */
}

/**
  * @brief  UART1发送字符串
  * @param  str: 字符串指针
  * @返回值 无
  */
void uart1_send_str(char *str)
{
	while (*str)
	{
		/* 等待发送缓冲区空 */
		while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET)
		{
		}

		/* 发送一个字符 */
		USART_SendData(USART1, *str);
		str++;
	}

	/* 等待发送完成 */
	while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET)
	{
	}
}

/**
  * @brief  UART2发送字符串
  * @param  str: 字符串指针
  * @返回值 无
  */
void uart2_send_str(char *str)
{
	while (*str)
	{
		while (USART_GetFlagStatus(USART2, USART_FLAG_TXE) == RESET)
		{
		}

		USART_SendData(USART2, *str);
		str++;
	}

	while (USART_GetFlagStatus(USART2, USART_FLAG_TC) == RESET)
	{
	}
}

/**
  * @brief  UART3发送字符串
  * @param  str: 字符串指针
  * @返回值 无
  */
void uart3_send_str(char *str)
{
	while (*str)
	{
		while (USART_GetFlagStatus(USART3, USART_FLAG_TXE) == RESET)
		{
		}

		USART_SendData(USART3, *str);
		str++;
	}

	while (USART_GetFlagStatus(USART3, USART_FLAG_TC) == RESET)
	{
	}
}

/**
  * @brief  UART1接收处理
  * @param  无
  * @返回值 无
  */
void uart1_receive_run(void)
{
	/* 接收在中断中处理，此处可扩展 */
}

/**
  * @brief  延时初始化
  * @param  无
  * @返回值 无
  */
void delay_init(void)
{
	/* 使用SysTick延时，已在system_init()中配置 */
}

/**
  * @brief  毫秒延时
  * @param  ms: 延时毫秒数
  * @返回值 无
  */
void delay_ms(uint32_t ms)
{
	uint32_t start = g_systick;

	while ((g_systick - start) < ms)
	{
		/* 等待 */
	}
}

/**
  * @brief  微秒延时
  * @param  us: 延时微秒数
  * @返回值 无
  * @说明   使用简单循环实现微秒延时(72MHz下约72个周期/us)
  */
void delay_us(uint32_t us)
{
	uint32_t i;

	for (i = 0; i < us; i++)
	{
		/* 72MHz时钟下，约72个周期 = 1us */
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
		__NOP();
	}
}

#ifdef USE_FULL_ASSERT

/**
  * @brief  断言失败处理
  * @param  file: 文件名
  * @param  line: 行号
  * @返回值 无
  */
void assert_failed(uint8_t* file, uint32_t line)
{
	/* 用户可添加日志输出 */
	/* 例如: printf("参数错误: 文件 %s 第 %d 行\r\n", file, line) */

	/* 进入无限循环 */
	while (1)
	{
	}
}

#endif /* USE_FULL_ASSERT */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/