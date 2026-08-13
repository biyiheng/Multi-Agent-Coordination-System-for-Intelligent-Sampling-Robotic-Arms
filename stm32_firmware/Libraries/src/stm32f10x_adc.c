#include "stm32f10x_adc.h"

void ADC_Init(ADC_TypeDef* ADCx, ADC_InitTypeDef* ADC_InitStruct) {
  uint32_t tmpreg1 = 0;
  uint8_t tmpreg2 = 0;

  tmpreg1 = ADCx->CR1;
  tmpreg1 &= (uint32_t)0xFFFF0000;
  tmpreg1 |= ADC_InitStruct->ADC_Mode | ADC_InitStruct->ADC_ScanConvMode;
  ADCx->CR1 = tmpreg1;

  tmpreg1 = ADCx->CR2;
  tmpreg1 &= (uint32_t)0xFFF1F7FD;
  tmpreg1 |= ADC_InitStruct->ADC_DataAlign | ADC_InitStruct->ADC_ExternalTrigConv | ADC_InitStruct->ADC_ContinuousConvMode;
  ADCx->CR2 = tmpreg1;

  tmpreg1 = ADCx->SQR1;
  tmpreg1 &= (uint32_t)0xFF0FFFFF;
  tmpreg2 = (uint8_t)(ADC_InitStruct->ADC_NbrOfChannel - (uint8_t)1);
  tmpreg1 |= (uint32_t)tmpreg2 << 20;
  ADCx->SQR1 = tmpreg1;
}

void ADC_Cmd(ADC_TypeDef* ADCx, uint8_t NewState) {
  if (NewState != 0) {
    ADCx->CR2 |= ADC_CR2_ADON;
  } else {
    ADCx->CR2 &= (uint32_t)(~ADC_CR2_ADON);
  }
}

void ADC_RegularChannelConfig(ADC_TypeDef* ADCx, uint8_t ADC_Channel, uint8_t Rank, uint8_t ADC_SampleTime) {
  uint32_t tmpreg1 = 0, tmpreg2 = 0;

  if (ADC_Channel > 9) {
    tmpreg1 = ADCx->SMPR1;
    tmpreg2 = ADC_SampleTime << (3 * (ADC_Channel - 10));
    tmpreg1 &= ~((uint32_t)0x07 << (3 * (ADC_Channel - 10)));
    tmpreg1 |= tmpreg2;
    ADCx->SMPR1 = tmpreg1;
  } else {
    tmpreg1 = ADCx->SMPR2;
    tmpreg2 = ADC_SampleTime << (3 * ADC_Channel);
    tmpreg1 &= ~((uint32_t)0x07 << (3 * ADC_Channel));
    tmpreg1 |= tmpreg2;
    ADCx->SMPR2 = tmpreg1;
  }

  if (Rank < 7) {
    tmpreg1 = ADCx->SQR3;
    tmpreg2 = ADC_Channel << (5 * (Rank - 1));
    tmpreg1 &= ~((uint32_t)0x1F << (5 * (Rank - 1)));
    tmpreg1 |= tmpreg2;
    ADCx->SQR3 = tmpreg1;
  } else if (Rank < 13) {
    tmpreg1 = ADCx->SQR2;
    tmpreg2 = ADC_Channel << (5 * (Rank - 7));
    tmpreg1 &= ~((uint32_t)0x1F << (5 * (Rank - 7)));
    tmpreg1 |= tmpreg2;
    ADCx->SQR2 = tmpreg1;
  } else {
    tmpreg1 = ADCx->SQR1;
    tmpreg2 = ADC_Channel << (5 * (Rank - 13));
    tmpreg1 &= ~((uint32_t)0x1F << (5 * (Rank - 13)));
    tmpreg1 |= tmpreg2;
    ADCx->SQR1 = tmpreg1;
  }
}

void ADC_SoftwareStartConvCmd(ADC_TypeDef* ADCx, uint8_t NewState) {
  if (NewState != 0) {
    ADCx->CR2 |= ADC_CR2_SWSTART;
  } else {
    ADCx->CR2 &= (uint32_t)(~ADC_CR2_SWSTART);
  }
}

void ADC_StartCalibration(ADC_TypeDef* ADCx) {
  ADCx->CR2 |= ADC_CR2_CAL;
}

uint8_t ADC_GetCalibrationStatus(ADC_TypeDef* ADCx) {
  uint8_t bitstatus = 0x00;
  if ((ADCx->CR2 & ADC_CR2_CAL) != (uint32_t)0x00) {
    bitstatus = 0x01;
  }
  return bitstatus;
}

void ADC_ResetCalibration(ADC_TypeDef* ADCx) {
  ADCx->CR2 |= ADC_CR2_RSTCAL;
}

uint8_t ADC_GetResetCalibrationStatus(ADC_TypeDef* ADCx) {
  uint8_t bitstatus = 0x00;
  if ((ADCx->CR2 & ADC_CR2_RSTCAL) != (uint32_t)0x00) {
    bitstatus = 0x01;
  }
  return bitstatus;
}

uint16_t ADC_GetConversionValue(ADC_TypeDef* ADCx) {
  return (uint16_t)ADCx->DR;
}

uint8_t ADC_GetFlagStatus(ADC_TypeDef* ADCx, uint8_t ADC_FLAG) {
  uint8_t bitstatus = 0x00;
  if ((ADCx->SR & ADC_FLAG) != (uint8_t)0x00) {
    bitstatus = 0x01;
  }
  return bitstatus;
}