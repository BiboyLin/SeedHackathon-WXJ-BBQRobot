from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
import random
import asyncio
from typing import Optional

app = FastAPI()

# 模拟传感器数据
sensor_data = {
    "front_doneness": 0,
    "back_doneness": 0,
    "voice_command": ""
}

# 自动测试控制变量
auto_test_task: Optional[asyncio.Task] = None
auto_test_running = False

# 应用启动事件 - 自动开始循环测试
@app.on_event("startup")
async def startup_event():
    """应用启动时自动开始循环测试"""
    global auto_test_task, auto_test_running
    print("应用启动，自动开始成熟度循环测试...")
    auto_test_running = True
    auto_test_task = asyncio.create_task(doneness_auto_test())

# 应用关闭事件 - 清理资源
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global auto_test_task, auto_test_running
    if auto_test_running:
        print("应用关闭，停止成熟度循环测试...")
        auto_test_running = False
        if auto_test_task:
            auto_test_task.cancel()
            auto_test_task = None

# 模拟循环测试函数
async def doneness_auto_test():
    """自动递增成熟度的后台任务"""
    global sensor_data, auto_test_running
    
    doneness_states = [
        (0, 0), (0,0), (0,0),(1, 0), (1, 1), (2, 1), (2, 2)
    ]
    
    state_index = 0

    
    while auto_test_running:
        # 当state_index为0时，设置为初始状态：生成开始指令
        if state_index == 0:
            sensor_data["voice_command"] = "开始"

        # 设置当前状态
        front, back = doneness_states[state_index]
        sensor_data["front_doneness"] = front
        sensor_data["back_doneness"] = back
        print(f"自动测试: 成熟度更新为 front={front}, back={back}")
        
        # 移动到下一个状态
        state_index = (state_index + 1) % len(doneness_states)
        
        # 等待20秒
        await asyncio.sleep(20)

        # 达到2,2后，额外停止20s
        if front == 2 and back == 2:
            print("达到2,2后停止测试")
            await asyncio.sleep(20)

@app.get("/sensors/doneness")
async def get_doneness():
    """获取食物成熟度"""
    return {
        "front_doneness": sensor_data["front_doneness"],
        "back_doneness": sensor_data["back_doneness"]
    }

@app.get("/sensors/voice")
async def get_voice_command():
    """获取语音指令"""
    command = sensor_data["voice_command"]
    sensor_data["voice_command"] = ""  # 读取后清空
    return {"command": command}

@app.post("/actions/put_on_grill")
async def put_on_grill():
    """执行上炉动作"""
    print("执行动作: 食物上炉")
    sensor_data["front_doneness"] = 0
    sensor_data["back_doneness"] = 0
    return {"status": "success", "message": "食物已上炉"}

@app.post("/actions/turn_over")
async def turn_over():
    """执行翻面动作"""
    print("执行动作: 食物翻面")
    return {"status": "success", "message": "食物已翻面"}

@app.post("/actions/take_off_grill")
async def take_off_grill():
    """执行下炉动作"""
    print("执行动作: 食物下炉")
    return {"status": "success", "message": "食物已下炉"}

@app.post("/actions/season")
async def season():
    """执行撒料动作"""
    print("执行动作: 食物撒料")
    return {"status": "success", "message": "食物已撒料"}

# 测试用API：模拟改变成熟度和发送语音指令
class DonenessData(BaseModel):
    front: int = None
    back: int = None

@app.post("/test/set_doneness")
async def set_doneness(data: DonenessData):
    """设置食物成熟度（测试用）"""
    if data.front is not None:
        sensor_data["front_doneness"] = data.front
    if data.back is not None:
        sensor_data["back_doneness"] = data.back
    return {"status": "success", "doneness": get_doneness()}

@app.post("/test/set_voice/{command}")
async def set_voice(command: str):
    """设置语音指令（测试用）"""
    sensor_data["voice_command"] = command
    return {"status": "success", "command": command}

@app.post("/test/auto_doneness/start")
async def start_auto_doneness_test():
    """开始自动成熟度测试（每20秒递增）"""
    global auto_test_task, auto_test_running
    
    if auto_test_running:
        return {"status": "error", "message": "自动测试已在运行中"}
    
    auto_test_running = True
    auto_test_task = asyncio.create_task(doneness_auto_test())
    return {"status": "success", "message": "自动成熟度测试已启动"}

@app.post("/test/auto_doneness/stop")
async def stop_auto_doneness_test():
    """停止自动成熟度测试"""
    global auto_test_task, auto_test_running
    
    if not auto_test_running:
        return {"status": "error", "message": "没有正在运行的自动测试"}
    
    auto_test_running = False
    if auto_test_task:
        auto_test_task.cancel()
        auto_test_task = None
    
    return {"status": "success", "message": "自动成熟度测试已停止"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)