/**
  ******************************************************************************
  * @file    SRC/encoder/y_encoder.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   AS5048A/B 绝对值编码器驱动头文件 (STM32F103 SPL 集成)
  *
  *          工业级升级规划 §1.3 / S1: 关节输出轴加装 AS5048 高精度绝对值
  *          编码器 (14bit, 分辨率 0.0219°), 通过 SPI 读取绝对角度, 用于
  *          关节闭环反馈。本文件为当前 F103 工程内的落地实现, 接口与
  *          stm32h7/as5048_encoder 参考骨架保持一致。
  *
  *          接线 (SPI1):
  *            PA5 -> AS5048 CLK
  *            PA6 <- AS5048 MISO
  *            PA7 -> AS5048 MOSI
  *            PC0 -> AS5048 CSn (片选, 低有效)
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_ENCODER_H
#define __Y_ENCODER_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"
#include "stm32f10x_spi.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"

/* 寄存器地址 (AS5048A/B) ------------------------------------------------------*/
#define AS5048_REG_NOP          0x0000  /* 空操作 */
#define AS5048_REG_CLEAR_ERROR  0x0001  /* 清除错误标志 */
#define AS5048_REG_PROG         0x0003  /* 编程控制 */
#define AS5048_REG_MAG          0x3FFE  /* 磁场诊断 */
#define AS5048_REG_ANGLE        0x3FFF  /* 角度寄存器 (14bit) */

/* 命令位定义: bit15=读(0)/写(1), bit14..6=地址 */
#define AS5048_CMD_READ         0x0000
#define AS5048_CMD_WRITE        0x4000

/* 磁场报警阈值 (MAG 高 11bit) */
#define AS5048_MAG_TOO_HIGH     0x0800  /* 磁场过强 (bit11) */
#define AS5048_MAG_TOO_LOW      0x0400  /* 磁场过弱 (bit10) */

/* 14bit 满量程与角度换算 */
#define AS5048_RAW_MAX          16384.0f
#define AS5048_DEG_PER_LSB      (360.0f / AS5048_RAW_MAX)

/* SPI 引脚 (SPI1 默认映射) */
#define ENC_CS_PORT             GPIOC
#define ENC_CS_PIN              GPIO_Pin_0
#define ENC_CS_CLOCK            RCC_APB2Periph_GPIOC

/* 错误码 */
#define ENC_OK                  0       /* 成功 */
#define ENC_ERR_INIT            1       /* 初始化失败 */
#define ENC_ERR_READ            2       /* 读取失败 */
#define ENC_ERR_MAGNETIC        3       /* 磁场异常 */

/**
  * @brief  编码器数据结构体
  */
typedef struct
{
    uint16_t angle_raw;     /* 角度原始值 (0-16383) */
    float    angle_deg;     /* 角度 (度, 0-360) */
    uint8_t  error_count;   /* 连续错误计数 */
    uint8_t  initialized;   /* 初始化完成标志 */
} encoder_data_t;

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  编码器模块初始化 (SPI1 + 片选)
  * @param  无
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_init(void);

/**
  * @brief  读取编码器绝对角度
  * @param  angle_deg: 输出角度指针 (度, 0-360)
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_read_angle(float *angle_deg);

/**
  * @brief  读取原始 14bit 值
  * @param  raw: 输出原始值 (0-16383)
  * @retval 0: 成功, 非0: 失败
  */
uint8_t encoder_read_raw(uint16_t *raw);

/**
  * @brief  获取编码器数据
  * @param  无
  * @retval 编码器数据指针
  */
encoder_data_t* encoder_get_data(void);

#endif /* __Y_ENCODER_H */
