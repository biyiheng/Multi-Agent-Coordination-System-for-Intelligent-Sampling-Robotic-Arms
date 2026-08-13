#include "stm32f10x_usart.h"

void USART_Init(USART_TypeDef* USARTx, USART_InitTypeDef* USART_InitStruct) {
  uint32_t tmpreg = 0x00, apbclock = 0x00;
  uint32_t integerdivider = 0x00;
  uint32_t fractionaldivider = 0x00;
  uint32_t usartxbase = 0;

  usartxbase = (uint32_t)USARTx;

  /* Use SystemCoreClock to determine APB clock dynamically */
	  extern uint32_t SystemCoreClock;
	  if (usartxbase == USART1_BASE) {
	    /* UART1 on APB2 (PCLK2 = SystemCoreClock if no prescaler) */
	    apbclock = SystemCoreClock;
	  } else {
	    /* UART2/3 on APB1 (PCLK1 = SystemCoreClock / 2 typically) */
	    apbclock = SystemCoreClock / 2;
	  }

  /* CR2 */
  tmpreg = USARTx->CR2;
  tmpreg &= (uint32_t)~(USART_CR2_STOP | USART_CR2_CLKEN | USART_CR2_CPOL | USART_CR2_CPHA | USART_CR2_LBCL);
  tmpreg |= (uint32_t)USART_InitStruct->USART_StopBits;
  USARTx->CR2 = (uint16_t)tmpreg;

  /* CR1 */
  tmpreg = USARTx->CR1;
  tmpreg &= (uint32_t)~(USART_CR1_M | USART_CR1_PCE | USART_CR1_PS | USART_CR1_TE | USART_CR1_RE);
  tmpreg |= (uint32_t)USART_InitStruct->USART_WordLength | USART_InitStruct->USART_Parity | USART_InitStruct->USART_Mode;
  USARTx->CR1 = (uint16_t)tmpreg;

  /* CR3 */
  tmpreg = USARTx->CR3;
  tmpreg &= (uint32_t)~(USART_CR3_RTSE | USART_CR3_CTSE);
  tmpreg |= USART_InitStruct->USART_HardwareFlowControl;
  USARTx->CR3 = (uint16_t)tmpreg;

  /* BRR */
  integerdivider = ((0x19 * apbclock) / (0x04 * (USART_InitStruct->USART_BaudRate)));
  tmpreg = (integerdivider / 0x64) << 0x04;
  fractionaldivider = integerdivider - (0x64 * (tmpreg >> 0x04));
  tmpreg |= ((((fractionaldivider * 0x10) + 0x32) / 0x64)) & ((uint8_t)0x0F);
  USARTx->BRR = (uint16_t)tmpreg;
}

void USART_Cmd(USART_TypeDef* USARTx, uint8_t NewState) {
  if (NewState != 0) {
    USARTx->CR1 |= USART_CR1_UE;
  } else {
    USARTx->CR1 &= (uint16_t)~((uint16_t)USART_CR1_UE);
  }
}

void USART_ITConfig(USART_TypeDef* USARTx, uint16_t USART_IT, uint8_t NewState) {
  uint32_t usartreg = 0x00, itpos = 0x00, itmask = 0x00;
  uint32_t usartxbase = 0x00;

  usartxbase = (uint32_t)USARTx;
  usartreg = (((uint16_t)USART_IT) >> 0x08);
  itpos = USART_IT & 0x00FF;
  itmask = (((uint32_t)0x01) << itpos);

  if (usartreg == 0x01) {
    usartxbase += 0x0C;
  } else if (usartreg == 0x02) {
    usartxbase += 0x10;
  } else {
    usartxbase += 0x14;
  }

  if (NewState != 0) {
    *(__IO uint32_t*)usartxbase |= itmask;
  } else {
    *(__IO uint32_t*)usartxbase &= ~itmask;
  }
}

void USART_SendData(USART_TypeDef* USARTx, uint16_t Data) {
  assert_param(IS_USART_ALL_PERIPH(USARTx));
  assert_param(IS_USART_DATA(Data));
  USARTx->DR = (Data & (uint16_t)0x01FF);
}

uint16_t USART_ReceiveData(USART_TypeDef* USARTx) {
  assert_param(IS_USART_ALL_PERIPH(USARTx));
  return (uint16_t)(USARTx->DR & (uint16_t)0x01FF);
}

uint8_t USART_GetFlagStatus(USART_TypeDef* USARTx, uint16_t USART_FLAG) {
  uint8_t bitstatus = 0x00;
  assert_param(IS_USART_ALL_PERIPH(USARTx));
  assert_param(IS_USART_FLAG(USART_FLAG));
  if ((USARTx->SR & USART_FLAG) != (uint16_t)0x00) {
    bitstatus = 0x01;
  }
  return bitstatus;
}

uint8_t USART_GetITStatus(USART_TypeDef* USARTx, uint16_t USART_IT) {
  uint32_t bitpos = 0x00, itmask = 0x00, usartreg = 0x00;
  uint8_t bitstatus = 0x00;
  usartreg = (((uint16_t)USART_IT) >> 0x08);
  itmask = USART_IT & 0x00FF;
  itmask = (uint32_t)0x01 << itmask;

  if (usartreg == 0x01) {
    bitstatus = ((USARTx->SR & itmask) != (uint16_t)0x00);
  } else if (usartreg == 0x02) {
    bitpos = USART_IT >> 0x0A;
    bitpos = (uint32_t)0x01 << bitpos;
    bitstatus = ((*(__IO uint32_t*) ((uint32_t)USARTx + 0x0C) & itmask) != (uint32_t)0x00) && (((USARTx->SR & bitpos) != (uint16_t)0x00));
  } else {
    bitstatus = ((*(__IO uint32_t*) ((uint32_t)USARTx + 0x10) & itmask) != (uint32_t)0x00);
  }
  return bitstatus;
}

void USART_ClearITPendingBit(USART_TypeDef* USARTx, uint16_t USART_IT) {
  uint16_t bitpos = 0x00, itmask = 0x00;
  itmask = USART_IT & 0x00FF;
  if (USART_IT == USART_IT_RXNE) {
    (void)USARTx->DR;
  } else {
    USARTx->SR = (uint16_t)~itmask;
  }
}