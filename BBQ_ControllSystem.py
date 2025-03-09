class ExecutionLayer:
    """执行层：执行BBQ相关动作，接入推理执行API"""
    
    def __init__(self, debug_mode=True, inference_url="http://localhost:8888"):
        """初始化执行层，可设置debug模式和推理服务URL"""
        self.debug_mode = debug_mode
        self.inference_url = inference_url
        self.available_policies = self._get_available_policies()
        print(f"执行层初始化完成，可用策略: {self.available_policies}")
    
    def _get_available_policies(self):
        """获取可用策略列表"""
        try:
            response = requests.get(f"{self.inference_url}/policies")
            if response.status_code == 200:
                policies = response.json().get("available_policies", [])
                print(f"获取到可用策略: {policies}")
                return policies
            else:
                print(f"获取策略列表失败，状态码: {response.status_code}")
                return ["pick", "transfer", "place"]  # 默认策略
        except Exception as e:
            print(f"获取策略列表异常: {e}")
            return ["pick", "transfer", "place"]  # 默认策略
    
    def _create_inference_task(self, task_name, control_time_s=None):
        """创建推理任务"""
        # 确保任务名称有效
        if task_name not in self.available_policies:
            print(f"无效的任务名称: {task_name}，可用任务: {self.available_policies}")
            if self.debug_mode:
                return True
            return False
        
        # 准备请求数据
        payload = {
            "task_name": task_name,
            "single_task": None
        }
        
        # 如果提供了控制时间，添加到请求中
        if control_time_s is not None:
            payload["control_time_s"] = control_time_s
        
        try:
            print(f"创建推理任务: {task_name}")
            response = requests.post(f"{self.inference_url}/inference", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                print(f"任务创建成功: {result}")
                return True
            else:
                print(f"任务创建失败，状态码: {response.status_code}, 响应: {response.text}")
                return self.debug_mode
        except Exception as e:
            print(f"创建推理任务异常: {e}")
            return self.debug_mode
    
    def put_on_grill(self):
        """上炉动作 - 使用pick策略"""
        return self._create_inference_task("pick", 15.0)
    
    def turn_over(self):
        """翻面动作 - 使用transfer策略"""
        return self._create_inference_task("transfer", 20.0)
    
    def take_off_grill(self):
        """下炉动作 - 使用place策略"""
        return self._create_inference_task("place", 10.0)
    
    def season(self):
        """撒料动作 - 使用pick策略但时间较短"""
        return self._create_inference_task("pick", 8.0)

# 启动BBQ系统
if __name__ == "__main__":
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="BBQ控制系统")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--inference-url", default="http://localhost:8888", help="推理执行API地址")
    args = parser.parse_args()
    
    # 默认启用debug模式，除非明确指定--no-debug
    debug_mode = True if args.debug else True
    
    # 启动控制器
    bbq_controller = BBQController(API_KEY, debug_mode=debug_mode, inference_url=args.inference_url)
    bbq_controller.start() 