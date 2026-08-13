# =============================================================================
# Makefile for STM32F103C8T6 (智能采样机械臂)
# Toolchain: ARM GNU Toolchain (arm-none-eabi-gcc)
# Usage: make all         - Build firmware
#        make clean       - Clean build artifacts
#        make flash       - Flash using ST-Link CLI
# =============================================================================

# Toolchain path (STM32CubeIDE bundled GNU Tools for STM32 13.3.rel1)
TC_BIN = C:/ST/STM32C~1.0/STM32C~1/plugins/CO7230~1.202/tools/bin

# Tell GCC where to find its internal executables (cc1, as, ld, etc.)
export GCC_EXEC_PREFIX := $(TC_BIN)/../lib/gcc/

# Add toolchain to PATH for make's shell
export PATH := $(TC_BIN):$(PATH)

CC      = $(TC_BIN)/arm-none-eabi-gcc
OBJCOPY = $(TC_BIN)/arm-none-eabi-objcopy
SIZE    = $(TC_BIN)/arm-none-eabi-size

# Project
TARGET  = STM32F103C8T6
BUILD   = OUT

# --- Compiler Flags ---
DEFS     = -DSTM32F10X_MD -DUSE_STDPERIPH_DRIVER
CPU      = -mcpu=cortex-m3 -mthumb
FPU      = -mfloat-abi=soft

INCLUDES  = -I.
INCLUDES += -ICMSIS/CM3/CoreSupport
INCLUDES += -ICMSIS/CM3/DeviceSupport
INCLUDES += -ILibraries/inc
INCLUDES += -IUSER
INCLUDES += -IUSER/includes
INCLUDES += -ISRC/action_group
INCLUDES += -ISRC/bus_servo
INCLUDES += -ISRC/can
INCLUDES += -ISRC/encoder
INCLUDES += -ISRC/flash
INCLUDES += -ISRC/safety
INCLUDES += -ISRC/sensor
INCLUDES += -ISRC/usart

CFLAGS   = $(CPU) $(FPU) $(DEFS) $(INCLUDES)
CFLAGS  += -Og -g3 -Wall -fdata-sections -ffunction-sections
CFLAGS  += -std=gnu99

ASFLAGS  = $(CPU) $(FPU) -g

LDFLAGS  = $(CPU) $(FPU)
LDFLAGS += -specs=nosys.specs -specs=nano.specs
LDFLAGS += -T STM32F103C8T6.ld
LDFLAGS += -Wl,-Map=$(BUILD)/$(TARGET).map,--cref
LDFLAGS += -Wl,--gc-sections

# --- Source Files ---
ASM_SRC = CMSIS/Startup/startup_stm32f10x_md.s

C_SRCS  = CMSIS/CM3/DeviceSupport/system_stm32f10x.c
C_SRCS += Libraries/src/stm32f10x_gpio.c
C_SRCS += Libraries/src/stm32f10x_rcc.c
C_SRCS += Libraries/src/stm32f10x_usart.c
C_SRCS += Libraries/src/stm32f10x_tim.c
C_SRCS += Libraries/src/stm32f10x_flash.c
C_SRCS += Libraries/src/stm32f10x_adc.c
C_SRCS += Libraries/src/stm32f10x_iwdg.c
C_SRCS += Libraries/src/stm32f10x_exti.c
C_SRCS += Libraries/src/misc.c
# 新增: SPI/CAN 标准外设库 (支持 AS5048 编码器与 CAN 通信层)
C_SRCS += Libraries/src/stm32f10x_spi.c
C_SRCS += Libraries/src/stm32f10x_can.c
# Application source files
C_SRCS += USER/main.c
C_SRCS += USER/app_protocol.c
C_SRCS += USER/app_arm.c
C_SRCS += USER/app_config.c
C_SRCS += USER/app_uart.c
C_SRCS += USER/stm32f10x_it.c
# SRC modules
C_SRCS += SRC/bus_servo/y_bus_servo.c
C_SRCS += SRC/sensor/y_sensor.c
C_SRCS += SRC/safety/y_safety.c
C_SRCS += SRC/flash/y_flash.c
C_SRCS += SRC/action_group/y_action_group.c
C_SRCS += SRC/usart/y_usart.c
# 新增: 编码器与 CAN 通信模块 (工业级升级 S1/S2)
C_SRCS += SRC/encoder/y_encoder.c
C_SRCS += SRC/can/y_can.c

# --- Build Objects ---
ASM_OBJ = $(BUILD)/startup_stm32f10x_md.o
C_OBJS  = $(patsubst %.c,$(BUILD)/%.o,$(notdir $(C_SRCS)))
OBJS    = $(ASM_OBJ) $(C_OBJS)

# --- Rules ---
.PHONY: all clean flash

all: $(BUILD)/$(TARGET).elf $(BUILD)/$(TARGET).hex $(BUILD)/$(TARGET).bin
	@echo "========================================="
	@echo "BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET).elf

# Create output directory
$(BUILD):
	-mkdir $(BUILD)

# Link
$(BUILD)/$(TARGET).elf: $(OBJS) | $(BUILD)
	@echo "Linking..."
	$(CC) $(LDFLAGS) $(OBJS) -o $@

# Assemble startup
$(ASM_OBJ): $(ASM_SRC) | $(BUILD)
	@echo "Assembling $(ASM_SRC)"
	$(CC) $(ASFLAGS) -c $(ASM_SRC) -o $@

# Compile each C file
$(BUILD)/system_stm32f10x.o: CMSIS/CM3/DeviceSupport/system_stm32f10x.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_gpio.o: Libraries/src/stm32f10x_gpio.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_rcc.o: Libraries/src/stm32f10x_rcc.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_usart.o: Libraries/src/stm32f10x_usart.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_tim.o: Libraries/src/stm32f10x_tim.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_flash.o: Libraries/src/stm32f10x_flash.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_adc.o: Libraries/src/stm32f10x_adc.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_iwdg.o: Libraries/src/stm32f10x_iwdg.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/misc.o: Libraries/src/misc.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_exti.o: Libraries/src/stm32f10x_exti.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/main.o: USER/main.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/app_protocol.o: USER/app_protocol.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/app_arm.o: USER/app_arm.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/app_config.o: USER/app_config.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/app_uart.o: USER/app_uart.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_it.o: USER/stm32f10x_it.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_bus_servo.o: SRC/bus_servo/y_bus_servo.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_sensor.o: SRC/sensor/y_sensor.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_safety.o: SRC/safety/y_safety.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_flash.o: SRC/flash/y_flash.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_action_group.o: SRC/action_group/y_action_group.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_usart.o: SRC/usart/y_usart.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

# 新增: SPI/CAN 标准外设库 (支持 AS5048 编码器与 CAN 通信层)
$(BUILD)/stm32f10x_spi.o: Libraries/src/stm32f10x_spi.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/stm32f10x_can.o: Libraries/src/stm32f10x_can.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

# 新增: 编码器与 CAN 通信模块 (工业级升级 S1/S2)
$(BUILD)/y_encoder.o: SRC/encoder/y_encoder.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/y_can.o: SRC/can/y_can.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

# Test minimal firmware (HSI only, minimal init)
$(BUILD)/test_minimal.o: USER/test_minimal.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

TEST_OBJS = $(ASM_OBJ) $(BUILD)/stm32f10x_gpio.o \
            $(BUILD)/stm32f10x_rcc.o $(BUILD)/stm32f10x_usart.o $(BUILD)/test_minimal.o

test_minimal: $(BUILD)/$(TARGET)_test.elf $(BUILD)/$(TARGET)_test.hex $(BUILD)/$(TARGET)_test.bin
	@echo "========================================="
	@echo "TEST MINIMAL BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_test.elf

$(BUILD)/$(TARGET)_test.elf: $(TEST_OBJS) | $(BUILD)
	@echo "Linking test_minimal..."
	$(CC) $(LDFLAGS) $(TEST_OBJS) -o $@

$(BUILD)/$(TARGET)_test.hex: $(BUILD)/$(TARGET)_test.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

$(BUILD)/$(TARGET)_test.bin: $(BUILD)/$(TARGET)_test.elf
	@echo "Creating BIN..."
	$(OBJCOPY) -O binary $< $@

# Minimal startup assembly (skips SystemInit and __libc_init_array)
$(BUILD)/startup_minimal.o: CMSIS/Startup/startup_minimal.s | $(BUILD)
	@echo "Assembling startup_minimal.s"
	$(CC) $(ASFLAGS) -c $< -o $@

# LED blink test firmware v2 (8E1 even parity, same as bootloader)
$(BUILD)/test_led_v2.o: USER/test_led_v2.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

LED_V2_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_led_v2.o

test_led_v2: $(BUILD)/$(TARGET)_led_v2.elf $(BUILD)/$(TARGET)_led_v2.hex
	@echo "========================================="
	@echo "LED V2 TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_led_v2.elf

$(BUILD)/$(TARGET)_led_v2.elf: $(LED_V2_OBJS) | $(BUILD)
	@echo "Linking test_led_v2..."
	$(CC) $(LDFLAGS) $(LED_V2_OBJS) -o $@

$(BUILD)/$(TARGET)_led_v2.hex: $(BUILD)/$(TARGET)_led_v2.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# LED blink test firmware (HSI 8MHz, no SystemInit)
$(BUILD)/test_led.o: USER/test_led.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

LED_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_led.o

test_led: $(BUILD)/$(TARGET)_led.elf $(BUILD)/$(TARGET)_led.hex
	@echo "========================================="
	@echo "LED TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_led.elf

$(BUILD)/$(TARGET)_led.elf: $(LED_OBJS) | $(BUILD)
	@echo "Linking test_led..."
	$(CC) $(LDFLAGS) $(LED_OBJS) -o $@

$(BUILD)/$(TARGET)_led.hex: $(BUILD)/$(TARGET)_led.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# YH-K32 V2 firmware (HSI 8MHz, 38400, no SysTick, no string libs)
$(BUILD)/main_v2.o: USER/main_v2.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

V2_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/main_v2.o

v2: $(BUILD)/$(TARGET)_v2.elf $(BUILD)/$(TARGET)_v2.hex
	@echo "========================================="
	@echo "YH-K32 V2 BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_v2.elf

$(BUILD)/$(TARGET)_v2.elf: $(V2_OBJS) | $(BUILD)
	@echo "Linking v2..."
	$(CC) $(LDFLAGS) $(V2_OBJS) -o $@

$(BUILD)/$(TARGET)_v2.hex: $(BUILD)/$(TARGET)_v2.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Step2b test: HSI 8MHz + UART 38400 + boot msg (NO SysTick)
$(BUILD)/test_step2b.o: USER/test_step2b.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

STEP2B_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_step2b.o

test_step2b: $(BUILD)/$(TARGET)_step2b.elf $(BUILD)/$(TARGET)_step2b.hex
	@echo "========================================="
	@echo "STEP2B TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_step2b.elf

$(BUILD)/$(TARGET)_step2b.elf: $(STEP2B_OBJS) | $(BUILD)
	@echo "Linking test_step2b..."
	$(CC) $(LDFLAGS) $(STEP2B_OBJS) -o $@

$(BUILD)/$(TARGET)_step2b.hex: $(BUILD)/$(TARGET)_step2b.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Step2 test: HSI 8MHz + UART 38400 + SysTick + boot msg (no string funcs)
$(BUILD)/test_step2.o: USER/test_step2.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

STEP2_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_step2.o

test_step2: $(BUILD)/$(TARGET)_step2.elf $(BUILD)/$(TARGET)_step2.hex
	@echo "========================================="
	@echo "STEP2 TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_step2.elf

$(BUILD)/$(TARGET)_step2.elf: $(STEP2_OBJS) | $(BUILD)
	@echo "Linking test_step2..."
	$(CC) $(LDFLAGS) $(STEP2_OBJS) -o $@

$(BUILD)/$(TARGET)_step2.hex: $(BUILD)/$(TARGET)_step2.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# 38400 baud test firmware (HSI 8MHz, UART 38400 8N1)
$(BUILD)/test_38400.o: USER/test_38400.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

T38400_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_38400.o

test_38400: $(BUILD)/$(TARGET)_38400.elf $(BUILD)/$(TARGET)_38400.hex
	@echo "========================================="
	@echo "38400 TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_38400.elf

$(BUILD)/$(TARGET)_38400.elf: $(T38400_OBJS) | $(BUILD)
	@echo "Linking test_38400..."
	$(CC) $(LDFLAGS) $(T38400_OBJS) -o $@

$(BUILD)/$(TARGET)_38400.hex: $(BUILD)/$(TARGET)_38400.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# YH-K32 main firmware (HSI 8MHz, 38400 baud, startup_minimal)
$(BUILD)/main_yhk32.o: USER/main_yhk32.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

YHK32_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/main_yhk32.o

yhk32: $(BUILD)/$(TARGET)_yhk32.elf $(BUILD)/$(TARGET)_yhk32.hex
	@echo "========================================="
	@echo "YH-K32 MAIN BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_yhk32.elf

$(BUILD)/$(TARGET)_yhk32.elf: $(YHK32_OBJS) | $(BUILD)
	@echo "Linking yhk32..."
	$(CC) $(LDFLAGS) $(YHK32_OBJS) -o $@

$(BUILD)/$(TARGET)_yhk32.hex: $(BUILD)/$(TARGET)_yhk32.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Passthrough test firmware (uses bootloader's UART, no reconfig)
$(BUILD)/test_passthru.o: USER/test_passthru.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

PASSTHRU_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_passthru.o

test_passthru: $(BUILD)/$(TARGET)_passthru.elf $(BUILD)/$(TARGET)_passthru.hex
	@echo "========================================="
	@echo "PASSTHRU TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_passthru.elf

$(BUILD)/$(TARGET)_passthru.elf: $(PASSTHRU_OBJS) | $(BUILD)
	@echo "Linking test_passthru..."
	$(CC) $(LDFLAGS) $(PASSTHRU_OBJS) -o $@

$(BUILD)/$(TARGET)_passthru.hex: $(BUILD)/$(TARGET)_passthru.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Absolute minimal test firmware (no init, just send 'U')
$(BUILD)/test_abs_min.o: USER/test_abs_min.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

ABS_MIN_OBJS = $(ASM_OBJ) $(BUILD)/test_abs_min.o

test_abs_min: $(BUILD)/$(TARGET)_abs_min.elf $(BUILD)/$(TARGET)_abs_min.hex
	@echo "========================================="
	@echo "ABS MIN TEST BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_abs_min.elf

$(BUILD)/$(TARGET)_abs_min.elf: $(ABS_MIN_OBJS) | $(BUILD)
	@echo "Linking test_abs_min..."
	$(CC) $(LDFLAGS) $(ABS_MIN_OBJS) -o $@

$(BUILD)/$(TARGET)_abs_min.hex: $(BUILD)/$(TARGET)_abs_min.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Test direct firmware (no library USART init, direct register access)
$(BUILD)/test_direct.o: USER/test_noinit.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

DIRECT_OBJS = $(BUILD)/startup_minimal.o $(BUILD)/test_direct.o

test_direct: $(BUILD)/$(TARGET)_direct.elf $(BUILD)/$(TARGET)_direct.hex
	@echo "========================================="
	@echo "TEST DIRECT BUILD SUCCESSFUL!"
	@echo "========================================="
	$(SIZE) $(BUILD)/$(TARGET)_direct.elf

$(BUILD)/$(TARGET)_direct.elf: $(DIRECT_OBJS) | $(BUILD)
	@echo "Linking test_direct..."
	$(CC) $(LDFLAGS) $(DIRECT_OBJS) -o $@

$(BUILD)/$(TARGET)_direct.hex: $(BUILD)/$(TARGET)_direct.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Create hex
$(BUILD)/%.hex: $(BUILD)/%.elf
	@echo "Creating HEX..."
	$(OBJCOPY) -O ihex $< $@

# Create bin
$(BUILD)/%.bin: $(BUILD)/%.elf
	@echo "Creating BIN..."
	$(OBJCOPY) -O binary $< $@

# Flash using ST-Link CLI
STLINK = "C:/Program Files (x86)/STMicroelectronics/ST-LINK Utility/ST-LINK_CLI.exe"
flash: $(BUILD)/$(TARGET).hex
	@echo "Flashing firmware..."
	$(STLINK) -c SWD -P $< -V -Rst
	@echo "Flash complete!"

clean:
	-rm -rf $(BUILD)