#ifndef __STM32F10X_ADC_H
#define __STM32F10X_ADC_H

#include "stm32f10x.h"

typedef struct {
  uint32_t ADC_Mode;
  uint32_t ADC_ScanConvMode;
  uint32_t ADC_ContinuousConvMode;
  uint32_t ADC_ExternalTrigConv;
  uint32_t ADC_DataAlign;
  uint8_t  ADC_NbrOfChannel;
} ADC_InitTypeDef;

#define ADC_Mode_Independent  ((uint32_t)0x00000000)
#define ADC_ScanConvMode_Enable  ((uint32_t)0x00000100)
#define ADC_ContinuousConvMode_Enable  ((uint32_t)0x00000002)
#define ADC_ExternalTrigConv_None  ((uint32_t)0x000E0000)
#define ADC_DataAlign_Right  ((uint32_t)0x00000000)
#define ADC_FLAG_EOC  ((uint8_t)0x02)
#define ADC_VOLTAGE_ADC          ADC1
#define ADC_VOLTAGE_CHANNEL      ADC_Channel_0
#define ADC_VOLTAGE_PIN          GPIO_Pin_0
#define ADC_VOLTAGE_PORT         GPIOA
#define ADC_VREF                 3300
#define ADC_RESOLUTION           4096

/* ADC Channel definitions */
#define ADC_Channel_0   ((uint8_t)0x00)
#define ADC_Channel_1   ((uint8_t)0x01)
#define ADC_Channel_2   ((uint8_t)0x02)
#define ADC_Channel_3   ((uint8_t)0x03)
#define ADC_Channel_4   ((uint8_t)0x04)
#define ADC_Channel_5   ((uint8_t)0x05)
#define ADC_Channel_6   ((uint8_t)0x06)
#define ADC_Channel_7   ((uint8_t)0x07)
#define ADC_Channel_8   ((uint8_t)0x08)
#define ADC_Channel_9   ((uint8_t)0x09)
#define ADC_Channel_10  ((uint8_t)0x0A)
#define ADC_Channel_11  ((uint8_t)0x0B)
#define ADC_Channel_12  ((uint8_t)0x0C)
#define ADC_Channel_13  ((uint8_t)0x0D)
#define ADC_Channel_14  ((uint8_t)0x0E)
#define ADC_Channel_15  ((uint8_t)0x0F)
#define ADC_Channel_16  ((uint8_t)0x10)
#define ADC_Channel_17  ((uint8_t)0x11)
#define ADC_SampleTime_1Cycles5   ((uint8_t)0x00)
#define ADC_SampleTime_7Cycles5   ((uint8_t)0x01)
#define ADC_SampleTime_13Cycles5  ((uint8_t)0x02)
#define ADC_SampleTime_28Cycles5  ((uint8_t)0x03)
#define ADC_SampleTime_41Cycles5  ((uint8_t)0x04)
#define ADC_SampleTime_55Cycles5  ((uint8_t)0x05)
#define ADC_SampleTime_71Cycles5  ((uint8_t)0x06)
#define ADC_SampleTime_239Cycles5 ((uint8_t)0x07)

void ADC_Init(ADC_TypeDef* ADCx, ADC_InitTypeDef* ADC_InitStruct);
void ADC_Cmd(ADC_TypeDef* ADCx, uint8_t NewState);
void ADC_RegularChannelConfig(ADC_TypeDef* ADCx, uint8_t ADC_Channel, uint8_t Rank, uint8_t ADC_SampleTime);
void ADC_SoftwareStartConvCmd(ADC_TypeDef* ADCx, uint8_t NewState);
void ADC_StartCalibration(ADC_TypeDef* ADCx);
uint8_t ADC_GetCalibrationStatus(ADC_TypeDef* ADCx);
void ADC_ResetCalibration(ADC_TypeDef* ADCx);
uint8_t ADC_GetResetCalibrationStatus(ADC_TypeDef* ADCx);
uint16_t ADC_GetConversionValue(ADC_TypeDef* ADCx);
uint8_t ADC_GetFlagStatus(ADC_TypeDef* ADCx, uint8_t ADC_FLAG);

#endif