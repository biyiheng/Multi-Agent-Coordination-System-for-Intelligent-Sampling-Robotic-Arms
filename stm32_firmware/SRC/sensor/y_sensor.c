/**
  ******************************************************************************
  * @file    SRC/sensor/y_sensor.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   传感器驱动模块实现
  *          支持传感器:
  *          - DHT11 温湿度传感器 (PA0, 单总线)
  *          - HC-SR04 超声波测距 (PB0/TRIG, PB1/ECHO)
  *          - ADC 电压监测 (PA4, ADC1通道4)
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "y_sensor.h"

/* 外部函数声明 ----------------------------------------------------------------*/
extern void delay_us(uint32_t us);				/* 微秒延时 */
extern void delay_ms(uint32_t ms);				/* 毫秒延时 */
extern uint32_t get_systick(void);				/* 获取系统滴答 */

/* GPIO引脚定义 ----------------------------------------------------------------*/

/* DHT11 数据引脚 */
#define DHT11_PORT				GPIOA
#define DHT11_PIN				GPIO_Pin_0
#define DHT11_CLOCK				RCC_APB2Periph_GPIOA

/* HC-SR04 超声波引脚 */
#define ULTRASONIC_TRIG_PORT	GPIOB
#define ULTRASONIC_TRIG_PIN		GPIO_Pin_0
#define ULTRASONIC_ECHO_PORT	GPIOB
#define ULTRASONIC_ECHO_PIN		GPIO_Pin_1
#define ULTRASONIC_CLOCK		RCC_APB2Periph_GPIOB

/* ADC 电压监测引脚 */
#define ADC_VOLTAGE_PORT		GPIOA
#define ADC_VOLTAGE_PIN			GPIO_Pin_4
#define ADC_VOLTAGE_CHANNEL		ADC_Channel_4
#define ADC_VOLTAGE_ADC			ADC1

/* 宏定义 ----------------------------------------------------------------------*/
#define DHT11_TIMEOUT			10000		/* DHT11通信超时(us) */
#define ULTRASONIC_TIMEOUT		30000		/* 超声波超时(us) */
#define ADC_VREF				3.3f		/* ADC参考电压(V) */
#define ADC_RESOLUTION			4095.0f		/* ADC分辨率(12位) */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  传感器数据实例
  */
sensor_data_t sensor_data = {
	.temperature = 0.0f,
	.humidity    = 0.0f,
	.distance    = 0.0f,
	.voltage     = 0.0f,
	.timestamp   = 0
};

/* 私有变量 --------------------------------------------------------------------*/
static uint8_t  dht11_data[5];					/* DHT11数据缓冲区 */
static uint32_t ultrasonic_start_time;			/* 超声波测距开始时间 */
static uint8_t  sensor_init_done = 0;			/* 初始化完成标志 */

/* 私有函数声明 ----------------------------------------------------------------*/
static void dht11_gpio_config(void);
static void dht11_set_output(void);
static void dht11_set_input(void);
static uint8_t dht11_read_byte(void);
static uint8_t dht11_read_data(void);
static void ultrasonic_gpio_config(void);
static void adc_voltage_config(void);

/**
  * @brief  传感器模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化所有传感器的GPIO和ADC
  */
void sensor_init(void)
{
	/* 初始化DHT11温湿度传感器 */
	dht11_gpio_config();

	/* 初始化HC-SR04超声波传感器 */
	ultrasonic_gpio_config();

	/* 初始化ADC电压监测 */
	adc_voltage_config();

	/* 标记初始化完成 */
	sensor_init_done = 1;

	/* 首次读取所有传感器数据 */
	sensor_read_all();
}

/**
  * @brief  DHT11 GPIO配置
  * @param  无
  * @返回值 无
  */
static void dht11_gpio_config(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	/* 使能GPIOA时钟 */
	RCC_APB2PeriphClockCmd(DHT11_CLOCK, ENABLE);

	/* 配置PA0为推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = DHT11_PIN;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(DHT11_PORT, &GPIO_InitStructure);

	/* 初始输出高电平 */
	GPIO_SetBits(DHT11_PORT, DHT11_PIN);
}

/**
  * @brief  设置DHT11引脚为输出模式
  * @param  无
  * @返回值 无
  */
static void dht11_set_output(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	GPIO_InitStructure.GPIO_Pin   = DHT11_PIN;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(DHT11_PORT, &GPIO_InitStructure);
}

/**
  * @brief  设置DHT11引脚为输入模式
  * @param  无
  * @返回值 无
  */
static void dht11_set_input(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	GPIO_InitStructure.GPIO_Pin   = DHT11_PIN;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_IPU;
	GPIO_Init(DHT11_PORT, &GPIO_InitStructure);
}

/**
  * @brief  读取DHT11一个字节
  * @param  无
  * @返回值 读取到的字节数据
  */
static uint8_t dht11_read_byte(void)
{
	uint8_t i, byte = 0;
	uint32_t timeout;

	for (i = 0; i < 8; i++)
	{
		byte <<= 1;

		/* 等待低电平结束 */
		timeout = 0;
		while (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_RESET)
		{
			timeout++;
			if (timeout > DHT11_TIMEOUT)
			{
				return 0;
			}
		}

		/* 延时30us后判断电平 */
		delay_us(30);

		/* 如果仍为高电平，则该位为1 */
		if (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_SET)
		{
			byte |= 0x01;
		}

		/* 等待高电平结束 */
		timeout = 0;
		while (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_SET)
		{
			timeout++;
			if (timeout > DHT11_TIMEOUT)
			{
				return 0;
			}
		}
	}

	return byte;
}

/**
  * @brief  读取DHT11数据
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   遵循DHT11单总线通信协议读取温湿度数据
  */
static uint8_t dht11_read_data(void)
{
	uint32_t timeout;
	uint8_t  checksum;

	/* 主机发送起始信号: 拉低至少18ms */
	dht11_set_output();
	GPIO_ResetBits(DHT11_PORT, DHT11_PIN);
	delay_ms(20);

	/* 拉高20~40us */
	GPIO_SetBits(DHT11_PORT, DHT11_PIN);
	delay_us(30);

	/* 切换为输入模式，等待DHT11响应 */
	dht11_set_input();

	/* 等待DHT11拉低(响应信号) */
	timeout = 0;
	while (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_SET)
	{
		timeout++;
		if (timeout > DHT11_TIMEOUT)
		{
			return 1;	/* 超时失败 */
		}
	}

	/* 等待DHT11拉高(响应结束) */
	timeout = 0;
	while (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_RESET)
	{
		timeout++;
		if (timeout > DHT11_TIMEOUT)
		{
			return 1;
		}
	}

	/* 等待DHT11拉低(准备发送数据) */
	timeout = 0;
	while (GPIO_ReadInputDataBit(DHT11_PORT, DHT11_PIN) == Bit_SET)
	{
		timeout++;
		if (timeout > DHT11_TIMEOUT)
		{
			return 1;
		}
	}

	/* 读取5字节数据: 湿度整数、湿度小数、温度整数、温度小数、校验和 */
	dht11_data[0] = dht11_read_byte();	/* 湿度整数 */
	dht11_data[1] = dht11_read_byte();	/* 湿度小数 */
	dht11_data[2] = dht11_read_byte();	/* 温度整数 */
	dht11_data[3] = dht11_read_byte();	/* 温度小数 */
	dht11_data[4] = dht11_read_byte();	/* 校验和 */

	/* 校验数据 */
	checksum = dht11_data[0] + dht11_data[1] + dht11_data[2] + dht11_data[3];
	if (checksum != dht11_data[4])
	{
		return 1;	/* 校验失败 */
	}

	return 0;	/* 成功 */
}

/**
  * @brief  读取温度值
  * @param  无
  * @返回值 温度值(摄氏度)
  * @说明   从DHT11读取温度数据
  */
float sensor_read_temp(void)
{
	if (dht11_read_data() == 0)
	{
		/* DHT11温度范围: 0~50摄氏度 */
		sensor_data.temperature = (float)dht11_data[2] + (float)dht11_data[3] * 0.1f;
	}
	else
	{
		/* 读取失败，保持上次值 */
	}

	return sensor_data.temperature;
}

/**
  * @brief  读取湿度值
  * @param  无
  * @返回值 湿度值(%RH)
  * @说明   从DHT11读取湿度数据
  */
float sensor_read_humidity(void)
{
	if (dht11_read_data() == 0)
	{
		/* DHT11湿度范围: 20~90%RH */
		sensor_data.humidity = (float)dht11_data[0] + (float)dht11_data[1] * 0.1f;
	}

	return sensor_data.humidity;
}

/**
  * @brief  HC-SR04 GPIO配置
  * @param  无
  * @返回值 无
  */
static void ultrasonic_gpio_config(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	/* 使能GPIOB时钟 */
	RCC_APB2PeriphClockCmd(ULTRASONIC_CLOCK, ENABLE);

	/* 配置PB0(TRIG)为推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = ULTRASONIC_TRIG_PIN;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(ULTRASONIC_TRIG_PORT, &GPIO_InitStructure);

	/* 配置PB1(ECHO)为浮空输入 */
	GPIO_InitStructure.GPIO_Pin  = ULTRASONIC_ECHO_PIN;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(ULTRASONIC_ECHO_PORT, &GPIO_InitStructure);

	/* TRIG初始低电平 */
	GPIO_ResetBits(ULTRASONIC_TRIG_PORT, ULTRASONIC_TRIG_PIN);
}

/**
  * @brief  读取距离值
  * @param  无
  * @返回值 距离值(cm)
  * @说明   从HC-SR04超声波传感器读取距离
  *         测量原理: 发送10us触发脉冲，测量ECHO高电平持续时间
  *         距离 = (高电平时间 * 声速) / 2
  *         声速约340m/s = 0.034cm/us
  */
float sensor_read_distance(void)
{
	uint32_t echo_time = 0;
	uint32_t timeout;

	/* 发送10us触发脉冲 */
	GPIO_SetBits(ULTRASONIC_TRIG_PORT, ULTRASONIC_TRIG_PIN);
	delay_us(10);
	GPIO_ResetBits(ULTRASONIC_TRIG_PORT, ULTRASONIC_TRIG_PIN);

	/* 等待ECHO引脚变为高电平 */
	timeout = 0;
	while (GPIO_ReadInputDataBit(ULTRASONIC_ECHO_PORT, ULTRASONIC_ECHO_PIN) == Bit_RESET)
	{
		timeout++;
		if (timeout > ULTRASONIC_TIMEOUT)
		{
			sensor_data.distance = 0.0f;
			return 0.0f;	/* 超时，无回波 */
		}
	}

	/* 记录高电平开始时间 */
	ultrasonic_start_time = get_systick();

	/* 等待ECHO引脚变为低电平 */
	timeout = 0;
	while (GPIO_ReadInputDataBit(ULTRASONIC_ECHO_PORT, ULTRASONIC_ECHO_PIN) == Bit_SET)
	{
		timeout++;
		if (timeout > ULTRASONIC_TIMEOUT)
		{
			sensor_data.distance = 0.0f;
			return 0.0f;	/* 超时 */
		}
	}

	/* 计算高电平持续时间(us) */
	echo_time = timeout;

	/* 计算距离: 距离(cm) = 时间(us) * 0.034 / 2 */
	sensor_data.distance = (float)echo_time * 0.017f;

	return sensor_data.distance;
}

/**
  * @brief  ADC电压监测配置
  * @param  无
  * @返回值 无
  */
static void adc_voltage_config(void)
{
	GPIO_InitTypeDef  GPIO_InitStructure;
	ADC_InitTypeDef   ADC_InitStructure;

	/* 使能GPIOA和ADC1时钟 */
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_ADC1, ENABLE);

	/* 配置PA4为模拟输入 */
	GPIO_InitStructure.GPIO_Pin  = ADC_VOLTAGE_PIN;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AIN;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* ADC配置 */
	ADC_InitStructure.ADC_Mode               = ADC_Mode_Independent;
	ADC_InitStructure.ADC_ScanConvMode       = DISABLE;
	ADC_InitStructure.ADC_ContinuousConvMode = DISABLE;
	ADC_InitStructure.ADC_ExternalTrigConv   = ADC_ExternalTrigConv_None;
	ADC_InitStructure.ADC_DataAlign          = ADC_DataAlign_Right;
	ADC_InitStructure.ADC_NbrOfChannel       = 1;
	ADC_Init(ADC1, &ADC_InitStructure);

	/* 配置ADC时钟分频 */
	RCC_ADCCLKConfig(RCC_PCLK2_Div6);

	/* 使能ADC1 */
	ADC_Cmd(ADC1, ENABLE);

	/* ADC校准 */
	ADC_ResetCalibration(ADC1);
	while (ADC_GetResetCalibrationStatus(ADC1));

	ADC_StartCalibration(ADC1);
	while (ADC_GetCalibrationStatus(ADC1));
}

/**
  * @brief  读取电压值
  * @param  无
  * @返回值 电压值(V)
  * @说明   从ADC1通道4读取电压，PA4输入
  *         假设使用分压电路，实际电压 = ADC值 * VREF / 4096 * 分压比
  */
float sensor_read_voltage(void)
{
	uint16_t adc_value;

	/* 配置ADC通道 */
	ADC_RegularChannelConfig(ADC1, ADC_VOLTAGE_CHANNEL, 1, ADC_SampleTime_55Cycles5);

	/* 启动ADC转换 */
	ADC_SoftwareStartConvCmd(ADC1, ENABLE);

	/* 等待转换完成 */
	while (!ADC_GetFlagStatus(ADC1, ADC_FLAG_EOC));

	/* 读取ADC值 */
	adc_value = ADC_GetConversionValue(ADC1);

	/* 转换为电压值 (假设2倍分压: 实际电压 = ADC读数 * VREF / 4096 * 2) */
	sensor_data.voltage = (float)adc_value * ADC_VREF / ADC_RESOLUTION * 2.0f;

	return sensor_data.voltage;
}

/**
  * @brief  读取所有传感器数据
  * @param  无
  * @返回值 无
  * @说明   一次性读取所有传感器数据并更新sensor_data结构体
  */
void sensor_read_all(void)
{
	/* 读取温湿度 */
	sensor_read_temp();

	/* 读取距离 */
	sensor_read_distance();

	/* 读取电压 */
	sensor_read_voltage();

	/* 记录时间戳 */
	sensor_data.timestamp = get_systick();
}

/**
  * @brief  获取传感器数据指针
  * @param  无
  * @返回值 传感器数据指针
  */
sensor_data_t* sensor_get_data(void)
{
	return &sensor_data;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/