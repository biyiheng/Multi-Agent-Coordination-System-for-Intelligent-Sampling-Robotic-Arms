/**
  ******************************************************************************
  * @file    SRC/flash/y_flash.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   Flash存储模块实现
  *          使用STM32内部Flash存储系统参数和动作组数据
  *          存储位置: 最后2KB用于参数存储(2页轮转)
  *          磨损均衡: 在两个页之间轮转，记录写入次数
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "y_flash.h"
#include <string.h>

/* 私有宏定义 ------------------------------------------------------------------*/
#define FLASH_ERASE_VALUE		0xFFFFFFFF	/* Flash擦除后默认值 */

/* 参数存储头结构体 ------------------------------------------------------------*/

/**
  * @brief  Flash参数页头部结构体
  *          用于标识有效参数页和版本信息
  */
typedef struct
{
	uint32_t magic;							/* 魔数标记 "SFHY" */
	uint32_t version;						/* 数据版本号 */
	uint32_t write_count;					/* 写入次数(用于磨损均衡) */
	uint32_t checksum;						/* 数据校验和 */
	uint16_t data_size;						/* 有效数据大小 */
	uint16_t reserved;						/* 保留 */
} flash_header_t;

/* 私有变量 --------------------------------------------------------------------*/
static flash_header_t flash_header;				/* 参数页头部 */
static uint8_t  flash_current_page;				/* 当前使用的参数页 */
static uint8_t  flash_status;					/* Flash存储状态 */
static uint32_t flash_action_base_addr;			/* 动作组存储基地址 */

/* 私有函数声明 ----------------------------------------------------------------*/
static uint32_t flash_calc_checksum(void *data, uint16_t size);
static uint8_t  flash_erase_page(uint32_t page_addr);
static uint8_t  flash_write_word(uint32_t addr, uint32_t data);
static uint8_t  flash_write_data(uint32_t addr, void *data, uint16_t size);
static uint8_t  flash_scan_params(void);

/**
  * @brief  Flash存储模块初始化
  * @param  无
  * @返回值 无
  * @说明   扫描参数页，确定当前有效页，设置动作组存储基地址
  */
void flash_init(void)
{
	/* 解锁Flash */
	FLASH_Unlock();

	/* 设置动作组存储基地址(最后8KB之前) */
	flash_action_base_addr = FLASH_ACTION_ADDR;

	/* 扫描参数页，确定有效页 */
	if (flash_scan_params() == 0)
	{
		flash_status = 0;	/* 正常 */
	}
	else
	{
		/* 参数页都无效，使用第一页 */
		flash_current_page = 1;
		flash_status = 1;	/* 未初始化 */
	}
}

/**
  * @brief  扫描参数页，确定哪个页包含有效数据
  * @param  无
  * @返回值 0: 找到有效页, 1: 未找到
  * @说明   检查两个页的魔数标记，选择写入次数多的有效页
  */
static uint8_t flash_scan_params(void)
{
	flash_header_t header1, header2;
	uint8_t valid1 = 0, valid2 = 0;

	/* 读取页1头部 */
	memcpy(&header1, (void*)FLASH_PARAM_ADDR1, sizeof(flash_header_t));

	/* 检查页1魔数 */
	if (header1.magic == FLASH_MAGIC_NUMBER)
	{
		valid1 = 1;
	}

	/* 读取页2头部 */
	memcpy(&header2, (void*)FLASH_PARAM_ADDR2, sizeof(flash_header_t));

	/* 检查页2魔数 */
	if (header2.magic == FLASH_MAGIC_NUMBER)
	{
		valid2 = 1;
	}

	if (valid1 && valid2)
	{
		/* 两页都有效，选择写入次数多的(更新的) */
		if (header1.write_count >= header2.write_count)
		{
			flash_current_page = 1;
		}
		else
		{
			flash_current_page = 2;
		}
		return 0;
	}
	else if (valid1)
	{
		flash_current_page = 1;
		return 0;
	}
	else if (valid2)
	{
		flash_current_page = 2;
		return 0;
	}

	/* 两页都无效 */
	return 1;
}

/**
  * @brief  计算数据校验和
  * @param  data: 数据指针
  * @param  size: 数据大小(字节)
  * @返回值 32位校验和
  * @说明   使用简单的累加校验和
  */
static uint32_t flash_calc_checksum(void *data, uint16_t size)
{
	uint32_t checksum = 0;
	uint8_t *p = (uint8_t*)data;
	uint16_t i;

	for (i = 0; i < size; i++)
	{
		checksum += p[i];
	}

	return checksum;
}

/**
  * @brief  擦除Flash页
  * @param  page_addr: 页起始地址
  * @返回值 0: 成功, 1: 失败
  */
static uint8_t flash_erase_page(uint32_t page_addr)
{
	FLASH_Status status;

	/* 清除Flash状态标志 */
	FLASH_ClearFlag(FLASH_FLAG_EOP | FLASH_FLAG_PGERR | FLASH_FLAG_WRPRTERR);

	/* 擦除指定页 */
	status = FLASH_ErasePage(page_addr);

	if (status != FLASH_COMPLETE)
	{
		return 1;
	}

	return 0;
}

/**
  * @brief  写入一个字(32位)到Flash
  * @param  addr: 目标地址
  * @param  data: 32位数据
  * @返回值 0: 成功, 1: 失败
  */
static uint8_t flash_write_word(uint32_t addr, uint32_t data)
{
	FLASH_Status status;

	/* 清除Flash状态标志 */
	FLASH_ClearFlag(FLASH_FLAG_EOP | FLASH_FLAG_PGERR | FLASH_FLAG_WRPRTERR);

	/* 编程一个字 */
	status = FLASH_ProgramWord(addr, data);

	if (status != FLASH_COMPLETE)
	{
		return 1;
	}

	return 0;
}

/**
  * @brief  写入数据块到Flash
  * @param  addr: 目标地址
  * @param  data: 数据指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  */
static uint8_t flash_write_data(uint32_t addr, void *data, uint16_t size)
{
	uint32_t *p32 = (uint32_t*)data;
	uint16_t  word_count = (size + 3) / 4;	/* 向上取整到4字节对齐 */
	uint16_t  i;
	uint32_t  word_data;

	for (i = 0; i < word_count; i++)
	{
		/* 处理最后不足4字节的情况 */
		if (i == word_count - 1 && (size % 4) != 0)
		{
			word_data = 0;
			memcpy(&word_data, &p32[i], size % 4);
		}
		else
		{
			word_data = p32[i];
		}

		if (flash_write_word(addr + i * 4, word_data) != 0)
		{
			return 1;
		}
	}

	return 0;
}

/**
  * @brief  保存系统参数到Flash
  * @param  data: 参数数据指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  * @说明   使用磨损均衡策略，在两个页之间轮转存储
  */
uint8_t flash_save_params(void *data, uint16_t size)
{
	uint32_t target_addr;
	uint8_t  target_page;

	if (size > FLASH_PARAM_SIZE)
	{
		return 1;	/* 数据太大 */
	}

	/* 确定目标页(与当前页交替) */
	if (flash_current_page == 1)
	{
		target_page = 2;
		target_addr = FLASH_PARAM_ADDR2;
	}
	else
	{
		target_page = 1;
		target_addr = FLASH_PARAM_ADDR1;
	}

	/* 擦除目标页 */
	if (flash_erase_page(target_addr) != 0)
	{
		flash_status = 2;
		return 1;
	}

	/* 构建头部 */
	flash_header.magic       = FLASH_MAGIC_NUMBER;
	flash_header.version     = 0x00010000;	/* V1.0.0 */
	flash_header.write_count = (flash_current_page == 1) ? 1 : 0;
	/* 从当前页读取写入次数并递增 */
	{
		flash_header_t old_header;
		uint32_t old_addr = (flash_current_page == 1) ? FLASH_PARAM_ADDR1 : FLASH_PARAM_ADDR2;
		memcpy(&old_header, (void*)old_addr, sizeof(flash_header_t));
		if (old_header.magic == FLASH_MAGIC_NUMBER)
		{
			flash_header.write_count = old_header.write_count + 1;
		}
		else
		{
			flash_header.write_count = 1;
		}
	}
	flash_header.data_size  = size;
	flash_header.checksum   = flash_calc_checksum(data, size);
	flash_header.reserved   = 0;

	/* 解锁Flash */
	FLASH_Unlock();

	/* 写入头部 */
	if (flash_write_data(target_addr, &flash_header, sizeof(flash_header_t)) != 0)
	{
		flash_status = 2;
		return 1;
	}

	/* 写入数据 */
	if (flash_write_data(target_addr + sizeof(flash_header_t), data, size) != 0)
	{
		flash_status = 2;
		return 1;
	}

	/* 锁定Flash */
	FLASH_Lock();

	/* 更新当前页 */
	flash_current_page = target_page;
	flash_status = 0;

	return 0;
}

/**
  * @brief  从Flash加载系统参数
  * @param  data: 参数数据缓冲区指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  * @说明   从最新的有效页加载参数数据
  */
uint8_t flash_load_params(void *data, uint16_t size)
{
	uint32_t src_addr;
	uint32_t checksum;

	if (flash_current_page == 1)
	{
		src_addr = FLASH_PARAM_ADDR1;
	}
	else
	{
		src_addr = FLASH_PARAM_ADDR2;
	}

	/* 读取头部 */
	memcpy(&flash_header, (void*)src_addr, sizeof(flash_header_t));

	/* 验证魔数 */
	if (flash_header.magic != FLASH_MAGIC_NUMBER)
	{
		return 1;
	}

	/* 验证数据大小 */
	if (flash_header.data_size > size || flash_header.data_size > FLASH_PARAM_SIZE)
	{
		return 1;
	}

	/* 读取数据 */
	memcpy(data, (void*)(src_addr + sizeof(flash_header_t)), flash_header.data_size);

	/* 校验数据 */
	checksum = flash_calc_checksum(data, flash_header.data_size);
	if (checksum != flash_header.checksum)
	{
		return 1;
	}

	return 0;
}

/**
  * @brief  擦除参数存储区
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   擦除两个参数页
  */
uint8_t flash_erase_params(void)
{
	FLASH_Unlock();

	if (flash_erase_page(FLASH_PARAM_ADDR1) != 0)
	{
		return 1;
	}

	if (flash_erase_page(FLASH_PARAM_ADDR2) != 0)
	{
		return 1;
	}

	FLASH_Lock();

	flash_current_page = 1;
	flash_status = 1;	/* 未初始化 */

	return 0;
}

/**
  * @brief  保存动作组到Flash
  * @param  group_id: 动作组ID
  * @param  data: 动作组数据指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  * @说明   每个动作组占一个Flash页(1KB)，最多支持8个动作组
  */
uint8_t flash_save_action_group(uint8_t group_id, void *data, uint16_t size)
{
	uint32_t target_addr;

	if (size > FLASH_PAGE_SIZE - sizeof(flash_header_t))
	{
		return 1;	/* 数据太大 */
	}

	if (group_id >= 8)
	{
		return 1;	/* 动作组ID超出范围 */
	}

	/* 计算目标地址: 每个动作组占用1KB */
	target_addr = flash_action_base_addr + (uint32_t)group_id * FLASH_PAGE_SIZE;

	/* 构建头部 */
	flash_header.magic       = FLASH_MAGIC_NUMBER;
	flash_header.version     = 0x00010000;
	flash_header.write_count = 1;
	flash_header.data_size   = size;
	flash_header.checksum    = flash_calc_checksum(data, size);
	flash_header.reserved    = 0;

	FLASH_Unlock();

	/* 擦除目标页 */
	if (flash_erase_page(target_addr) != 0)
	{
		FLASH_Lock();
		return 1;
	}

	/* 写入头部 */
	if (flash_write_data(target_addr, &flash_header, sizeof(flash_header_t)) != 0)
	{
		FLASH_Lock();
		return 1;
	}

	/* 写入数据 */
	if (flash_write_data(target_addr + sizeof(flash_header_t), data, size) != 0)
	{
		FLASH_Lock();
		return 1;
	}

	FLASH_Lock();

	return 0;
}

/**
  * @brief  从Flash加载动作组
  * @param  group_id: 动作组ID
  * @param  data: 数据缓冲区指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  */
uint8_t flash_load_action_group(uint8_t group_id, void *data, uint16_t size)
{
	uint32_t src_addr;
	uint32_t checksum;

	if (group_id >= 8)
	{
		return 1;
	}

	src_addr = flash_action_base_addr + (uint32_t)group_id * FLASH_PAGE_SIZE;

	/* 读取头部 */
	memcpy(&flash_header, (void*)src_addr, sizeof(flash_header_t));

	/* 验证魔数 */
	if (flash_header.magic != FLASH_MAGIC_NUMBER)
	{
		return 1;
	}

	/* 验证数据大小 */
	if (flash_header.data_size > size)
	{
		return 1;
	}

	/* 读取数据 */
	memcpy(data, (void*)(src_addr + sizeof(flash_header_t)), flash_header.data_size);

	/* 校验数据 */
	checksum = flash_calc_checksum(data, flash_header.data_size);
	if (checksum != flash_header.checksum)
	{
		return 1;
	}

	return 0;
}

/**
  * @brief  擦除动作组存储区
  * @param  无
  * @返回值 0: 成功, 1: 失败
  */
uint8_t flash_erase_action_groups(void)
{
	uint8_t i;

	FLASH_Unlock();

	for (i = 0; i < 8; i++)
	{
		uint32_t addr = flash_action_base_addr + (uint32_t)i * FLASH_PAGE_SIZE;
		if (flash_erase_page(addr) != 0)
		{
			FLASH_Lock();
			return 1;
		}
	}

	FLASH_Lock();

	return 0;
}

/**
  * @brief  获取Flash存储状态
  * @param  无
  * @返回值 0: 正常, 1: 未初始化, 2: 错误
  */
uint8_t flash_get_status(void)
{
	return flash_status;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/