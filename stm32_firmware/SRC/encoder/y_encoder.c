/**
  ******************************************************************************
  * @file    SRC/encoder/y_encoder.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   AS5048A/B 绝对值编码器驱动实现 (STM32F103 SPL 集成)
  *
  *          SPI1 全双工 16bit 读时序 (CPOL=0, CPHA=1, 模式1):
  *            1) 拉低 CSn
  *            2) 发送读命令 (reg<<1, bit14=0 表示读)
  *            3) 同时回读上一命令的响应 (全双工)
  *            4) 拉高 CSn
  *
  *          AS5048 响应分布在两次传输中: 发送命令帧后, 下一次发送 NOP 帧
  *          时回读命令帧的响应, 响应 bit14=错误标志, bit13..0=数据。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include <stddef.h>
#include "y_encoder.h"

/* 私有变量 --------------------------------------------------------------------*/
static encoder_data_t encoder_data = {
	.angle_raw   = 0,
	.angle_deg   = 0.0f,
	.error_count = 0,
	.initialized = 0
};

/* 私有函数声明 ----------------------------------------------------------------*/
static void spi1_gpio_init(void);
static void spi1_config(void);
static uint16_t spi_transfer16(uint16_t tx);
static uint8_t as5048_read_reg(uint16_t reg, uint16_t *value);
static void as5048_cs_low(void);
static void as5048_cs_high(void);

/**
  * @brief  片选拉低
  * @param  无
  * @返回值 无
  */
static void as5048_cs_low(void)
{
	GPIO_ResetBits(ENC_CS_PORT, ENC_CS_PIN);
}

/**
  * @brief  片选拉高
  * @param  无
  * @返回值 无
  */
static void as5048_cs_high(void)
{
	GPIO_SetBits(ENC_CS_PORT, ENC_CS_PIN);
}

/**
  * @brief  SPI1 引脚初始化
  * @param  无
  * @返回值 无
  * @说明   PA5(SCK)/PA7(MOSI) 复用推挽, PA6(MISO) 浮空输入, PC0(CS) 推挽输出
  */
static void spi1_gpio_init(void)
{
	GPIO_InitTypeDef GPIO_InitStructure;

	/* 使能 GPIOA/GPIOC/AFIO/SPI1 时钟 */
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
	                       RCC_APB2Periph_AFIO | RCC_APB2Periph_SPI1, ENABLE);

	/* SCK(PA5), MOSI(PA7) - 复用推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_5 | GPIO_Pin_7;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* MISO(PA6) - 浮空输入 */
	GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_6;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	/* CS(PC0) - 推挽输出, 初始高电平 (非选中) */
	GPIO_InitStructure.GPIO_Pin   = ENC_CS_PIN;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(ENC_CS_PORT, &GPIO_InitStructure);
	as5048_cs_high();
}

/**
  * @brief  SPI1 模式配置
  * @param  无
  * @返回值 无
  * @说明   主机, 16bit, CPOL=0/CPHA=1 (AS5048 模式1),
  *         72MHz/16 = 4.5MHz 时钟
  */
static void spi1_config(void)
{
	SPI_InitTypeDef SPI_InitStructure;

	SPI_InitStructure.SPI_Direction         = SPI_Direction_2Lines_FullDuplex;
	SPI_InitStructure.SPI_Mode              = SPI_Mode_Master;
	SPI_InitStructure.SPI_DataSize          = SPI_DataSize_16b;
	SPI_InitStructure.SPI_CPOL              = SPI_CPOL_Low;
	SPI_InitStructure.SPI_CPHA              = SPI_CPHA_2Edge;
	SPI_InitStructure.SPI_NSS               = SPI_NSS_Soft;
	SPI_InitStructure.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_16;
	SPI_InitStructure.SPI_FirstBit          = SPI_FirstBit_MSB;
	SPI_InitStructure.SPI_CRCPolynomial     = 7;
	SPI_Init(SPI1, &SPI_InitStructure);

	SPI_Cmd(SPI1, ENABLE);
}

/**
  * @brief  SPI1 全双工 16bit 传输
  * @param  tx: 待发送数据
  * @retval 回读数据
  */
static uint16_t spi_transfer16(uint16_t tx)
{
	/* 等待发送缓冲区空 */
	while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_TXE) == RESET)
	{
	}

	/* 发送数据 */
	SPI_I2S_SendData(SPI1, tx);

	/* 等待接收缓冲区非空 */
	while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_RXNE) == RESET)
	{
	}

	/* 回读数据 */
	return SPI_I2S_ReceiveData(SPI1);
}

/**
  * @brief  读取 AS5048 指定寄存器
  * @param  reg: 寄存器地址
  * @param  value: 输出寄存器值 (bit13..0)
  * @retval 0: 成功, 非0: 失败
  */
static uint8_t as5048_read_reg(uint16_t reg, uint16_t *value)
{
	uint16_t cmd;
	uint16_t dummy_rx;
	uint16_t data_rx;

	/* 第一次传输: 发送读命令, 回读数据无效 */
	cmd = AS5048_CMD_READ | ((reg & 0x3FFF) << 1);
	as5048_cs_low();
	dummy_rx = spi_transfer16(cmd);
	as5048_cs_high();

	/* 第二次传输: 发送 NOP 帧, 回读有效数据 */
	as5048_cs_low();
	data_rx = spi_transfer16(0x0000);
	as5048_cs_high();

	(void)dummy_rx;

	/* 检查错误标志 (bit14) */
	if (data_rx & 0x4000)
	{
		return ENC_ERR_READ;
	}

	*value = data_rx & 0x3FFF;
	return ENC_OK;
}

/**
  * @brief  编码器模块初始化
  * @param  无
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_init(void)
{
	uint16_t dummy;

	/* SPI 引脚与模式初始化 */
	spi1_gpio_init();
	spi1_config();

	/* 探测读: 验证 SPI 链路与芯片在线 */
	if (as5048_read_reg(AS5048_REG_ANGLE, &dummy) != ENC_OK)
	{
		encoder_data.error_count++;
		return ENC_ERR_INIT;
	}

	encoder_data.initialized = 1;
	encoder_data.error_count = 0;
	return ENC_OK;
}

/**
  * @brief  读取原始 14bit 值
  * @param  raw: 输出原始值 (0-16383)
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_read_raw(uint16_t *raw)
{
	uint16_t angle;
	uint16_t mag;

	if (!encoder_data.initialized || raw == NULL)
	{
		return ENC_ERR_INIT;
	}

	if (as5048_read_reg(AS5048_REG_ANGLE, &angle) != ENC_OK)
	{
		encoder_data.error_count++;
		return ENC_ERR_READ;
	}

	/* 读取磁场强度, 检测磁场异常 */
	if (as5048_read_reg(AS5048_REG_MAG, &mag) == ENC_OK)
	{
		if ((mag & (AS5048_MAG_TOO_HIGH | AS5048_MAG_TOO_LOW)) != 0)
		{
			encoder_data.error_count++;
			return ENC_ERR_MAGNETIC;
		}
	}

	encoder_data.angle_raw   = angle;
	encoder_data.error_count = 0;
	if (raw != NULL)
	{
		*raw = angle;
	}
	return ENC_OK;
}

/**
  * @brief  读取编码器绝对角度
  * @param  angle_deg: 输出角度指针 (度, 0-360)
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_read_angle(float *angle_deg)
{
	uint16_t raw;

	if (encoder_read_raw(&raw) != ENC_OK)
	{
		return ENC_ERR_READ;
	}

	encoder_data.angle_deg = (float)raw * AS5048_DEG_PER_LSB;
	if (angle_deg != NULL)
	{
		*angle_deg = encoder_data.angle_deg;
	}
	return ENC_OK;
}

/**
  * @brief  获取编码器数据
  * @param  无
  * @retval 编码器数据指针
  */
encoder_data_t* encoder_get_data(void)
{
	return &encoder_data;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/
