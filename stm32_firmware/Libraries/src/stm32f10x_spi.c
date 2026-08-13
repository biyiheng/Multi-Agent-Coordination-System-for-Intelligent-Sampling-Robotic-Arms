#include "stm32f10x_spi.h"

/* 本工程自定义 stm32f10x.h 未提供 SPI_CR1 位宏, 此处自行定义可配置位掩码 */

/* SPI CR1 中可被初始化结构体配置的位 (除 SPE/CRCEN/CRCNEXT 及保留位外) */
#define SPI_CR1_CONFIG_MASK  0xCFBFu

/* SPI CR1 SPE 位 (bit6) */
#define SPI_CR1_SPE          0x0040u

/** @brief 复位 SPI 外设
 *  @note  本工程 RCC 库未提供 RCC_APBxPeriphResetCmd, 复位由
 *         SPI_Init 前的 SPI_Cmd(DISABLE) 完成; 此处保留空实现以兼容 API。 */
void SPI_I2S_DeInit(SPI_TypeDef* SPIx)
{
  (void)SPIx;
}

/** @brief 按结构体初始化 SPI */
void SPI_Init(SPI_TypeDef* SPIx, SPI_InitTypeDef* SPI_InitStruct)
{
  uint16_t tmpreg;

  /* 读取 CR1, 清除所有可配置位, 保留 SPE/CRCEN/CRCNEXT/保留位 */
  tmpreg = SPIx->CR1;
  tmpreg &= (uint16_t)~SPI_CR1_CONFIG_MASK;

  /* 组合新的配置值 */
  tmpreg |= (uint16_t)((uint16_t)SPI_InitStruct->SPI_Direction |
                       (uint16_t)SPI_InitStruct->SPI_Mode |
                       (uint16_t)SPI_InitStruct->SPI_DataSize |
                       (uint16_t)SPI_InitStruct->SPI_CPOL |
                       (uint16_t)SPI_InitStruct->SPI_CPHA |
                       (uint16_t)SPI_InitStruct->SPI_NSS |
                       (uint16_t)SPI_InitStruct->SPI_BaudRatePrescaler |
                       (uint16_t)SPI_InitStruct->SPI_FirstBit);

  /* 写回 CR1 */
  SPIx->CR1 = tmpreg;

  /* 配置 CRC 多项式 */
  SPIx->CRCPR = SPI_InitStruct->SPI_CRCPolynomial;
}

/** @brief 使能/关闭 SPI */
void SPI_Cmd(SPI_TypeDef* SPIx, FunctionalState NewState)
{
  if (NewState != DISABLE)
  {
    SPIx->CR1 |= (uint16_t)SPI_CR1_SPE;
  }
  else
  {
    SPIx->CR1 &= (uint16_t)~SPI_CR1_SPE;
  }
}

/** @brief 获取 SPI/I2S 标志状态 */
FlagStatus SPI_I2S_GetFlagStatus(SPI_TypeDef* SPIx, uint16_t SPI_I2S_FLAG)
{
  if ((SPIx->SR & SPI_I2S_FLAG) != (uint16_t)RESET)
  {
    return SET;
  }
  return RESET;
}

/** @brief 发送一个数据帧 (16bit) */
void SPI_I2S_SendData(SPI_TypeDef* SPIx, uint16_t Data)
{
  /* 写入 DR 寄存器 (触发一次传输) */
  SPIx->DR = Data;
}

/** @brief 接收一个数据帧 (16bit) */
uint16_t SPI_I2S_ReceiveData(SPI_TypeDef* SPIx)
{
  /* 读取 DR 寄存器 */
  return SPIx->DR;
}

/** @brief 配置 SPI/I2S DMA */
void SPI_I2S_DMACmd(SPI_TypeDef* SPIx, uint16_t SPI_I2S_DMAReq,
                    FunctionalState NewState)
{
  if (NewState != DISABLE)
  {
    SPIx->CR2 |= SPI_I2S_DMAReq;
  }
  else
  {
    SPIx->CR2 &= (uint16_t)~SPI_I2S_DMAReq;
  }
}
