/**
  ******************************************************************************
  * @file    USER/app_protocol.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   应用层协议解析器实现
  *          负责解析来自树莓派的命令帧，路由到对应处理模块
  *          命令格式: #PREFIX:CMD! 或 #PREFIX:CMD:DATA!
  *          支持命令链: cmd1;cmd2;cmd3 (用;分隔)
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "app_protocol.h"
#include "app_arm.h"
#include "app_config.h"
#include "y_action_group.h"
#include "y_bus_servo.h"
#include "y_sensor.h"
#include "y_safety.h"
#include "y_flash.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* 外部函数声明 ----------------------------------------------------------------*/
extern void uart1_send_str(char *str);			/* UART1发送字符串 */
extern void uart2_send_str(char *str);			/* UART2发送字符串 */
extern void uart3_send_str(char *str);			/* UART3发送字符串 */
extern void uart1_receive_run(void);			/* UART1接收处理 */
extern uint8_t uart1_get_rx_data(char *buf, uint16_t *len);	/* 获取UART1接收数据 */
extern uint32_t get_systick(void);				/* 获取系统滴答 */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  当前解析的命令
  */
protocol_cmd_t protocol_cmd;

/* 私有变量 --------------------------------------------------------------------*/
static char  protocol_rx_buf[PROTOCOL_BUF_SIZE];	/* 接收缓冲区 */
static char  protocol_tx_buf[PROTOCOL_RESPONSE_SIZE];	/* 发送缓冲区 */
static uint16_t protocol_rx_len;					/* 接收数据长度 */
static uint8_t  protocol_busy;						/* 协议忙碌标志 */

/* 私有函数声明 ----------------------------------------------------------------*/
static void protocol_handle_arm(void);
static void protocol_handle_ag(void);
static void protocol_handle_sensor(void);
static void protocol_handle_vision(void);
static void protocol_handle_sys(void);
static void protocol_handle_bus(void);
static void protocol_execute_cmd(void);
static void protocol_parse_chain(char *data, uint16_t len);
static uint8_t protocol_parse_yhk32(char *data, uint16_t len);
static void protocol_handle_yhk32_servo(void);
static void protocol_handle_yhk32_multi_servo(char *data, uint16_t len);
static void protocol_handle_yhk32_sys(void);

/**
  * @brief  协议解析器初始化
  * @param  无
  * @返回值 无
  * @说明   初始化接收缓冲区和命令结构体
  */
void app_protocol_init(void)
{
	/* 清空接收缓冲区 */
	memset(protocol_rx_buf, 0, PROTOCOL_BUF_SIZE);
	protocol_rx_len = 0;

	/* 清空命令结构体 */
	memset(&protocol_cmd, 0, sizeof(protocol_cmd_t));

	/* 清空发送缓冲区 */
	memset(protocol_tx_buf, 0, PROTOCOL_RESPONSE_SIZE);

	/* 清除忙碌标志 */
	protocol_busy = 0;
}

/**
  * @brief  协议解析运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，检查是否有完整命令帧并处理
  */
void app_protocol_run(void)
{
	uint16_t len;
	uint8_t  result;

	/* 运行UART1接收 */
	uart1_receive_run();

	/* 获取接收数据 */
	result = uart1_get_rx_data(protocol_rx_buf, &len);

	if (result == 0 && len > 0)
	{
		/* 有数据到达，解析命令 */
		protocol_rx_len = len;

		/* 检查是否有命令链 */
		protocol_parse_chain(protocol_rx_buf, len);
	}
}

/**
  * @brief  解析命令链
  * @param  data: 接收数据
  * @param  len: 数据长度
  * @返回值 无
  * @说明   将命令链按;分割，逐个解析执行
  */
static void protocol_parse_chain(char *data, uint16_t len)
{
	char *cmd_start = data;
	char *cmd_end;
	uint16_t cmd_len;

	/* 查找命令链分隔符 */
	cmd_end = strchr(cmd_start, ';');

	while (cmd_end != NULL)
	{
		/* 计算单个命令长度 */
		cmd_len = (uint16_t)(cmd_end - cmd_start);

		/* 解析并执行单个命令 */
		if (cmd_len > 0 && cmd_len < PROTOCOL_BUF_SIZE)
		{
			app_protocol_parse(cmd_start, cmd_len);
			protocol_execute_cmd();
		}

		/* 移动到下一个命令 */
		cmd_start = cmd_end + 1;
		cmd_end = strchr(cmd_start, ';');
	}

	/* 处理最后一个命令(或唯一命令) */
	cmd_len = strlen(cmd_start);
	if (cmd_len > 0 && cmd_len < PROTOCOL_BUF_SIZE)
	{
		app_protocol_parse(cmd_start, cmd_len);
		protocol_execute_cmd();
	}
}

/**
  * @brief  解析协议命令
  * @param  data: 接收到的数据字符串
  * @param  len: 数据长度
  * @返回值 0: 成功, 1: 失败
  * @说明   支持两种协议格式:
  *         1. YH-K32格式: #IndexPpwmTtime! 或 $CMD! 
  *         2. 自定义格式: #PREFIX:CMD:DATA! 或 #PREFIX:CMD!
  *         优先尝试YH-K32格式解析，失败后回退到自定义格式
  */
uint8_t app_protocol_parse(char *data, uint16_t len)
{
	char *p_start, *p_end;

	/* 清空命令结构体 */
	memset(&protocol_cmd, 0, sizeof(protocol_cmd_t));

	/* 1. 先尝试YH-K32协议格式解析 */
	if (protocol_parse_yhk32(data, len) == 0)
	{
		return 0;  /* YH-K32格式解析成功 */
	}

	/* 2. 回退到自定义协议格式解析: #PREFIX:CMD:DATA! */
	/* 查找命令起始标记 '#' */
	p_start = strchr(data, '#');
	if (p_start == NULL)
	{
		protocol_cmd.valid = 0;
		return 1;
	}

	/* 查找命令结束标记 '!' */
	p_end = strchr(data, '!');
	if (p_end == NULL)
	{
		protocol_cmd.valid = 0;
		return 1;
	}

	/* 提取前缀(跳过#) */
	p_start++;  /* 跳过# */
	{
		char *colon = strchr(p_start, ':');
		if (colon != NULL && (uint16_t)(colon - p_start) < sizeof(protocol_cmd.prefix))
		{
			uint16_t prefix_len = (uint16_t)(colon - p_start);
			memcpy(protocol_cmd.prefix, p_start, prefix_len);
			protocol_cmd.prefix[prefix_len] = '\0';

			/* 提取命令和可选数据 */
			p_start = colon + 1;
			{
				char *data_sep = strchr(p_start, ':');
				uint16_t cmd_len;

				if (data_sep != NULL && data_sep < p_end)
				{
					/* 有数据部分 */
					cmd_len = (uint16_t)(data_sep - p_start);
					if (cmd_len < sizeof(protocol_cmd.cmd))
					{
						memcpy(protocol_cmd.cmd, p_start, cmd_len);
						protocol_cmd.cmd[cmd_len] = '\0';
					}

					data_sep++;
					cmd_len = (uint16_t)(p_end - data_sep);
					if (cmd_len < sizeof(protocol_cmd.data))
					{
						memcpy(protocol_cmd.data, data_sep, cmd_len);
						protocol_cmd.data[cmd_len] = '\0';
					}
				}
				else
				{
					/* 无数据部分 */
					cmd_len = (uint16_t)(p_end - p_start);
					if (cmd_len < sizeof(protocol_cmd.cmd))
					{
						memcpy(protocol_cmd.cmd, p_start, cmd_len);
						protocol_cmd.cmd[cmd_len] = '\0';
					}
				}
			}
		}
		else
		{
			protocol_cmd.valid = 0;
			return 1;
		}
	}

	/* 确定命令类型 */
	if (strcmp(protocol_cmd.prefix, "ARM") == 0)
	{
		protocol_cmd.type = CMD_ARM;
	}
	else if (strcmp(protocol_cmd.prefix, "AG") == 0)
	{
		protocol_cmd.type = CMD_AG;
	}
	else if (strcmp(protocol_cmd.prefix, "SENSOR") == 0)
	{
		protocol_cmd.type = CMD_SENSOR;
	}
	else if (strcmp(protocol_cmd.prefix, "VISION") == 0)
	{
		protocol_cmd.type = CMD_VISION;
	}
	else if (strcmp(protocol_cmd.prefix, "SYS") == 0)
	{
		protocol_cmd.type = CMD_SYS;
	}
	else if (strcmp(protocol_cmd.prefix, "BUS") == 0)
	{
		protocol_cmd.type = CMD_BUS;
	}
	else
	{
		protocol_cmd.type = CMD_UNKNOWN;
		protocol_cmd.valid = 0;
		return 1;
	}

	protocol_cmd.valid = 1;
	return 0;
}

/**
  * @brief  执行解析后的命令
  * @param  无
  * @返回值 无
  * @说明   根据命令类型路由到对应的处理函数
  */
static void protocol_execute_cmd(void)
{
	if (!protocol_cmd.valid)
	{
		app_protocol_send_response("ERR", "INVALID_CMD");
		return;
	}

	switch (protocol_cmd.type)
	{
		case CMD_ARM:
			protocol_handle_arm();
			break;

		case CMD_AG:
			protocol_handle_ag();
			break;

		case CMD_SENSOR:
			protocol_handle_sensor();
			break;

		case CMD_VISION:
			protocol_handle_vision();
			break;

		case CMD_SYS:
			protocol_handle_sys();
			break;

		case CMD_BUS:
			protocol_handle_bus();
			break;

		case CMD_YHK32_SERVO:
			protocol_handle_yhk32_servo();
			break;

		case CMD_YHK32_MULTI:
			/* 多舵机命令保持原始数据在protocol_cmd.data中 */
			protocol_handle_yhk32_multi_servo(protocol_cmd.data, strlen(protocol_cmd.data));
			break;

		case CMD_YHK32_SYS:
			protocol_handle_yhk32_sys();
			break;

		default:
			app_protocol_send_response("ERR", "UNKNOWN_TYPE");
			break;
	}
}

/**
  * @brief  处理机械臂控制命令
  * @param  无
  * @返回值 无
  * @说明   支持命令:
  *         MOVE:id,pwm,time - 移动单个关节
  *         MOVEALL:p1,p2,p3,p4,p5,p6,time - 移动所有关节
  *         STOP - 停止运动
  *         ORIGIN - 返回原点
  *         STATUS - 获取状态
  */
static void protocol_handle_arm(void)
{
	if (strcmp(protocol_cmd.cmd, "MOVE") == 0)
	{
		/* 解析: #ARM:MOVE:id,pwm,time! */
		uint8_t id;
		uint16_t pwm, time;
		if (sscanf(protocol_cmd.data, "%hhu,%hu,%hu", &id, &pwm, &time) == 3)
		{
			app_arm_move_joint(id, pwm, time);
			app_protocol_send_response("OK", "MOVE");
		}
		else
		{
			app_protocol_send_response("ERR", "PARAM");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "MOVEALL") == 0)
	{
		/* 解析: #ARM:MOVEALL:p1,p2,p3,p4,p5,p6,time! */
		uint16_t positions[6];
		uint16_t time;
		if (sscanf(protocol_cmd.data, "%hu,%hu,%hu,%hu,%hu,%hu,%hu",
			&positions[0], &positions[1], &positions[2],
			&positions[3], &positions[4], &positions[5], &time) == 7)
		{
			app_arm_move_all(positions, time);
			app_protocol_send_response("OK", "MOVEALL");
		}
		else
		{
			app_protocol_send_response("ERR", "PARAM");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "STOP") == 0)
	{
		app_arm_stop();
		app_protocol_send_response("OK", "STOP");
	}
	else if (strcmp(protocol_cmd.cmd, "ORIGIN") == 0)
	{
		app_arm_origin();
		app_protocol_send_response("OK", "ORIGIN");
	}
	else if (strcmp(protocol_cmd.cmd, "STATUS") == 0)
	{
		char status_buf[64];
		uint8_t status = app_arm_get_status();
		sprintf(status_buf, "STATUS:%d", status);
		app_protocol_send_response("OK", status_buf);
	}
	else
	{
		app_protocol_send_response("ERR", "UNKNOWN_ARM_CMD");
	}
}

/**
  * @brief  处理动作组命令
  * @param  无
  * @返回值 无
  * @说明   支持命令:
  *         PLAY:id - 播放动作组
  *         STOP - 停止播放
  *         RECORD:id - 开始录制
  *         FRAME - 录制一帧
  *         SAVE - 保存动作组
  *         LIST - 列出所有动作组
  *         DELETE:id - 删除动作组
  */
static void protocol_handle_ag(void)
{
	if (strcmp(protocol_cmd.cmd, "PLAY") == 0)
	{
		uint8_t id = atoi(protocol_cmd.data);
		if (ag_play(id) == 0)
		{
			app_protocol_send_response("OK", "PLAY");
		}
		else
		{
			app_protocol_send_response("ERR", "PLAY_FAIL");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "STOP") == 0)
	{
		ag_stop();
		app_protocol_send_response("OK", "STOP");
	}
	else if (strcmp(protocol_cmd.cmd, "RECORD") == 0)
	{
		uint8_t id = atoi(protocol_cmd.data);
		if (ag_record_start(id) == 0)
		{
			app_protocol_send_response("OK", "RECORD_START");
		}
		else
		{
			app_protocol_send_response("ERR", "RECORD_FAIL");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "FRAME") == 0)
	{
		if (ag_record_frame() == 0)
		{
			app_protocol_send_response("OK", "FRAME");
		}
		else
		{
			app_protocol_send_response("ERR", "FRAME_FAIL");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "SAVE") == 0)
	{
		if (ag_save() == 0)
		{
			app_protocol_send_response("OK", "SAVE");
		}
		else
		{
			app_protocol_send_response("ERR", "SAVE_FAIL");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "LIST") == 0)
	{
		char list_buf[512];
		ag_list(list_buf, sizeof(list_buf));
		app_protocol_send_response("OK", list_buf);
	}
	else if (strcmp(protocol_cmd.cmd, "DELETE") == 0)
	{
		uint8_t id = atoi(protocol_cmd.data);
		if (ag_delete(id) == 0)
		{
			app_protocol_send_response("OK", "DELETE");
		}
		else
		{
			app_protocol_send_response("ERR", "DELETE_FAIL");
		}
	}
	else
	{
		app_protocol_send_response("ERR", "UNKNOWN_AG_CMD");
	}
}

/**
  * @brief  处理传感器命令
  * @param  无
  * @返回值 无
  * @说明   支持命令:
  *         TEMP - 读取温度
  *         HUM - 读取湿度
  *         DIST - 读取距离
  *         VOLT - 读取电压
  *         ALL - 读取所有传感器
  */
static void protocol_handle_sensor(void)
{
	char   data_buf[128];
	float  value;

	if (strcmp(protocol_cmd.cmd, "TEMP") == 0)
	{
		value = sensor_read_temp();
		sprintf(data_buf, "TEMP:%.1f", value);
		app_protocol_send_response("OK", data_buf);
	}
	else if (strcmp(protocol_cmd.cmd, "HUM") == 0)
	{
		value = sensor_read_humidity();
		sprintf(data_buf, "HUM:%.1f", value);
		app_protocol_send_response("OK", data_buf);
	}
	else if (strcmp(protocol_cmd.cmd, "DIST") == 0)
	{
		value = sensor_read_distance();
		sprintf(data_buf, "DIST:%.1f", value);
		app_protocol_send_response("OK", data_buf);
	}
	else if (strcmp(protocol_cmd.cmd, "VOLT") == 0)
	{
		value = sensor_read_voltage();
		sprintf(data_buf, "VOLT:%.2f", value);
		app_protocol_send_response("OK", data_buf);
	}
	else if (strcmp(protocol_cmd.cmd, "ALL") == 0)
	{
		sensor_read_all();
		sensor_data_t *sd = sensor_get_data();
		sprintf(data_buf, "T:%.1f,H:%.1f,D:%.1f,V:%.2f",
			sd->temperature, sd->humidity, sd->distance, sd->voltage);
		app_protocol_send_response("OK", data_buf);
	}
	else
	{
		app_protocol_send_response("ERR", "UNKNOWN_SENSOR_CMD");
	}
}

/**
  * @brief  处理视觉命令(转发到OpenMV)
  * @param  无
  * @返回值 无
  * @说明   将命令通过UART2转发到OpenMV模块
  */
static void protocol_handle_vision(void)
{
	/* 构建转发命令 */
	sprintf(protocol_tx_buf, "#VISION:%s:%s!", protocol_cmd.cmd, protocol_cmd.data);

	/* 通过UART2发送到OpenMV */
	uart2_send_str(protocol_tx_buf);

	/* 回复确认 */
	app_protocol_send_response("OK", "VISION_FWD");
}

/**
  * @brief  处理系统命令
  * @param  无
  * @返回值 无
  * @说明   支持命令:
  *         RESET - 系统复位
  *         ESTOP - 紧急停止
  *         SAFETY - 获取安全状态
  *         CONFIG:save - 保存配置
  *         CONFIG:load - 加载配置
  *         CONFIG:reset - 恢复出厂设置
  *         INFO - 获取系统信息
  */
static void protocol_handle_sys(void)
{
	if (strcmp(protocol_cmd.cmd, "RESET") == 0)
	{
		app_protocol_send_response("OK", "RESET");
		/* 软件复位 */
		NVIC_SystemReset();
	}
	else if (strcmp(protocol_cmd.cmd, "ESTOP") == 0)
	{
		safety_emergency_stop();
		app_protocol_send_response("OK", "ESTOP");
	}
	else if (strcmp(protocol_cmd.cmd, "SAFETY") == 0)
	{
		char buf[32];
		safety_status_t status = safety_get_status();
		sprintf(buf, "SAFETY:%d", status);
		app_protocol_send_response("OK", buf);
	}
	else if (strcmp(protocol_cmd.cmd, "CONFIG") == 0)
	{
		if (strcmp(protocol_cmd.data, "save") == 0)
		{
			app_config_save();
			app_protocol_send_response("OK", "CONFIG_SAVED");
		}
		else if (strcmp(protocol_cmd.data, "load") == 0)
		{
			app_config_load();
			app_protocol_send_response("OK", "CONFIG_LOADED");
		}
		else if (strcmp(protocol_cmd.data, "reset") == 0)
		{
			app_config_reset();
			app_protocol_send_response("OK", "CONFIG_RESET");
		}
		else
		{
			app_protocol_send_response("ERR", "UNKNOWN_CONFIG_CMD");
		}
	}
	else if (strcmp(protocol_cmd.cmd, "INFO") == 0)
	{
		char info_buf[128];
		sprintf(info_buf, "FW:V1.0.0,MCU:STM32F103C8T6,NAME:智能采样机械臂");
		app_protocol_send_response("OK", info_buf);
	}
	else
	{
		app_protocol_send_response("ERR", "UNKNOWN_SYS_CMD");
	}
}

/**
  * @brief  处理总线舵机命令
  * @param  无
  * @返回值 无
  * @说明   直接转发原始总线舵机命令到UART3
  */
static void protocol_handle_bus(void)
{
	/* 直接通过UART3发送原始命令 */
	uart3_send_str(protocol_cmd.data);
	app_protocol_send_response("OK", "BUS");
}

/* ========================================================================== */
/*                     YH-K32 协议格式支持                                     */
/* ========================================================================== */

/**
  * @brief  解析YH-K32协议格式命令
  * @param  data: 接收到的数据字符串
  * @param  len: 数据长度
  * @返回值 0: 成功(YH-K32格式), 1: 失败(非YH-K32格式)
  * @说明   检测并解析YH-K32格式命令:
  *         - #NNNPNNNNTNNNN!  → 单舵机 (NNN=3位ID, NNNN=4位PWM, NNNN=4位时间)
  *         - {#NNNPNNNNTNNNN!...}  → 多舵机
  *         - $DST! 或 $DST:x!  → 停止
  *         - $RST!  → 复位
  *         - $DGT:x-y,n!  → 动作组
  */
static uint8_t protocol_parse_yhk32(char *data, uint16_t len)
{
	char *p_start;
	char first_char;

	/* 查找第一个有效字符 */
	p_start = data;
	while (*p_start == ' ' || *p_start == '\r' || *p_start == '\n')
	{
		p_start++;
	}

	first_char = *p_start;

	/* 检测YH-K32多舵机命令: { ... } */
	if (first_char == '{')
	{
		char *p_end = strchr(p_start, '}');
		if (p_end != NULL)
		{
			/* 提取{}内的多舵机命令 */
			uint16_t data_len = (uint16_t)(p_end - p_start - 1);
			if (data_len > 0 && data_len < sizeof(protocol_cmd.data))
			{
				memcpy(protocol_cmd.data, p_start + 1, data_len);
				protocol_cmd.data[data_len] = '\0';
			}
			strcpy(protocol_cmd.prefix, "YHK32");
			strcpy(protocol_cmd.cmd, "MULTI");
			protocol_cmd.type = CMD_YHK32_MULTI;
			protocol_cmd.valid = 1;
			return 0;
		}
	}

	/* 检测YH-K32系统命令: $... */
	if (first_char == '$')
	{
		char *p_end = strchr(p_start, '!');
		if (p_end != NULL)
		{
			uint16_t cmd_len = (uint16_t)(p_end - p_start - 1);
			if (cmd_len > 0 && cmd_len < sizeof(protocol_cmd.cmd))
			{
				memcpy(protocol_cmd.cmd, p_start + 1, cmd_len);
				protocol_cmd.cmd[cmd_len] = '\0';
			}

			/* 提取参数(如果有) */
			{
				char *colon = strchr(protocol_cmd.cmd, ':');
				if (colon != NULL)
				{
					*colon = '\0';  /* 分离命令和参数 */
					strcpy(protocol_cmd.data, colon + 1);
				}
			}

			strcpy(protocol_cmd.prefix, "YHK32");
			protocol_cmd.type = CMD_YHK32_SYS;
			protocol_cmd.valid = 1;
			return 0;
		}
	}

	/* 检测YH-K32单舵机命令: #NNNPNNNNTNNNN! */
	/* 格式: # + 3位ID + P + 4位PWM + T + 4位时间 + ! */
	if (first_char == '#')
	{
		char *p = p_start + 1;

		/* 检查是否为数字(舵机ID) */
		if (*p >= '0' && *p <= '9')
		{
			/* 查找'P'字符 */
			char *p_p = strchr(p, 'P');
			if (p_p != NULL)
			{
				/* 查找'T'字符 */
				char *p_t = strchr(p_p, 'T');
				if (p_t != NULL)
				{
					/* 查找'!'结束符 */
					char *p_end = strchr(p_t, '!');
					if (p_end != NULL)
					{
						/* 确认是YH-K32格式: ID在P之前, PWM在P和T之间, 时间在T和!之间 */
						uint16_t id_len = (uint16_t)(p_p - p);
						uint16_t pwm_len = (uint16_t)(p_t - p_p - 1);
						uint16_t time_len = (uint16_t)(p_end - p_t - 1);

						if (id_len >= 1 && id_len <= 3 &&
						    pwm_len >= 1 && pwm_len <= 4 &&
						    time_len >= 1 && time_len <= 4)
						{
							/* 提取舵机ID */
							{
								char id_str[4] = {0};
								memcpy(id_str, p, id_len);
								protocol_cmd.data[0] = (char)atoi(id_str);  /* 存储ID */
							}

							/* 提取PWM值 */
							{
								char pwm_str[5] = {0};
								memcpy(pwm_str, p_p + 1, pwm_len);
								uint16_t pwm_val = (uint16_t)atoi(pwm_str);
								/* 存储到data[1-2] (Big-endian) */
								protocol_cmd.data[1] = (char)((pwm_val >> 8) & 0xFF);
								protocol_cmd.data[2] = (char)(pwm_val & 0xFF);
							}

							/* 提取时间值 */
							{
								char time_str[5] = {0};
								memcpy(time_str, p_t + 1, time_len);
								uint16_t time_val = (uint16_t)atoi(time_str);
								/* 存储到data[3-4] (Big-endian) */
								protocol_cmd.data[3] = (char)((time_val >> 8) & 0xFF);
								protocol_cmd.data[4] = (char)(time_val & 0xFF);
							}

							strcpy(protocol_cmd.prefix, "YHK32");
							strcpy(protocol_cmd.cmd, "SERVO");
							protocol_cmd.type = CMD_YHK32_SERVO;
							protocol_cmd.valid = 1;
							return 0;
						}
					}
				}
			}
		}
	}

	/* 非YH-K32格式 */
	return 1;
}

/**
  * @brief  处理YH-K32单舵机命令
  * @param  无
  * @返回值 无
  * @说明   从protocol_cmd.data中提取ID/PWM/Time并执行
  *         data[0] = ID, data[1-2] = PWM(BE), data[3-4] = Time(BE)
  */
static void protocol_handle_yhk32_servo(void)
{
	uint8_t  servo_id;
	uint16_t pwm_val;
	uint16_t time_val;

	/* 提取参数 */
	servo_id = (uint8_t)protocol_cmd.data[0];
	pwm_val  = (uint16_t)(((uint8_t)protocol_cmd.data[1] << 8) | (uint8_t)protocol_cmd.data[2]);
	time_val = (uint16_t)(((uint8_t)protocol_cmd.data[3] << 8) | (uint8_t)protocol_cmd.data[4]);

	/* 参数范围检查 */
	if (servo_id > 5)
	{
		app_protocol_send_response("ERR", "YHK32_ID_RANGE");
		return;
	}
	if (pwm_val < 500 || pwm_val > 2500)
	{
		app_protocol_send_response("ERR", "YHK32_PWM_RANGE");
		return;
	}

	/* 执行舵机移动 */
	app_arm_move_joint(servo_id, pwm_val, time_val);
	app_protocol_send_response("OK", "YHK32_SERVO");
}

/**
  * @brief  处理YH-K32多舵机命令
  * @param  data: 多舵机命令数据(不含{})
  * @param  len: 数据长度
  * @返回值 无
  * @说明   解析格式: #000P1500T1000!#001P0900T1000!...
  *         逐个解析并执行每个单舵机命令
  */
static void protocol_handle_yhk32_multi_servo(char *data, uint16_t len)
{
	char *p = data;
	uint8_t servo_count = 0;

	while (*p && servo_count < 6)
	{
		/* 查找下一个# */
		char *p_start = strchr(p, '#');
		if (p_start == NULL) break;

		/* 查找P */
		char *p_p = strchr(p_start + 1, 'P');
		if (p_p == NULL) break;

		/* 查找T */
		char *p_t = strchr(p_p + 1, 'T');
		if (p_t == NULL) break;

		/* 查找! */
		char *p_end = strchr(p_t + 1, '!');
		if (p_end == NULL) break;

		/* 提取ID */
		{
			char id_str[4] = {0};
			uint16_t id_len = (uint16_t)(p_p - p_start - 1);
			if (id_len > 3) id_len = 3;
			memcpy(id_str, p_start + 1, id_len);
			protocol_cmd.data[0] = (char)atoi(id_str);
		}

		/* 提取PWM */
		{
			char pwm_str[5] = {0};
			uint16_t pwm_len = (uint16_t)(p_t - p_p - 1);
			if (pwm_len > 4) pwm_len = 4;
			memcpy(pwm_str, p_p + 1, pwm_len);
			uint16_t pwm_val = (uint16_t)atoi(pwm_str);
			protocol_cmd.data[1] = (char)((pwm_val >> 8) & 0xFF);
			protocol_cmd.data[2] = (char)(pwm_val & 0xFF);
		}

		/* 提取时间 */
		{
			char time_str[5] = {0};
			uint16_t time_len = (uint16_t)(p_end - p_t - 1);
			if (time_len > 4) time_len = 4;
			memcpy(time_str, p_t + 1, time_len);
			uint16_t time_val = (uint16_t)atoi(time_str);
			protocol_cmd.data[3] = (char)((time_val >> 8) & 0xFF);
			protocol_cmd.data[4] = (char)(time_val & 0xFF);
		}

		/* 执行单个舵机命令 */
		protocol_handle_yhk32_servo();

		/* 移动到下一个命令 */
		p = p_end + 1;
		servo_count++;
	}

	app_protocol_send_response("OK", "YHK32_MULTI");
}

/**
  * @brief  处理YH-K32系统命令
  * @param  无
  * @返回值 无
  * @说明   支持的命令:
  *         DST     → 停止所有舵机
  *         DST:x   → 停止指定舵机
  *         RST     → 软件复位
  *         DGT:x-y,n → 播放动作组
  */
static void protocol_handle_yhk32_sys(void)
{
	if (strcmp(protocol_cmd.cmd, "DST") == 0)
		{
			/* 停止 */
			if (protocol_cmd.data[0] != '\0')
			{
				/* $DST:x! - 停止指定舵机 */
				/* 停止所有舵机(暂不支持单舵机停止) */
				app_arm_stop();
			}
		else
		{
			/* $DST! - 停止所有舵机 */
			app_arm_stop();
		}
		app_protocol_send_response("OK", "DST");
	}
	else if (strcmp(protocol_cmd.cmd, "RST") == 0)
	{
		/* 软件复位 */
		app_protocol_send_response("OK", "RST");
		delay_ms(100);  /* 等待发送完成 */
		NVIC_SystemReset();
	}
	else if (strcmp(protocol_cmd.cmd, "DGT") == 0)
	{
		/* 动作组: $DGT:start-end,count! */
		char *dash = strchr(protocol_cmd.data, '-');
		char *comma = strchr(protocol_cmd.data, ',');
		if (dash != NULL)
		{
			uint8_t start_id = (uint8_t)atoi(protocol_cmd.data);
			uint8_t end_id = (uint8_t)atoi(dash + 1);
			uint8_t count = 1;
			if (comma != NULL)
			{
				count = (uint8_t)atoi(comma + 1);
			}

			/* 播放动作组序列 */
			{
				uint8_t i;
				uint8_t play_count = (count == 0) ? 1 : count;  /* count=0表示循环, 暂播放1次 */
				uint8_t c;
				for (c = 0; c < play_count; c++)
				{
					for (i = start_id; i <= end_id && i <= 254; i++)
					{
						ag_play(i);
						/* 等待动作组播放完成 */
						delay_ms(2000);
					}
				}
			}
			app_protocol_send_response("OK", "DGT");
		}
		else
		{
			app_protocol_send_response("ERR", "DGT_PARAM");
		}
	}
	else
	{
		app_protocol_send_response("ERR", "UNKNOWN_YHK32_CMD");
	}
}

/**
  * @brief  发送协议响应
  * @param  type: 响应类型 "OK" 或 "ERR"
  * @param  data: 响应数据
  * @返回值 无
  * @说明   格式: #CMD:type:data!
  */
void app_protocol_send_response(char *type, char *data)
{
	/* 构建响应帧 */
	sprintf(protocol_tx_buf, "#CMD:%s:%s!", type, data);

	/* 通过UART1发送到树莓派 */
	uart1_send_str(protocol_tx_buf);
}

/**
  * @brief  处理接收到的UART1数据
  * @param  data: 接收到的数据
  * @param  len: 数据长度
  * @返回值 无
  */
void app_protocol_receive(char *data, uint16_t len)
{
	if (len < PROTOCOL_BUF_SIZE)
	{
		memcpy(protocol_rx_buf, data, len);
		protocol_rx_len = len;
		protocol_rx_buf[len] = '\0';
	}
}

/**
  * @brief  获取协议状态
  * @param  无
  * @返回值 0: 空闲, 1: 忙碌
  */
uint8_t app_protocol_get_status(void)
{
	return protocol_busy;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/