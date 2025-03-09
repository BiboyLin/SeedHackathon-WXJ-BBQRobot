import json
import time
from datetime import datetime
import requests
import threading
import re
from flask import Flask, request, jsonify

# 全局配置
API_KEY = "sk-fkwtuizesuehmupvrdrdwjvijdguzqlvtkaeivnljfwzsntp"  # 修改为SiliconFlow API密钥
# LLM_MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct-128K"  # 使用SiliconFlow支持的模型
# LLM_MODEL_NAME = "moonshot-v1-8k"  # 使用SiliconFlow支持的模型
LLM_MODEL_NAME = "deepseek-v3-241226"  # 使用SiliconFlow支持的模型

# API_URL = "https://api.siliconflow.cn/v1/chat/completions"  # SiliconFlow API地址
# API_URL = "https://api.moonshot.cn/v1"  # moonshot API地址
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions" # 修改为volces API地址

# 当前ServerURL定义
local_server_url = "http://localhost:7999"
Excute_URL = "http://localhost:8000"  # 本地执行层API地址

# 创建Flask应用
app = Flask(__name__)

# 使用火山
import os
from volcenginesdkarkruntime import Ark
client = Ark(api_key=os.environ.get("ARK_API_KEY"))
print(os.environ.get("ARK_API_KEY"))

# 全局实例
bbq_controller = None

class PerceptionLayer:
    """感知层：维护食物成熟度和语音指令状态（服务器逻辑）"""
    
    def __init__(self):
        self.last_voice_command = None
        # 添加内部状态存储
        self.doneness = {
            "front_doneness": 0,
            "back_doneness": 0
        }
        # 添加时间戳记录更新时间
        self.last_update_time = time.time()
        # 添加直接触发上炉指令的标志
        self.immediate_put_on_grill = False
    
    def get_doneness(self):
        """获取当前成熟度状态"""
        return self.doneness
    
    def get_voice_command(self):
        """获取最近的语音指令"""
        return self.last_voice_command
    
    def update_doneness(self, front_doneness, back_doneness):
        """更新成熟度状态"""
        # 更新两面的成熟度
        self.doneness["front_doneness"] = front_doneness
        self.doneness["back_doneness"] = back_doneness
        self.last_update_time = time.time()
        print(f"成熟度已更新: 前面={front_doneness}, 后面={back_doneness}")
    
    def update_voice_command(self, command):
        """更新语音指令"""
        self.last_voice_command = command
        print(f"语音指令已更新: {command}")
    
    def api_update_doneness(self, doneness):
        """成熟度接口（/api/v1/cooking/doneness）"""
        print(f"API更新成熟度: {doneness}")
        
        # 确保doneness是一个字典
        if not isinstance(doneness, dict):
            print(f"无效的成熟度数据类型: {type(doneness)}")
            return {"error": "Invalid doneness data type"}
        
        # 提取前面和后面的成熟度
        front_doneness = doneness.get("front_doneness")
        back_doneness = doneness.get("back_doneness")
        
        # 如果只提供了一个面的成熟度，保留另一个面的现有值
        if front_doneness is not None and back_doneness is None:
            back_doneness = self.doneness["back_doneness"]
            print(f"只提供了前面成熟度({front_doneness})，保留后面成熟度: {back_doneness}")
        elif back_doneness is not None and front_doneness is None:
            front_doneness = self.doneness["front_doneness"]
            print(f"只提供了后面成熟度({back_doneness})，保留前面成熟度: {front_doneness}")
        
        # 如果两个值都有效，更新两面的成熟度
        if front_doneness is not None and back_doneness is not None:
            # 确保值在有效范围内
            front_doneness = max(0, min(2, float(front_doneness)))
            back_doneness = max(0, min(2, float(back_doneness)))
            
            self.update_doneness(front_doneness, back_doneness)
            return {"front_doneness": front_doneness, "back_doneness": back_doneness}
        
        # 如果没有有效数据，返回错误
        print("没有有效的成熟度数据可更新")
        return {"error": "No valid doneness data to update"}
    
    def api_update_voice_command(self, voice_command):
        """语音指令接口（/api/v1/cooking/voice-command）"""
        command_map = {
            "0": "瓦香鸡唤醒",
            "1": "一把烤肉",
            "2": "两把烤肉", 
            "3": "一串烤肉"
        }
        command_text = command_map.get(str(voice_command), "未知指令")
        
        # 检查是否是需要立即上炉的指令
        if str(voice_command) in ["1", "2", "01", "02"]:
            self.immediate_put_on_grill = True
        else:
            self.immediate_put_on_grill = False
            
        self.update_voice_command(command_text)
        return {"voice_command": voice_command}

class ExecutionLayer:
    """执行层：执行BBQ相关动作"""
    
    def __init__(self, debug_mode=True):
        """初始化执行层，可设置debug模式"""
        self.debug_mode = debug_mode
    
    def put_on_grill(self):
        """上炉动作"""
        try:
            response = requests.post(f"{Excute_URL}/actions/put_on_grill")
            return response.status_code == 200
        except Exception as e:
            print(f"上炉操作失败: {e}")
            # 在debug模式下，即使失败也返回成功
            return self.debug_mode
    
    def turn_over(self):
        """翻面动作"""
        try:
            response = requests.post(f"{Excute_URL}/actions/turn_over")
            return response.status_code == 200
        except Exception as e:
            print(f"翻面操作失败: {e}")
            # 在debug模式下，即使失败也返回成功
            return self.debug_mode
    
    def take_off_grill(self):
        """下炉动作"""
        try:
            response = requests.post(f"{Excute_URL}/actions/take_off_grill")
            return response.status_code == 200
        except Exception as e:
            print(f"下炉操作失败: {e}")
            # 在debug模式下，即使失败也返回成功
            return self.debug_mode
    
    def season(self):
        """撒料动作"""
        try:
            response = requests.post(f"{Excute_URL}/actions/season")
            return response.status_code == 200
        except Exception as e:
            print(f"撒料操作失败: {e}")
            # 在debug模式下，即使失败也返回成功
            return self.debug_mode

class DecisionLayer:
    """决策层：使用LLM Agent进行决策"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.prompt_file = "BBQDecisionBrainPrompt.md"
        self.system_prompt = self._load_prompt()
        self.history = []
        self.use_volces_sdk = True  # 新增标志位，控制是否使用火山引擎SDK
    
    def _load_prompt(self):
        """加载系统提示词"""
        try:
            with open(self.prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"加载提示词失败: {e}")
            return ""
    
    def _extract_json_from_markdown(self, text):
        """从Markdown格式的响应中提取JSON内容"""
        # 查找```json和```之间的内容
        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, text)
        
        if matches:
            return matches[0]  # 返回第一个匹配的JSON内容
        return text  # 如果没找到，返回原始文本
    
    def make_decision(self, front_doneness, back_doneness, voice_command=None, system_status=None):
        """根据当前状态做出决策"""
        
        # 构建输入消息
        input_data = {
            "front_doneness": front_doneness,
            "back_doneness": back_doneness
        }
        
        if voice_command:
            input_data["voice_command"] = voice_command
        
        if system_status:
            input_data["system_status"] = system_status

        
        # 构建完整提示词
        user_message = f"请根据以下信息做出BBQ烧烤决策：\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"
        
        # 记录请求开始时间
        start_time = time.time()
        
        if self.use_volces_sdk:
            try:
                # print(f"[DEBUG] 使用火山引擎SDK发送LLM请求")
                
                # 使用火山引擎SDK调用LLM
                completion = client.chat.completions.create(
                    model=LLM_MODEL_NAME,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.1,
                    top_p=0.7,
                )
                
                # 计算响应时间
                response_time = time.time() - start_time
                print(f"[DEBUG] LLM响应时间: {response_time:.2f}秒")
                
                # 获取响应内容
                response_text = completion.choices[0].message.content
                # print(f"[DEBUG] 原始LLM响应:\n{response_text[:1000]}...")
                
                # 尝试将响应解析为JSON
                try:
                    decision = json.loads(response_text)
                    # print("[DEBUG] 直接JSON解析成功")
                    return decision
                except json.JSONDecodeError as e:
                    # 如果直接解析失败，尝试从Markdown中提取JSON
                    # print(f"[DEBUG] 直接解析JSON失败: {e}，尝试从Markdown中提取...")
                    json_text = self._extract_json_from_markdown(response_text)
                    # print(f"[DEBUG] 从Markdown提取的JSON内容:\n{json_text[:500]}...")
                    try:
                        decision = json.loads(json_text)
                        # print("[DEBUG] Markdown提取后JSON解析成功")
                        return decision
                    except json.JSONDecodeError as e:
                        # print(f"[DEBUG] 最终JSON解析失败: {e}")
                        # print(f"[ERROR] LLM返回的格式无法解析: {response_text[:200]}...")
                        return None
                
            except Exception as e:
                print(f"[ERROR] 使用火山引擎SDK决策失败: {str(e)}")
                # print("[DEBUG] 尝试使用HTTP请求方式作为备选")
                self.use_volces_sdk = False  # 失败后切换到HTTP请求方式
                
        # 如果未使用SDK或SDK调用失败，使用HTTP请求作为备选
        if not self.use_volces_sdk:
            try:
                payload = {
                    "model": LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "stream": False,
                    "max_tokens": 512,
                    "temperature": 0.1,
                    "top_p": 0.7,
                    "top_k": 50,
                    "frequency_penalty": 0.5,
                    "n": 1
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # 打印原始请求（隐藏API密钥）
                safe_headers = headers.copy()
                safe_headers["Authorization"] = "Bearer sk-***" 
                # print(f"\n[DEBUG] 发送LLM请求:\n请求URL: {API_URL}\n请求头: {safe_headers}\n请求体: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}...")
                
                response = requests.post(API_URL, json=payload, headers=headers)
                
                # 计算响应时间
                response_time = time.time() - start_time
                print(f"[DEBUG] LLM响应时间: {response_time:.2f}秒")
                
                response.raise_for_status()  # 检查请求是否成功
                
                # 打印原始响应
                raw_response = response.text
                print(f"[DEBUG] 原始LLM响应:\n{raw_response[:1000]}...")
                
                result = response.json()
                response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 尝试将响应解析为JSON
                try:
                    decision = json.loads(response_text)
                    print("[DEBUG] 直接JSON解析成功")
                    return decision
                except json.JSONDecodeError as e:
                    # 如果直接解析失败，尝试从Markdown中提取JSON
                    print(f"[DEBUG] 直接解析JSON失败: {e}，尝试从Markdown中提取...")
                    json_text = self._extract_json_from_markdown(response_text)
                    print(f"[DEBUG] 从Markdown提取的JSON内容:\n{json_text[:500]}...")
                    try:
                        decision = json.loads(json_text)
                        print("[DEBUG] Markdown提取后JSON解析成功")
                        return decision
                    except json.JSONDecodeError as e:
                        print(f"[DEBUG] 最终JSON解析失败: {e}")
                        print(f"[ERROR] LLM返回的格式无法解析: {response_text[:200]}...")
                        return None
                    
            except Exception as e:
                print(f"[ERROR] 决策失败: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return None

class BBQController:
    """BBQ控制系统：协调三层架构并处理超时状态"""
    
    def __init__(self, api_key, debug_mode=True):
        self.perception = PerceptionLayer()
        self.decision = DecisionLayer(api_key)
        self.execution = ExecutionLayer(debug_mode)
        self.debug_mode = debug_mode
        
        # 系统状态
        self.system_status = {
            "Current Grilling Side": "Back",
            "Front Doneness": 0,
            "Back Doneness": 0,
            "Expected Seasoning Times": 1,
            "Executed Seasoning Times": 0,
            "Is On Grill": False,
            "Last Doneness Change Time": time.time()
        }
        
        # 超时检测
        self.timeout_threshold = 240  # 秒
        self.is_running = False
        self.timeout_thread = None
        self.api_thread = None
        
        if debug_mode:
            print("BBQ控制系统运行在DEBUG模式，操作失败将被忽略")
            print(f"初始烤制面设置为: {self.system_status['Current Grilling Side']}")
    
    def execute_action(self, decision):
        """执行决策动作"""
        if not decision:
            return
        
        action = decision.get("Execution Information", {}).get("Current Action", "")
        
        if action == "Put on the grill":
            success = self.execution.put_on_grill()
            if success:
                self.system_status["Is On Grill"] = True
                # 修改上炉时的默认烤制面为后面
                self.system_status["Current Grilling Side"] = "Back"
                print(f"决策执行上炉，烤制面设置为: {self.system_status['Current Grilling Side']}")
        
        elif action == "Turn over":
            success = self.execution.turn_over()
            if success:
                # 翻面后更新当前烤制面
                if self.system_status["Current Grilling Side"] == "Front":
                    self.system_status["Current Grilling Side"] = "Back"
                else:
                    self.system_status["Current Grilling Side"] = "Front"
                print(f"翻面后烤制面变为: {self.system_status['Current Grilling Side']}")
        
        elif action == "Take off the grill":
            success = self.execution.take_off_grill()
            if success:
                self.system_status["Is On Grill"] = False
        
        elif action == "Season":
            success = self.execution.season()
            if success:
                self.system_status["Executed Seasoning Times"] += 1
        
        # 更新系统状态
        new_status = decision.get("System Status", {})
        for key, value in new_status.items():
            if key in self.system_status:
                self.system_status[key] = value
        
        # 执行完后重置语音指令
        self.perception.last_voice_command = None
    
    def check_doneness_timeout(self):
        """检查成熟度是否超时未变化"""
        while self.is_running:
            current_time = time.time()
            elapsed_time = current_time - self.system_status["Last Doneness Change Time"]
            
            if (elapsed_time > self.timeout_threshold and 
                self.system_status["Is On Grill"] and
                (self.system_status["Front Doneness"] < 2 or self.system_status["Back Doneness"] < 2)):
                
                print(f"检测到成熟度超时未变化，自动执行翻面操作")
                self.execution.turn_over()
                
                # 翻面后更新当前烤制面
                if self.system_status["Current Grilling Side"] == "Front":
                    self.system_status["Current Grilling Side"] = "Back"
                else:
                    self.system_status["Current Grilling Side"] = "Front"
                
                # 重置超时计时器
                self.system_status["Last Doneness Change Time"] = current_time
            
            time.sleep(20)  # 每5秒检查一次
    
    def start_api_server(self):
        """启动API服务器"""
        # 解析地址和端口的方式有问题，修改为更可靠的方式
        parsed_url = local_server_url.replace("http://", "").split(":")
        host = parsed_url[0]
        port = int(parsed_url[1]) if len(parsed_url) > 1 else 7999
        
        print(f"API服务器正在启动，监听地址: {host}:{port}")
        
        # 关键修改：将host设置为"0.0.0.0"以允许任何IP访问
        self.api_thread = threading.Thread(
            target=app.run, 
            kwargs={"host": "0.0.0.0", "port": port, "debug": False, "use_reloader": False}
        )
        self.api_thread.daemon = True
        self.api_thread.start()
        print(f"API服务器线程已启动")
    
    def start(self):
        """启动BBQ控制系统"""
        self.is_running = True
        
        # 启动API服务器
        self.start_api_server()
        
        # 启动超时检测线程
        self.timeout_thread = threading.Thread(target=self.check_doneness_timeout)
        self.timeout_thread.daemon = True
        self.timeout_thread.start()
        
        print("BBQ烧烤系统已启动，等待指令...")
        
        # 记录上次决策时间
        last_decision_time = time.time()
        # 决策间隔时间（秒）
        decision_interval = 10
        
        try:
            while self.is_running:
                # 获取感知数据
                doneness_data = self.perception.get_doneness()
                voice_command = self.perception.get_voice_command()
                
                # 当前时间
                current_time = time.time()
                
                # 检查是否有语音指令或者是否需要立即执行上炉操作
                has_voice_command = voice_command is not None
                immediate_action_needed = hasattr(self.perception, 'immediate_put_on_grill') and self.perception.immediate_put_on_grill
                
                # 检查是否需要立即执行上炉操作
                if immediate_action_needed:
                    print("检测到01或02指令，立即执行上炉操作")
                    success = self.execution.put_on_grill()
                    
                    # 即使在非debug模式下操作失败，也更新系统状态
                    # 这确保系统可以继续运行
                    if success or self.debug_mode:
                        print("上炉操作完成或处于DEBUG模式，更新系统状态")
                        self.system_status["Is On Grill"] = True
                        # 修改上炉时的默认烤制面为后面
                        self.system_status["Current Grilling Side"] = "Back"
                        print(f"上炉后烤制面设置为: {self.system_status['Current Grilling Side']}")
                    
                    # 重置标志位
                    self.perception.immediate_put_on_grill = False
                    # 执行完毕后重置语音指令
                    self.perception.last_voice_command = None
                    
                    # 更新上次决策时间
                    last_decision_time = current_time
                
                # 检查成熟度是否有变化，同时更新两面的成熟度
                if (doneness_data["front_doneness"] != self.system_status["Front Doneness"] or
                    doneness_data["back_doneness"] != self.system_status["Back Doneness"]):
                    
                    # 更新成熟度变化时间
                    self.system_status["Last Doneness Change Time"] = current_time
                    
                    # 更新两面的成熟度
                    old_front = self.system_status["Front Doneness"]
                    old_back = self.system_status["Back Doneness"]
                    self.system_status["Front Doneness"] = doneness_data["front_doneness"]
                    self.system_status["Back Doneness"] = doneness_data["back_doneness"]
                    
                    print(f"成熟度已更新: 前面 {old_front}->{doneness_data['front_doneness']}, 后面 {old_back}->{doneness_data['back_doneness']}")
                
                # 决策逻辑：有语音指令时立即决策，没有语音指令时每10秒决策一次
                should_make_decision = has_voice_command or (current_time - last_decision_time >= decision_interval)
                
                if should_make_decision:
                    # 做出决策
                    decision = self.decision.make_decision(
                        doneness_data["front_doneness"],
                        doneness_data["back_doneness"],
                        voice_command,
                        self.system_status
                    )
                    
                    # 执行决策
                    if decision:
                        print(f"决策结果: {json.dumps(decision, ensure_ascii=False)}")
                        self.execute_action(decision)
                        
                        # 更新上次决策时间
                        last_decision_time = current_time
                        
                        # 如果是响应语音指令的决策，重置语音指令
                        if has_voice_command:
                            self.perception.last_voice_command = None
                            print("语音指令已处理并重置")
                
                # 循环间隔降低到1秒，以便更快响应语音指令
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("接收到中断信号，系统关闭中...")
        finally:
            self.is_running = False
            print("BBQ系统已关闭")

# API路由定义
@app.route("/api/v1/cooking/doneness", methods=["POST"])
def update_doneness():
    """更新成熟度API"""
    try:
        # 添加详细日志，帮助调试
        print(f"收到成熟度更新请求: {request.data}")
        
        # 尝试多种方式解析请求数据
        try:
            data = request.get_json(force=True, silent=True)
        except Exception as e:
            print(f"JSON解析失败: {e}")
            data = None
            
        # 如果JSON解析失败，尝试表单数据
        if data is None:
            try:
                data = request.form.to_dict()
                # 尝试将字符串转换为数字
                if "front_doneness" in data:
                    data["front_doneness"] = float(data["front_doneness"])
                if "back_doneness" in data:
                    data["back_doneness"] = float(data["back_doneness"])
            except Exception as e:
                print(f"表单数据解析失败: {e}")
                data = None
                
        # 如果仍然没有数据，尝试直接解析请求体
        if data is None:
            try:
                import json
                data = json.loads(request.data.decode('utf-8'))
            except Exception as e:
                print(f"请求体解析失败: {e}")
                data = None
        
        # 如果所有方法都失败，返回错误
        if not data:
            print("无法解析请求数据")
            return jsonify({"error": "No data provided or invalid format"}), 400
        
        print(f"解析后的数据: {data}")
        
        # 验证数据格式
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid data format, expected JSON object"}), 400
        
        # 提取成熟度数据
        doneness = {}
        
        # 检查是否提供了前面成熟度
        if "front_doneness" in data:
            try:
                front_doneness = float(data["front_doneness"])
                if 0 <= front_doneness <= 2:
                    doneness["front_doneness"] = front_doneness
                else:
                    print(f"前面成熟度值超出范围: {front_doneness}")
            except (ValueError, TypeError) as e:
                print(f"前面成熟度值无效: {data['front_doneness']}, 错误: {e}")
        
        # 检查是否提供了后面成熟度
        if "back_doneness" in data:
            try:
                back_doneness = float(data["back_doneness"])
                if 0 <= back_doneness <= 2:
                    doneness["back_doneness"] = back_doneness
                else:
                    print(f"后面成熟度值超出范围: {back_doneness}")
            except (ValueError, TypeError) as e:
                print(f"后面成熟度值无效: {data['back_doneness']}, 错误: {e}")
        
        # 如果没有提供任何成熟度数据，尝试使用替代字段名
        if not doneness:
            # 尝试替代字段名
            alternative_fields = [
                ("frontDoneness", "front_doneness"),
                ("backDoneness", "back_doneness"),
                ("front", "front_doneness"),
                ("back", "back_doneness"),
                ("doneness_front", "front_doneness"),
                ("doneness_back", "back_doneness")
            ]
            
            for src_field, dst_field in alternative_fields:
                if src_field in data:
                    try:
                        value = float(data[src_field])
                        if 0 <= value <= 2:
                            doneness[dst_field] = value
                            print(f"使用替代字段 {src_field} -> {dst_field}: {value}")
                    except (ValueError, TypeError) as e:
                        print(f"替代字段 {src_field} 值无效: {data[src_field]}, 错误: {e}")
        
        # 如果仍然没有有效数据，检查是否有单一的doneness值
        if not doneness and "doneness" in data:
            try:
                value = float(data["doneness"])
                if 0 <= value <= 2:
                    # 根据当前烤制面决定更新哪一面：更新的是烤制面的反面
                    current_side = bbq_controller.system_status.get("Current Grilling Side", "Back")
                    if current_side == "Back":
                        doneness["front_doneness"] = value
                        print(f"使用单一成熟度值更新前面: {value}")
                    else:
                        doneness["back_doneness"] = value
                        print(f"使用单一成熟度值更新后面: {value}")
                else:
                    print(f"单一成熟度值超出范围: {value}")
            except (ValueError, TypeError) as e:
                print(f"单一成熟度值无效: {data['doneness']}, 错误: {e}")
        
        # 至少需要提供一个面的成熟度
        if not doneness:
            print("没有提供有效的成熟度数据")
            return jsonify({"error": "No valid doneness data provided"}), 400
        
        # 更新成熟度
        print(f"更新成熟度: {doneness}")
        result = bbq_controller.perception.api_update_doneness(doneness)
        return jsonify(result), 200
    
    except Exception as e:
        print(f"成熟度更新异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/cooking/voice-command", methods=["POST"])
def update_voice_command():
    """语音指令API路由"""
    print(f"[API DEBUG] 收到语音指令请求: {request}")
    # if not request.is_json:
    #     print("[API ERROR] 请求不是JSON格式")
    #     return jsonify({"error": "请求必须是JSON格式"}), 400
    
    data = request.get_json()
    print(f"[API DEBUG] 请求数据: {data}")
    if "voice_command" not in data:
        print("[API ERROR] 缺少voice_command参数")
        return jsonify({"error": "缺少voice_command参数"}), 400
    
    try:
        result = bbq_controller.perception.api_update_voice_command(data["voice_command"])
        print(f"[API] 成功更新语音命令: {data['voice_command']}")
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"[API ERROR] 处理语音指令请求时发生错误: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# 添加一个测试路由来确认API服务器正在运行
@app.route("/api/test", methods=["GET"])
def test_api():
    """测试API是否正常工作"""
    return jsonify({"status": "success", "message": "API服务器正常运行"})

@app.route("/api/status", methods=["GET"])
def get_system_status():
    """获取系统状态API"""
    if bbq_controller:
        status_data = {
            "Front Doneness": bbq_controller.system_status["Front Doneness"],
            "Back Doneness": bbq_controller.system_status["Back Doneness"],
            "Current Grilling Side": bbq_controller.system_status["Current Grilling Side"],
            "Is On Grill": bbq_controller.system_status["Is On Grill"],
            "Executed Seasoning Times": bbq_controller.system_status["Executed Seasoning Times"],
            "Expected Seasoning Times": bbq_controller.system_status["Expected Seasoning Times"]
        }
        
        # 获取最后一次决策信息
        last_decision = getattr(bbq_controller, 'last_decision', None)
        if last_decision:
            execution_info = last_decision.get("Execution Information", {})
            status_data["Execution Information"] = execution_info
        
        return jsonify(status_data)
    else:
        return jsonify({"error": "系统未初始化"}), 500

# 启动BBQ系统
if __name__ == "__main__":
    # 默认启用debug模式
    bbq_controller = BBQController(API_KEY, debug_mode=True)
    bbq_controller.start()