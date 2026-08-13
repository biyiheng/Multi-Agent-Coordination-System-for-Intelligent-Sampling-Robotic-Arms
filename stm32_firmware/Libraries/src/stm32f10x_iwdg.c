#include "stm32f10x_iwdg.h"
void IWDG_ReloadCounter(void) {
  IWDG->KR = 0xAAAA;
}