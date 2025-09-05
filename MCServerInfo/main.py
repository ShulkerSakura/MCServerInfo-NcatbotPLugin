# plugins/MCServerInfoPlugin/main.py
import os
import asyncio
import json
import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import PrivateMessage, GroupMessage

bot = CompatibleEnrollment

def parse_motd_node(node):
    """递归解析MOTD节点，提取所有文本内容"""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text_parts = []
        if 'text' in node:
            text_parts.append(node['text'])
        if 'extra' in node:
            for child in node['extra']:
                text_parts.append(parse_motd_node(child))
        return ''.join(text_parts)
    if isinstance(node, list):
        return ''.join(parse_motd_node(child) for child in node)
    return ''

def remove_color_codes(text):
    """移除Minecraft颜色代码（§后跟一个字符）"""
    return re.sub(r'§[0-9a-fk-orA-FK-OR]', '', text)

def parse_motd(json_data):
    """解析MOTD数据，支持多种格式"""
    # 解析JSON数据
    if isinstance(json_data, str):
        data = json.loads(json_data, strict=False)
    else:
        data = json_data

    # 提取MOTD部分
    if 'motd' not in data:
        return ""

    motd_data = data['motd']

    # 处理不同类型的MOTD格式
    if isinstance(motd_data, str):
        # 格式1: motd字段是字符串
        motd_text = motd_data
    elif isinstance(motd_data, dict):
        if 'text' in motd_data and ('extra' not in motd_data or not motd_data['extra']):
            # 格式2: motd字段是对象，且只有text字段
            motd_text = motd_data['text']
        else:
            # 复杂格式: motd字段是对象，包含extra等复杂结构
            motd_text = parse_motd_node(motd_data)
    else:
        motd_text = str(motd_data)

    # 移除颜色代码并返回
    return remove_color_codes(motd_text)

def format_server_info(json_data):
    """格式化服务器信息为指定输出格式"""
    # 解析JSON数据
    if isinstance(json_data, str):
        data = json.loads(json_data, strict=False)
    else:
        data = json_data

    # 提取各字段值，提供默认值以防字段缺失
    version = data.get('version', '未知')
    protocol = data.get('protocol', '未知')
    players_online = data.get('playersOnline', 0)
    max_players = data.get('maxPlayers', 0)
    ping = data.get('ping', 0)

    # 处理MOTD
    motd_text = parse_motd(data)

    # 格式化输出
    output_lines = [
        f"🖥️ 服务器信息:",
        f"版本: {version}",
        f"协议: {protocol}",
        f"玩家: {players_online}/{max_players}",
        f"延迟: {ping}ms",
        f"标语: {motd_text}"
    ]

    return "\n".join(output_lines)

class MCServerInfoPlugin(BasePlugin):
    name = "MCServerInfo"
    version = "1.0.0"

    # 1️⃣ 先定义帮助方法
    async def send_help(self, msg):
        help_text = (
            "📦 **MCServerInfo 插件使用说明**\n\n"
            "📌 命令格式：\n"
            "`/mcsinfo <服务器地址>`\n\n"
            "📌 说明：\n"
            "查询指定 Minecraft 服务器的版本、在线人数、延迟等信息。"
        )
        await msg.reply(text=help_text)

    # 2️⃣ 再定义 on_load，里面才能引用 send_help
    async def on_load(self):
        print(f"{self.name} 插件已加载 (版本: {self.version})")
        self.register_user_func(
            name="help",
            handler=self.send_help,
            prefix="/help",
            description="查看 MCServerInfo 插件帮助",
            usage="/help MCServerInfo",
            examples=["/help MCServerInfo"]
        )

    # 3️⃣ 其余事件处理
    @bot.private_event()
    async def on_private_message(self, msg: PrivateMessage):
        await self.handle_mc_command(msg)

    @bot.group_event()
    async def on_group_message(self, msg: GroupMessage):
        await self.handle_mc_command(msg)

    async def handle_mc_command(self, msg):
        raw_message = msg.raw_message.strip()
        if raw_message.startswith("/mcsinfo"):
            parts = raw_message.split(maxsplit=1)
            if len(parts) < 2:
                reply_text = "❌ 请输入服务器地址。\n用法：/mcsinfo <服务器地址>"
            else:
                server_address = parts[1].strip()
                reply_text = await self.run_mcserverinfo(server_address)
            await msg.reply(text=reply_text)

    async def run_mcserverinfo(self, server_address):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        jar_path = os.path.join(plugin_dir, "MCServerInfo-1.3.jar")

        if not os.path.isfile(jar_path):
            return f"❌ 未找到 JAR 文件: {jar_path}"

        try:
            process = await asyncio.create_subprocess_exec(
                "java", "-Dfile.encoding=UTF-8", "-jar", jar_path, "-c", "api", server_address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=plugin_dir
            )
            stdout, stderr = await process.communicate()

            try:
                output = stdout.decode("utf-8").strip()
            except UnicodeDecodeError:
                output = stdout.decode("gbk", errors="replace").strip()
            
            try:
                error = stderr.decode("utf-8").strip()
            except UnicodeDecodeError:
                error = stderr.decode("gbk", errors="replace").strip()

            if process.returncode != 0:
                return f"❌ 命令执行失败:\n{error}"
            if not output:
                return "⚠️ 命令执行成功，但无输出内容。"
            formated = format_server_info(output)
            return f"{formated}"

        except Exception as e:
            return f"❌ 运行命令时发生异常:\n{str(e)}"