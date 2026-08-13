#ifndef __STM32F10X_SPI_H
#define __STM32F10X_SPI_H

#include "stm32f10x.h"

/* ========================================================================= */
/*                        SPI Init Structure                                */
/* ========================================================================= */

/** @brief SPI 初始化结构体 */
typedef struct
{
  uint16_t SPI_Direction;            /* 传输方向 */
  uint16_t SPI_Mode;                 /* 主/从模式 */
  uint16_t SPI_DataSize;             /* 数据帧长度 */
  uint16_t SPI_CPOL;                 /* 时钟极性 */
  uint16_t SPI_CPHA;                 /* 时钟相位 */
  uint16_t SPI_NSS;                  /* NSS 管理 */
  uint16_t SPI_BaudRatePrescaler;    /* 波特率预分频 */
  uint16_t SPI_FirstBit;             /* 首 bit */
  uint16_t SPI_CRCPolynomial;        /* CRC 多项式 */
} SPI_InitTypeDef;

/* ========================================================================= */
/*                         SPI Exported Constants                           */
/* ========================================================================= */

/* SPI_Direction */
#define SPI_Direction_2Lines_FullDuplex   ((uint16_t)0x0000)
#define SPI_Direction_2Lines_RxOnly       ((uint16_t)0x0400)
#define SPI_Direction_1Line_Rx            ((uint16_t)0x8000)
#define SPI_Direction_1Line_Tx            ((uint16_t)0xC000)

/* SPI_Mode */
#define SPI_Mode_Slave                    ((uint16_t)0x0000)
#define SPI_Mode_Master                   ((uint16_t)0x0104)

/* SPI_DataSize */
#define SPI_DataSize_16b                  ((uint16_t)0x0000)
#define SPI_DataSize_8b                   ((uint16_t)0x0800)

/* SPI_CPOL */
#define SPI_CPOL_Low                      ((uint16_t)0x0000)
#define SPI_CPOL_High                     ((uint16_t)0x0002)

/* SPI_CPHA */
#define SPI_CPHA_1Edge                    ((uint16_t)0x0000)
#define SPI_CPHA_2Edge                    ((uint16_t)0x0001)

/* SPI_NSS */
#define SPI_NSS_Soft                      ((uint16_t)0x0200)
#define SPI_NSS_Hard                      ((uint16_t)0x0000)

/* SPI_BaudRatePrescaler */
#define SPI_BaudRatePrescaler_2           ((uint16_t)0x0000)
#define SPI_BaudRatePrescaler_4           ((uint16_t)0x0008)
#define SPI_BaudRatePrescaler_8           ((uint16_t)0x0010)
#define SPI_BaudRatePrescaler_16          ((uint16_t)0x0018)
#define SPI_BaudRatePrescaler_32          ((uint16_t)0x0020)
#define SPI_BaudRatePrescaler_64          ((uint16_t)0x0028)
#define SPI_BaudRatePrescaler_128         ((uint16_t)0x0030)
#define SPI_BaudRatePrescaler_256         ((uint16_t)0x0038)

/* SPI_FirstBit */
#define SPI_FirstBit_MSB                  ((uint16_t)0x0000)
#define SPI_FirstBit_LSB                  ((uint16_t)0x0080)

/* SPI/I2S flags (SR 寄存器) */
#define SPI_I2S_FLAG_RXNE                 ((uint16_t)0x0001)
#define SPI_I2S_FLAG_TXE                  ((uint16_t)0x0002)
#define SPI_I2S_FLAG_CHSIDE               ((uint16_t)0x0004)
#define SPI_I2S_FLAG_UDR                  ((uint16_t)0x0008)
#define SPI_I2S_FLAG_CRCERR               ((uint16_t)0x0010)
#define SPI_I2S_FLAG_MODF                 ((uint16_t)0x0020)
#define SPI_I2S_FLAG_OVR                  ((uint16_t)0x0040)
#define SPI_I2S_FLAG_BSY                  ((uint16_t)0x0080)

/* SPI DMA request */
#define SPI_I2S_DMAReq_Tx                 ((uint16_t)0x0002)
#define SPI_I2S_DMAReq_Rx                 ((uint16_t)0x0001)

/* SPI/I2S interrupts (CR2 寄存器) */
#define SPI_I2S_IT_TXE                    ((uint8_t)0x02)
#define SPI_I2S_IT_RXNE                   ((uint8_t)0x01)
#define SPI_I2S_IT_ERR                    ((uint8_t)0x38)

/* 中断状态掩码 */
#define SPI_I2S_IT_MASK                   ((uint8_t)0x03)
#define SPI_I2S_ERR_IT_MASK               ((uint8_t)0x38)

/* ========================================================================= */
/*                     SPI Exported Functions                              */
/* ========================================================================= */

/** @brief 复位 SPI 外设 */
void SPI_I2S_DeInit(SPI_TypeDef* SPIx);

/** @brief 按结构体初始化 SPI */
void SPI_Init(SPI_TypeDef* SPIx, SPI_InitTypeDef* SPI_InitStruct);

/** @brief 使能/关闭 SPI */
void SPI_Cmd(SPI_TypeDef* SPIx, FunctionalState NewState);

/** @brief 获取 SPI/I2S 标志状态 */
FlagStatus SPI_I2S_GetFlagStatus(SPI_TypeDef* SPIx, uint16_t SPI_I2S_FLAG);

/** @brief 发送一个数据帧 */
void SPI_I2S_SendData(SPI_TypeDef* SPIx, uint16_t Data);

/** @brief 接收一个数据帧 */
uint16_t SPI_I2S_ReceiveData(SPI_TypeDef* SPIx);

/** @brief 配置 SPI/I2S DMA */
void SPI_I2S_DMACmd(SPI_TypeDef* SPIx, uint16_t SPI_I2S_DMAReq,
                    FunctionalState NewState);

#endif /* __STM32F10X_SPI_H */
