"""
BBQ决策系统核心逻辑 - 集成计时驱动机制
功能包含：
1. 成熟度驱动的状态迁移
    * 成熟度达到指定值时，触发状态迁移
2. 语音指令处理
    * 语音指令优先级最高，直接触发对应动作
3. 计时强制刷新机制
    * 成熟度卡滞时，强制刷新状态
4. 安全校验与冲突解决
    * 安全校验：撒料次数限制
    * 冲突解决：动作冷却时间
"""

from collections import deque
from enum import Enum
import time

class ActionType(Enum):
    LOAD = "上炉"
    FLIP = "翻面"
    SEASONING = "撒料"
    UNLOAD = "下炉"
    EMERGENCY_STOP = "紧急停止"

class BBQController:
    def __init__(self):
        # 状态机初始化
        self.state = "IDLE"
        self.current_side = 0  # 当前烤面 0:正面 1:反面
        self.last_maturity = 0
        self.seasoning_count = 0
        
        # 计时驱动参数
        self.STUCK_THRESHOLD = 10    # 连续相同读数次数
        self.TIMEOUT = 120           # 超时阈值(秒)
        self.maturity_history = deque(maxlen=self.STUCK_THRESHOLD)
        self.last_update_time = time.time()
        
        # 动作冷却时间
        self.action_cooldown = {
            ActionType.FLIP: 0,
            ActionType.SEASONING: 0
        }
        
        # 安全参数
        self.MAX_SEASONING = 2       # 最大撒料次数
    
    def update_sensors(self, maturity: int, voice_cmd: str = None):
        """主更新入口：处理传感器输入"""
        # 刷新计时器
        current_time = time.time()
        time_since_update = current_time - self.last_update_time
        
        # 处理成熟度数据
        self._handle_maturity(maturity, current_time)
        
        # 处理语音指令（最高优先级）
        if voice_cmd:
            self._handle_voice_command(voice_cmd)
            
        # 执行状态检查
        self._check_state_transition()
        
        # 更新动作冷却
        self._update_cooldown(current_time)
    
    def _handle_maturity(self, maturity: int, timestamp: float):
        """处理成熟度数据并检测卡顿"""
        self.maturity_history.append(maturity)
        self.last_update_time = timestamp
        
        # 触发卡顿检测
        if len(self.maturity_history) == self.STUCK_THRESHOLD:
            if len(set(self.maturity_history)) == 1:  # 连续N次相同
                print(f"[警告] 成熟度卡滞，强制刷新状态 (读数={maturity})")
                self._force_state_update()
    
    def _handle_voice_command(self, command: str):
        """处理语音指令"""
        cmd = command.strip().lower()
        
        # 指令映射表
        if "撒料" in cmd and self._check_safety(ActionType.SEASONING):
            self._trigger_action(ActionType.SEASONING)
        elif "停止" in cmd:
            self._trigger_action(ActionType.EMERGENCY_STOP)
    
    def _check_state_transition(self):
        """主状态迁移逻辑"""
        current_maturity = self.maturity_history[-1] if self.maturity_history else 0
        
        # 超时强制刷新
        if (time.time() - self.last_update_time) > self.TIMEOUT:
            print(f"[系统] {self.TIMEOUT}秒无更新，重置状态")
            self._reset_to_safe_state()
            return
        
        # 状态迁移条件
        if self.state == "COOKING_1":
            if current_maturity >= 2 and self.current_side == 0:
                self._trigger_action(ActionType.FLIP)
        elif self.state == "COOKING_2":
            if current_maturity >= 3 and self.seasoning_count < self.MAX_SEASONING:
                self._trigger_action(ActionType.SEASONING)
            elif current_maturity >=4:
                self._trigger_action(ActionType.UNLOAD)
    
    def _trigger_action(self, action: ActionType):
        """触发指定动作"""
        if self._check_cooldown(action):
            print(f"[动作] 执行：{action.value}")
            
            # 更新状态
            if action == ActionType.FLIP:
                self.current_side = 1
                self.state = "COOKING_2"
                self.action_cooldown[ActionType.FLIP] = time.time() + 30
            elif action == ActionType.SEASONING:
                self.seasoning_count +=1
                self.action_cooldown[ActionType.SEASONING] = time.time() + 15
            elif action == ActionType.UNLOAD:
                self.state = "COMPLETE"
    
    def _force_state_update(self):
        """强制状态刷新策略"""
        last_maturity = self.maturity_history[-1]
        
        if self.state == "COOKING_1" and last_maturity <2:
            print("[计时驱动] 触发强制翻面")
            self._trigger_action(ActionType.FLIP)
        elif self.state == "COOKING_2" and last_maturity <3:
            print("[计时驱动] 触发强制撒料")
            self._trigger_action(ActionType.SEASONING)
    
    def _check_cooldown(self, action: ActionType) -> bool:
        """检查动作冷却时间"""
        remaining = self.action_cooldown[action] - time.time()
        if remaining >0:
            print(f"[阻止] {action.value} 冷却中（剩余{int(remaining)}秒）")
            return False
        return True
    
    def _check_safety(self, action: ActionType) -> bool:
        """安全检查"""
        if action == ActionType.SEASONING:
            return self.seasoning_count < self.MAX_SEASONING
        return True
    
    def _reset_to_safe_state(self):
        """重置到安全状态"""
        self.state = "IDLE"
        self.current_side = 0
        self.maturity_history.clear()
        print("[系统] 已重置到安全待机状态")

    def _update_cooldown(self, current_time: float):
        """更新所有动作的冷却状态"""
        # 格式化冷却状态输出
        for action in self.action_cooldown:
            if current_time >= self.action_cooldown[action]:
                self.action_cooldown[action] = 0

    def get_cooldown_status(self) -> dict:
        """获取格式化的冷却状态"""
        current_time = time.time()
        status = {}
        for action, cooldown_time in self.action_cooldown.items():
            if cooldown_time > 0:
                remaining = max(0, cooldown_time - current_time)
                status[action.value] = round(remaining, 1)  # 保留一位小数
            else:
                status[action.value] = 0
        return status

# 使用示例
if __name__ == "__main__":
    controller = BBQController()
    
    # 模拟输入流
    test_cases = [
        (1, None),   # 第1秒
        (1, None),   # 第2秒 
        (1, "撒料"), # 第3秒（语音指令）
        (2, None),   # 第4秒
        (3, None),   # 第5秒
        (4, None)    # 第6秒
    ]
    
    for idx, (maturity, cmd) in enumerate(test_cases):
        print(f"\n=== 步骤 {idx+1} ===")
        controller.update_sensors(maturity, cmd)
        time.sleep(1)  # 模拟实时间隔

        # 打印当前状态
        print(f"当前状态: {controller.state}")
        print(f"当前成熟度: {controller.maturity_history[-1]}")
        print(f"当前撒料次数: {controller.seasoning_count}")

        print(f"当前冷却状态: {controller.get_cooldown_status()}")
