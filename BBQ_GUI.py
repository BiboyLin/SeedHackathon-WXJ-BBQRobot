import sys
import json
import time
import threading
import requests
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QProgressBar, QFrame)
from PyQt5.QtGui import QPixmap, QMovie, QFont, QColor, QPainter
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread

class BBQStatusMonitor(QThread):
    """后台线程，用于从BBQ系统获取状态更新"""
    status_updated = pyqtSignal(dict)
    
    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url
        self.running = True
    
    def run(self):
        while self.running:
            try:
                # 从BBQ控制系统获取状态
                response = requests.get(f"{self.server_url}/api/status")
                if response.status_code == 200:
                    status_data = response.json()
                    self.status_updated.emit(status_data)
            except Exception as e:
                print(f"获取状态失败: {e}")
            
            # 每秒更新一次
            time.sleep(1)
    
    def stop(self):
        self.running = False


class BBQAnimationWidget(QLabel):
    """BBQ动画显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setAlignment(Qt.AlignCenter)
        
        # 加载不同状态的动画
        self.animations = {}
        
        # 动态扫描assets目录加载所有动画文件
        self.load_animations_from_directory("assets")
        
        # 添加动画键名映射，解决文件名与代码中使用的键名不匹配问题
        self.animation_key_map = {
            "put_on_grill": "put_on",
            "take_off_grill": "take_off",
            "turn_over": "turn_over",
            "idle": "idle",
            "season": "season"
        }
        
        # 如果没有找到任何动画，使用默认映射
        if not self.animations:
            print("警告：未找到任何动画文件，使用默认映射")
            animation_files = {
                "idle": "assets/bbq_idle.gif",
                "put_on": "assets/bbq_put_on.gif",
                "turn_over": "assets/bbq_turn_over.gif",
                "take_off": "assets/bbq_take_off.gif",
                "season": "assets/bbq_season.gif"
            }
            
            for key, path in animation_files.items():
                try:
                    movie = QMovie(path)
                    if movie.isValid():
                        self.animations[key] = movie
                    else:
                        print(f"无效的动画文件: {path}")
                except Exception as e:
                    print(f"加载动画文件出错 {path}: {e}")
        
        # 确保至少有一个idle动画
        if "idle" not in self.animations:
            print("创建空白idle动画")
            self.animations["idle"] = QMovie()
        
        # 设置默认动画
        self.current_animation = "idle"
        self.setMovie(self.animations[self.current_animation])
        self.animations[self.current_animation].start()
        
        # 打印所有可用的动画
        print(f"已加载的动画: {list(self.animations.keys())}")
        print(f"动画键名映射: {self.animation_key_map}")
    
    def load_animations_from_directory(self, directory):
        """从指定目录加载所有GIF动画文件"""
        if not os.path.exists(directory):
            print(f"动画目录不存在: {directory}")
            os.makedirs(directory, exist_ok=True)
            return
            
        print(f"扫描动画目录: {directory}")
        animation_count = 0
        
        # 遍历目录中的所有文件
        for filename in os.listdir(directory):
            if filename.lower().endswith('.gif'):
                # 从文件名提取动画键名
                animation_key = os.path.splitext(filename)[0]
                
                # 如果文件名包含前缀bbq_，则移除它
                if animation_key.startswith('bbq_'):
                    animation_key = animation_key[4:]
                
                file_path = os.path.join(directory, filename)
                print(f"尝试加载动画: {file_path} -> {animation_key}")
                
                try:
                    movie = QMovie(file_path)
                    if movie.isValid():
                        self.animations[animation_key] = movie
                        animation_count += 1
                        print(f"成功加载动画: {animation_key}")
                    else:
                        print(f"无效的动画文件: {file_path}")
                except Exception as e:
                    print(f"加载动画文件出错 {file_path}: {e}")
        
        print(f"从目录 {directory} 加载了 {animation_count} 个动画")
    
    def set_animation(self, animation_key):
        """切换当前播放的动画"""
        # 使用映射转换键名
        mapped_key = self.animation_key_map.get(animation_key, animation_key)
        
        if mapped_key not in self.animations:
            print(f"未找到动画: {animation_key}(映射为:{mapped_key})，使用idle代替")
            mapped_key = "idle"
        
        # 停止当前动画
        if self.current_animation in self.animations:
            self.animations[self.current_animation].stop()
        
        # 开始新动画
        self.current_animation = mapped_key
        self.setMovie(self.animations[self.current_animation])
        self.animations[self.current_animation].start()
        print(f"切换到动画: {animation_key} -> {mapped_key}")


class DonenessWidget(QFrame):
    """成熟度显示组件"""
    
    def __init__(self, side="前面", parent=None):
        super().__init__(parent)
        self.side = side
        self.doneness_level = 0
        self.percentage = 0  # 新增百分比值
        self.setMinimumSize(200, 120)
        self.setFrameShape(QFrame.Box)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 标题标签
        self.title_label = QLabel(f"{self.side}成熟度")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        
        # 成熟度进度条 - 修改为百分比显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # 修改为0-100的范围
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)  # 显示文本
        self.progress_bar.setFormat("%p%")  # 设置为百分比格式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444444;
                border-radius: 8px;
                background-color: #F5F5F5;
                min-height: 25px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #D32F2F, stop:0.5 #FFA000, stop:1 #FFCA28);
            }
        """)
        
        # 状态标签
        self.status_label = QLabel("生肉")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        
        # 添加至布局
        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def update_doneness(self, level, percentage=None):
        """更新成熟度等级和百分比"""
        # 如果档位没变，保留当前百分比
        if level == self.doneness_level and percentage is None:
            return
            
        self.doneness_level = level
        
        # 如果提供了百分比值，则使用提供的值
        if percentage is not None:
            self.percentage = percentage
        else:
            # 只在档位变化时重置百分比，否则保留当前百分比
            # 这样可以防止自动增长的百分比被重置
            if level == 0:
                # 0档位时，百分比在0-49%之间
                self.percentage = max(0, min(49, self.percentage))
            elif level == 1:
                # 1档位时，百分比在50-99%之间
                self.percentage = max(50, min(99, self.percentage))
            elif level == 2:
                # 2档位时，百分比为100%
                self.percentage = 100
        
        self.progress_bar.setValue(self.percentage)
        
        # 更新状态文本和颜色
        if level == 0:
            self.status_label.setText("生肉")
            self.status_label.setStyleSheet("color: #D32F2F;")
        elif level == 1:
            self.status_label.setText("熟肉")
            self.status_label.setStyleSheet("color: #FFA000;")
        elif level == 2:
            self.status_label.setText("焦黄")
            self.status_label.setStyleSheet("color: #FFCA28;")
    
    def increment_percentage(self):
        """增加1%的进度，如果当前档位小于2"""
        if self.doneness_level < 2:
            self.percentage = min(100, self.percentage + 1)
            self.progress_bar.setValue(self.percentage)
            
            # 检查是否达到下一档
            if self.percentage >= 50 and self.doneness_level == 0:
                self.doneness_level = 1
                self.status_label.setText("熟肉")
                self.status_label.setStyleSheet("color: #FFA000;")
            elif self.percentage >= 100:
                self.doneness_level = 2
                self.status_label.setText("焦黄")
                self.status_label.setStyleSheet("color: #FFCA28;")
            
            return True
        return False


class BBQStatusWidget(QFrame):
    """BBQ状态显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Box)
        self.setMinimumSize(200, 180)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 标题标签
        title_label = QLabel("系统状态")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        
        # 状态标签 - 删除撒料和在炉显示
        self.status_labels = {
            "current_side": QLabel("当前烤制面: 无"),
            "action": QLabel("当前动作: 无")
        }
        
        for label in self.status_labels.values():
            label.setFont(QFont("Microsoft YaHei", 10))
        
        # 添加到布局
        layout.addWidget(title_label)
        for label in self.status_labels.values():
            layout.addWidget(label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_status(self, status_data):
        """更新状态显示"""
        # 更新烤制面
        side = status_data.get("Current Grilling Side", "None")
        side_text = "正面" if side == "Front" else "反面" if side == "Back" else "无"
        self.status_labels["current_side"].setText(f"当前烤制面: {side_text}")
        
        # 更新当前动作
        action = status_data.get("Current Action", "无")
        action_map = {
            "Put on the grill": "上炉",
            "Turn over": "翻面",
            "Take off the grill": "下炉",
            "Season": "撒料",
            "Wait": "等待",
            "None": "无"
        }
        action_text = action_map.get(action, action)
        self.status_labels["action"].setText(f"当前动作: {action_text}")


class BBQGuiApp(QMainWindow):
    """BBQ GUI主窗口"""
    
    def __init__(self, server_url="http://localhost:7999"):
        super().__init__()
        self.server_url = server_url
        self.init_ui()
        
        # 启动状态监控线程
        self.status_monitor = BBQStatusMonitor(server_url)
        self.status_monitor.status_updated.connect(self.update_status)
        self.status_monitor.start()
        
        # 启动定时器用于演示动画切换
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self.demo_animation)
        self.demo_timer.start(10000)  # 每10秒切换一次动画
        
        # 记录当前状态和动作
        self.current_status = {}
        self.current_action = "idle"
        
        # 重新实现进度条更新计时器
        self.progress_counter = 0
        self.doneness_timer = QTimer(self)
        self.doneness_timer.timeout.connect(self.check_increment_doneness)
        self.doneness_timer.start(1000)  # 每秒检查一次
        
        print("所有计时器已启动")
    
    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("瓦香鸡BBQ控制系统")
        self.setMinimumSize(800, 600)
        self.resize(1920, 1080)  # 设置默认尺寸为1920*1080
        
        # 创建主窗口部件
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 顶部标题
        title_label = QLabel("瓦香鸡BBQ智能烧烤系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        
        # 创建动画显示区域
        self.animation_widget = BBQAnimationWidget()
        
        # 创建成熟度显示区域
        doneness_layout = QHBoxLayout()
        self.front_doneness = DonenessWidget(side="前面")
        self.back_doneness = DonenessWidget(side="后面")
        doneness_layout.addWidget(self.front_doneness)
        doneness_layout.addWidget(self.back_doneness)
        
        # 创建状态显示区域
        self.status_widget = BBQStatusWidget()
        
        # 添加底部状态标签
        self.status_bar_label = QLabel("系统已启动，等待操作...")
        
        # 组合布局
        main_layout.addWidget(title_label)
        main_layout.addWidget(self.animation_widget)
        main_layout.addLayout(doneness_layout)
        main_layout.addWidget(self.status_widget)
        main_layout.addWidget(self.status_bar_label)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def update_status(self, status_data):
        """更新UI显示的状态"""
        # 保存旧状态，用于检测变化
        old_status = self.current_status.copy() if self.current_status else {}
        
        # 更新当前状态
        self.current_status = status_data
        
        # 更新成熟度显示，但保留百分比进度
        front_doneness = status_data.get("Front Doneness", 0)
        back_doneness = status_data.get("Back Doneness", 0)
        
        # 只在档位变化时更新成熟度
        if "Front Doneness" not in old_status or front_doneness != old_status.get("Front Doneness"):
            print(f"前面成熟度档位变化: {old_status.get('Front Doneness', '无')} -> {front_doneness}")
            self.front_doneness.update_doneness(front_doneness)
        
        if "Back Doneness" not in old_status or back_doneness != old_status.get("Back Doneness"):
            print(f"后面成熟度档位变化: {old_status.get('Back Doneness', '无')} -> {back_doneness}")
            self.back_doneness.update_doneness(back_doneness)
        
        # 更新状态显示
        self.status_widget.update_status(status_data)
        
        # 获取当前动作并更新动画
        current_action = status_data.get("Current Action", "None")
        
        # 如果没有从Execution Information获取到动作，尝试直接从状态中获取
        if current_action == "None" or not current_action:
            execution_info = status_data.get("Execution Information", {})
            if execution_info:
                current_action = execution_info.get("Current Action", "None")
        
        # 检查是否刚上炉或刚下炉
        is_on_grill = status_data.get("Is On Grill", False)
        was_on_grill = old_status.get("Is On Grill", False)
        
        # 如果刚上炉，强制显示上炉动画
        if is_on_grill and not was_on_grill:
            print("检测到刚上炉，强制显示上炉动画")
            animation_key = "put_on_grill"
            self.animation_widget.set_animation(animation_key)
            self.current_action = animation_key
            # 延迟5秒后恢复到idle状态
            QTimer.singleShot(5000, lambda: self.animation_widget.set_animation("idle"))
            return
        
        # 如果刚下炉，强制显示下炉动画
        if was_on_grill and not is_on_grill:
            print("检测到刚下炉，强制显示下炉动画")
            animation_key = "take_off_grill"
            self.animation_widget.set_animation(animation_key)
            self.current_action = animation_key
            # 延迟5秒后恢复到idle状态
            QTimer.singleShot(5000, lambda: self.animation_widget.set_animation("idle"))
            return
        
        # 检查是否刚翻面
        current_side = status_data.get("Current Grilling Side", "None")
        previous_side = old_status.get("Current Grilling Side", "None")
        
        if (is_on_grill and was_on_grill and 
            current_side != previous_side and 
            current_side != "None" and previous_side != "None"):
            print(f"检测到翻面: {previous_side} -> {current_side}，强制显示翻面动画")
            animation_key = "turn_over"
            self.animation_widget.set_animation(animation_key)
            self.current_action = animation_key
            # 延迟5秒后恢复到idle状态
            QTimer.singleShot(5000, lambda: self.animation_widget.set_animation("idle"))
            return
        
        # 动作映射到动画
        action_to_animation = {
            "Put on the grill": "put_on_grill",
            "Turn over": "turn_over",
            "Take off the grill": "take_off_grill",
            "Season": "season",
            "Wait": "idle",
            "None": "idle"
        }
        
        # 打印当前动作，帮助调试
        print(f"当前动作: '{current_action}'")
        
        animation_key = action_to_animation.get(current_action, "idle")
        
        # 只在动作改变时更新动画
        if animation_key != self.current_action:
            print(f"动画变化: {self.current_action} -> {animation_key}")
            self.animation_widget.set_animation(animation_key)
            self.current_action = animation_key
        
        # 更新状态栏
        self.status_bar_label.setText(f"最后更新: {time.strftime('%H:%M:%S')}")
    
    def demo_animation(self):
        """用于演示的动画切换函数，只在没有真实状态时使用"""
        # 如果已连接到真实系统就不执行演示
        if self.current_status:
            self.demo_timer.stop()
            return
        
        # 循环切换动画
        animations = ["idle", "put_on_grill", "turn_over", "take_off_grill"]
        current_index = animations.index(self.current_action)
        next_index = (current_index + 1) % len(animations)
        self.animation_widget.set_animation(animations[next_index])
        self.current_action = animations[next_index]
    
    def check_increment_doneness(self):
        """检查是否应该增加成熟度"""
        # 增加计数器
        self.progress_counter += 1
        
        # 每10秒增加一次进度
        if self.progress_counter >= 10:
            print("达到10秒，准备增加成熟度")
            self.progress_counter = 0  # 重置计数器
            
            if not self.current_status:
                print("当前没有状态数据，跳过增加成熟度")
                return
            
            # 检查是否在烤架上
            is_on_grill = self.current_status.get("Is On Grill", False)
            if not is_on_grill:
                print("食物不在烤架上，跳过增加成熟度")
                return
            
            # 获取当前烤制面
            current_side = self.current_status.get("Current Grilling Side", "None")
            print(f"当前烤制面: {current_side}")
            
            # 增加相应面的成熟度
            if current_side == "Front":
                if self.front_doneness.doneness_level < 2:
                    old_percentage = self.front_doneness.percentage
                    self.front_doneness.increment_percentage()
                    print(f"增加前面成熟度 {old_percentage}% -> {self.front_doneness.percentage}%")
                else:
                    print(f"前面已完全熟透 ({self.front_doneness.percentage}%)，跳过")
            
            elif current_side == "Back":
                if self.back_doneness.doneness_level < 2:
                    old_percentage = self.back_doneness.percentage
                    self.back_doneness.increment_percentage()
                    print(f"增加后面成熟度 {old_percentage}% -> {self.back_doneness.percentage}%")
                else:
                    print(f"后面已完全熟透 ({self.back_doneness.percentage}%)，跳过")
            else:
                print(f"无效的烤制面: {current_side}，跳过增加成熟度")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.status_monitor.stop()
        self.status_monitor.wait()
        event.accept()


# 如果直接运行此文件
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BBQGuiApp()
    window.show()
    sys.exit(app.exec_()) 