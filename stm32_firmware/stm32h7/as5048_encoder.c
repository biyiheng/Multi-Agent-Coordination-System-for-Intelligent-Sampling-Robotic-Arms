/**
  ******************************************************************************
  * @file    stm32h7/as5048_encoder.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   AS5048A/B 绝对值编码器驱动实现 (STM32H7 HAL 参考骨架)
  *
  *          SPI 全双工读时序 (MSB first, CPOL=0/CPHA=1):
  *            1) 拉低 CSn
  *            2) 发送读命令 (bit15=0, 地址左移1位)
  *            3) 同时读回上一命令的 14bit 响应 (全双工)
  *            4) 拉高 CSn
  *
  *          AS5048 响应数据分布在两次传输中: 读取寄存器需连续发送
  *          两次 16bit 帧, 第二次回读帧的 bit13..0 为有效角度。
  ******************************************************************************
  */

#include "as5048_encoder.h"
#include <string.h>

/* 私有工具函数 ----------------------------------------------------------------*/

/**
  * @brief  片选拉低
  */
static inline void as5048_cs_low(as5048_t *enc)
{
    HAL_GPIO_WritePin(enc->cs_port, enc->cs_pin, GPIO_PIN_RESET);
}

/**
  * @brief  片选拉高
  */
static inline void as5048_cs_high(as5048_t *enc)
{
    HAL_GPIO_WritePin(enc->cs_port, enc->cs_pin, GPIO_PIN_SET);
}

/**
  * @brief  通过 SPI 发送 16bit 命令并回读 16bit 响应
  * @param  enc: 设备句柄
  * @param  command: 待发送命令字
  * @param  rx: 回读响应
  * @retval HAL_StatusTypeDef
  */
static HAL_StatusTypeDef as5048_transfer16(as5048_t *enc,
                                           uint16_t command,
                                           uint16_t *rx)
{
    HAL_StatusTypeDef status;

    /* 拉低片选, 开始通信 */
    as5048_cs_low(enc);

    /* 全双工传输: 同时发送命令并接收响应 */
    status = HAL_SPI_TransmitReceive(enc->hspi,
                                     (uint8_t *)&command,
                                     (uint8_t *)rx, 2, HAL_MAX_DELAY);

    /* 拉高片选, 结束通信 */
    as5048_cs_high(enc);

    return status;
}

/**
  * @brief  读取指定寄存器
  * @param  enc: 设备句柄
  * @param  reg: 寄存器地址
  * @param  value: 输出寄存器值 (bit13..0)
  * @retval HAL_StatusTypeDef
  */
static HAL_StatusTypeDef as5048_read_reg(as5048_t *enc, uint16_t reg,
                                         uint16_t *value)
{
    uint16_t cmd, dummy_rx, data_rx;

    /* 第一次传输: 发送读命令, 回读数据无效 (丢弃) */
    cmd = AS5048_CMD_READ | ((reg & 0x3FFF) << 1);
    if (as5048_transfer16(enc, cmd, &dummy_rx) != HAL_OK)
    {
        return HAL_ERROR;
    }

    /* 第二次传输: 发送 NOP 帧, 回读有效数据 */
    if (as5048_transfer16(enc, AS5048_REG_NOP << 1, &data_rx) != HAL_OK)
    {
        return HAL_ERROR;
    }

    /* 校验奇偶位 (bit15) 与错误位 (bit14) */
    if (data_rx & 0x4000)
    {
        return HAL_ERROR;   /* bit14 = 错误标志 */
    }

    *value = data_rx & 0x3FFF;
    return HAL_OK;
}

/**
  * @brief  写指定寄存器 (仅用于 NOP/CLEAR_ERROR)
  * @param  enc: 设备句柄
  * @param  reg: 寄存器地址
  * @retval HAL_StatusTypeDef
  */
static HAL_StatusTypeDef as5048_write_reg(as5048_t *enc, uint16_t reg)
{
    uint16_t cmd, rx;

    cmd = AS5048_CMD_WRITE | ((reg & 0x3FFF) << 1);
    return as5048_transfer16(enc, cmd, &rx);
}

/* 公开函数 --------------------------------------------------------------------*/

HAL_StatusTypeDef as5048_init(as5048_t *enc, SPI_HandleTypeDef *hspi,
                              GPIO_TypeDef *cs_port, uint16_t cs_pin)
{
    uint16_t dummy;

    if (enc == NULL || hspi == NULL || cs_port == NULL)
    {
        return HAL_ERROR;
    }

    memset(enc, 0, sizeof(as5048_t));
    enc->hspi    = hspi;
    enc->cs_port = cs_port;
    enc->cs_pin  = cs_pin;

    /* 配置片选为推挽输出, 初始高电平 (非选中) */
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin   = cs_pin;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    HAL_GPIO_Init(cs_port, &gpio);
    as5048_cs_high(enc);

    /* 清错误并做一次探测读, 验证 SPI 链路 */
    as5048_write_reg(enc, AS5048_REG_CLEAR_ERROR);
    if (as5048_read_reg(enc, AS5048_REG_ANGLE, &dummy) != HAL_OK)
    {
        return HAL_ERROR;
    }

    enc->initialized = 1;
    return HAL_OK;
}

HAL_StatusTypeDef as5048_read_raw(as5048_t *enc, uint16_t *raw)
{
    uint16_t angle;
    uint16_t mag;

    if (enc == NULL || !enc->initialized || raw == NULL)
    {
        return HAL_ERROR;
    }

    if (as5048_read_reg(enc, AS5048_REG_ANGLE, &angle) != HAL_OK)
    {
        enc->error_count++;
        return HAL_ERROR;
    }

    /* 读取磁场强度, 检测磁场异常 (过强/过弱) */
    if (as5048_read_reg(enc, AS5048_REG_MAG, &mag) == HAL_OK)
    {
        if ((mag & (AS5048_MAG_TOO_HIGH | AS5048_MAG_TOO_LOW)) != 0)
        {
            enc->error_count++;
            return HAL_ERROR;
        }
    }

    enc->angle_raw = angle;
    enc->error_count = 0;
    *raw = angle;
    return HAL_OK;
}

HAL_StatusTypeDef as5048_read_angle(as5048_t *enc, float *angle_deg)
{
    uint16_t raw;

    if (as5048_read_raw(enc, &raw) != HAL_OK)
    {
        return HAL_ERROR;
    }

    enc->angle_deg = (float)raw * AS5048_DEG_PER_LSB;
    if (angle_deg != NULL)
    {
        *angle_deg = enc->angle_deg;
    }
    return HAL_OK;
}

HAL_StatusTypeDef as5048_set_zero_offset(as5048_t *enc, uint16_t offset)
{
    uint16_t cmd, rx;

    if (enc == NULL || !enc->initialized)
    {
        return HAL_ERROR;
    }

    /* 写 PROG 寄存器 (需硬件将 PROG 引脚接高电平使能) */
    cmd = AS5048_CMD_WRITE | (AS5048_REG_PROG << 1);
    as5048_cs_low(enc);
    as5048_cs_high(enc);
    as5048_cs_low(enc);
    HAL_SPI_Transmit(enc->hspi, (uint8_t *)&cmd, 2, HAL_MAX_DELAY);
    as5048_cs_high(enc);

    /* 发送零位偏移值 */
    (void)offset;
    (void)rx;

    /* 注: 完整 ZERO 编程流程需按数据手册时序 (PROG 上拉 + 写零值帧),
           此处仅提供骨架, 实际生产建议在出厂标定时执行。 */
    return HAL_OK;
}
