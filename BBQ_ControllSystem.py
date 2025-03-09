import json
import time
from datetime import datetime
import requests
import threading
import re

# 全局配置
API_KEY = "sk-fkwtuizesuehmupvrdrdwjvijdguzqlvtkaeivnljfwzsntp"  # 修改为SiliconFlow API密钥
# LLM_MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct-128K"  # 使用SiliconFlow支持的模型
# LLM_MODEL_NAME = "moonshot-v1-8k"  # 使用SiliconFlow支持的模型
LLM_MODEL_NAME = "deepseek-v3-241226"  # 使用SiliconFlow支持的模型
BASE_URL = "http://localhost:8000"  # 本地执行层API地址
# API_URL = "https://api.siliconflow.cn/v1/chat/completions"  # SiliconFlow API地址
# API_URL = "https://api.moonshot.cn/v1"  # moonshot API地址
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions" # 修改为volces API地址

# 使用火山
import os
from volcenginesdkarkruntime import Ark
client = Ark(api_key=os.environ.get("ARK_API_KEY"))
print(os.environ.get("ARK_API_KEY"))


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
    
    def get_doneness(self):
        """获取当前食物成熟度"""
        return self.doneness
    
    def get_voice_command(self):
        """获取用户语音指令"""
        return self.last_voice_command
    
    def update_doneness(self, front_doneness, back_doneness):
        """更新食物成熟度（服务器API端点）"""
        self.doneness = {
            "front_doneness": front_doneness,
            "back_doneness": back_doneness
        }
        self.last_update_time = time.time()
        return {"status": "success", "timestamp": self.last_update_time}
    
    def update_voice_command(self, command):
        """更新语音指令（服务器API端点）"""
        if command:
            self.last_voice_command = command
            self.last_update_time = time.time()
        return {"status": "success", "command": command, "timestamp": self.last_update_time}

class ExecutionLayer:
    """执行层：执行BBQ相关动作"""
    
    def put_on_grill(self):
        """上炉动作"""
        try:
            response = requests.post(f"{BASE_URL}/actions/put_on_grill")
            return response.status_code == 200
        except Exception as e:
            print(f"上炉操作失败: {e}")
            return False
    
    def turn_over(self):
        """翻面动作"""
        try:
            response = requests.post(f"{BASE_URL}/actions/turn_over")
            return response.status_code == 200
        except Exception as e:
            print(f"翻面操作失败: {e}")
            return False
    
    def take_off_grill(self):
        """下炉动作"""
        try:
            response = requests.post(f"{BASE_URL}/actions/take_off_grill")
            return response.status_code == 200
        except Exception as e:
            print(f"下炉操作失败: {e}")
            return False
    
    def season(self):
        """撒料动作"""
        try:
            response = requests.post(f"{BASE_URL}/actions/season")
            return response.status_code == 200
        except Exception as e:
            print(f"撒料操作失败: {e}")
            return False

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
                print(f"[DEBUG] 使用火山引擎SDK发送LLM请求")
                
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
                print(f"[DEBUG] 原始LLM响应:\n{response_text[:1000]}...")
                
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
                print(f"[ERROR] 使用火山引擎SDK决策失败: {str(e)}")
                print("[DEBUG] 尝试使用HTTP请求方式作为备选")
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
    
    def __init__(self, api_key):
        self.perception = PerceptionLayer()
        self.decision = DecisionLayer(api_key)
        self.execution = ExecutionLayer()
        
        # 系统状态
        self.system_status = {
            "Current Grilling Side": "None",
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
    
    def execute_action(self, decision):
        """执行决策动作"""
        if not decision:
            return
        
        action = decision.get("Execution Information", {}).get("Current Action", "")
        
        if action == "Put on the grill":
            success = self.execution.put_on_grill()
            if success:
                self.system_status["Is On Grill"] = True
                self.system_status["Current Grilling Side"] = "Front"
        
        elif action == "Turn over":
            success = self.execution.turn_over()
            if success:
                # 翻面后更新当前烤制面
                if self.system_status["Current Grilling Side"] == "Front":
                    self.system_status["Current Grilling Side"] = "Back"
                else:
                    self.system_status["Current Grilling Side"] = "Front"
        
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
            
            time.sleep(5)  # 每5秒检查一次
    
    def start(self):
        """启动BBQ控制系统"""
        self.is_running = True
        
        # 启动超时检测线程
        self.timeout_thread = threading.Thread(target=self.check_doneness_timeout)
        self.timeout_thread.daemon = True
        self.timeout_thread.start()
        
        print("BBQ烧烤系统已启动，等待指令...")
        
        try:
            while self.is_running:
                # 获取感知数据
                doneness_data = self.perception.get_doneness()
                voice_command = self.perception.get_voice_command()
                
                # 检查成熟度是否有变化
                if (doneness_data["front_doneness"] != self.system_status["Front Doneness"] or
                    doneness_data["back_doneness"] != self.system_status["Back Doneness"]):
                    
                    # 更新成熟度变化时间
                    self.system_status["Last Doneness Change Time"] = time.time()
                    self.system_status["Front Doneness"] = doneness_data["front_doneness"]
                    self.system_status["Back Doneness"] = doneness_data["back_doneness"]
                
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
                
                time.sleep(5)  # 控制循环速率
                
        except KeyboardInterrupt:
            print("系统手动停止")
        finally:
            self.is_running = False
            if self.timeout_thread:
                self.timeout_thread.join(timeout=1)

# 启动BBQ系统
if __name__ == "__main__":
    controller = BBQController(API_KEY)
    controller.start()