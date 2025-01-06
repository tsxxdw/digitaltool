from flask import Blueprint, render_template, request, jsonify, send_from_directory
import os
import json
import uuid
import shutil
import subprocess
from datetime import datetime
import threading
import time
import queue
from pathlib import Path
import platform
import random
import string
import asyncio
from concurrent.futures import ThreadPoolExecutor

bp = Blueprint('train', __name__)

# 获取项目根目录路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# 配置文件路径
SYSTEM_SETTINGS_FILE = os.path.join(ROOT_DIR, 'config/system_setting.json')
TRAIN_DIR = os.path.join(ROOT_DIR, 'file/train')

# 清空 TRAIN_DIR 目录
if os.path.exists(TRAIN_DIR):
    shutil.rmtree(TRAIN_DIR)
os.makedirs(TRAIN_DIR, exist_ok=True)

# 确保 config 目录存在
os.makedirs('config', exist_ok=True)

# 存储任务信息的全局字典
train_tasks = {}

# 任务队列和锁
current_task = None
task_queue = []  # 存储 TrainTask 对象
task_lock = threading.Lock()
task_thread = None

def load_system_settings():
    """加载系统设置"""
    try:
        with open(SYSTEM_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            os_type = platform.system()
            if os_type == "Windows":
                return settings.get('windows_musetalk_path', '')
            else:
                return settings.get('linux_musetalk_path', '')
    except Exception as e:
        print(f"加载系统设置失败: {str(e)}")
        return ''

# 获取对应操作系统的 MUSETALK 路径
MUSETALK = load_system_settings()
if not MUSETALK:
    print("警告: 未在 system_setting.json 中找到对应操作系统的 MUSETALK 路径配置")

class TrainTask:
    def __init__(self, task_id, name, video_name, audio_name):
        self.task_id = task_id
        self.name = name
        self.video_name = video_name
        self.audio_name = audio_name
        
        # 使用绝对路径
        task_dir = os.path.join(TRAIN_DIR, task_id)
        self.new_video_name = os.path.abspath(os.path.join(task_dir, f"{task_id}.mp4"))
        self.new_audio_name = os.path.abspath(os.path.join(task_dir, f"{task_id}.wav"))
        self.yaml_file = os.path.abspath(os.path.join(task_dir, f"{task_id}.yaml"))
        self.log_file = os.path.abspath(os.path.join(task_dir, f"{task_id}.log"))
        # 修改 save_path 的文件名格式
        self.save_path = os.path.abspath(os.path.join(task_dir, f"save_path_{task_id}.mp4"))
        
        self.status = "等待中"
        self.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.process = None
        
    def to_dict(self):
        return {
            "name": self.name,
            "yaml_file": self.yaml_file,
            "status": self.status,
            "log_file": self.log_file,
            "create_time": self.create_time,
            "video_name": self.video_name,
            "audio_name": self.audio_name,
            "new_video_name": self.new_video_name,
            "new_audio_name": self.new_audio_name,
            "save_path": self.save_path  # 添加到配置中
        }

def generate_task_id():
    """生成任务ID - 年月日时分秒 + 4位随机字母"""
    now = datetime.now()
    # 生成4位随机字母
    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
    # 格式化日期时间 + 4位字母
    return f"{now.strftime('%Y%m%d%H%M%S')}_{letters}"

def convert_video(input_file, output_path):
    """转换视频为MP4格式"""
    # 保存上传的文件
    temp_path = os.path.join(os.path.dirname(output_path), "temp_" + input_file.filename)
    input_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.mp4'):
            shutil.copy2(temp_path, output_path)
        else:
            cmd = f'ffmpeg -i "{temp_path}" -c:v libx264 -preset medium -crf 23 "{output_path}"'
            subprocess.run(cmd, shell=True, check=True)
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

def convert_audio(input_file, output_path):
    """转换音频为WAV格式"""
    # 保存上传的文件
    temp_path = os.path.join(os.path.dirname(output_path), "temp_" + input_file.filename)
    input_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.wav'):
            shutil.copy2(temp_path, output_path)
        else:
            cmd = f'ffmpeg -i "{temp_path}" "{output_path}"'
            subprocess.run(cmd, shell=True, check=True)
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

def create_yaml_file(task_id, new_video_name, new_audio_name):
    """创建YAML配置文件"""
    yaml_content = f"""{task_id}:
  preparation: True
  bbox_shift: 5
  video_path: {new_video_name}
  audio_clips:
    audio_0: {new_audio_name}
"""
    yaml_path = os.path.join(TRAIN_DIR, task_id, f"{task_id}.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

def get_command(yaml_path, save_path):
    """根据操作系统生成对应的命令"""
    if not MUSETALK:
        raise ValueError("MUSETALK 路径未配置")
        
    os_type = platform.system()
    
    if os_type == "Windows":
        # Windows 环境下，使用 cmd 激活 conda 环境并执行命令
        return f'cmd /c "cd /d {MUSETALK} && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {yaml_path} --save_path {save_path}"'
    else:
        # Linux/macOS 环境下，先进入目录，然后激活环境并执行命令
        cmd = f'cd {MUSETALK} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {yaml_path} --save_path {save_path}'
        return f"bash -c '{cmd}'"  # 在Linux环境下包装命令

async def process_task_queue():
    """处理任务队列"""
    global current_task
    while True:
        try:
            with task_lock:
                if not current_task and task_queue:
                    current_task = task_queue[0]
                    current_task.status = "训练中"
                else:
                    await asyncio.sleep(3)
                    continue
            
            try:
                yaml_path = current_task.yaml_file
                save_path = current_task.save_path
                cmd = get_command(yaml_path, save_path)
                log_path = current_task.log_file
                
                # 写入初始日志
                with open(log_path, 'w', encoding='utf-8') as log_file:
                    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{start_time}] 开始训练...\n")
                
                # 使用异步执行命令
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=open(log_path, 'a', encoding='utf-8'),
                    stderr=asyncio.subprocess.STDOUT
                )
                current_task.process = process

                while True:
                    if process.returncode is not None:
                        break
                        
                    if os.path.exists(save_path):
                        with open(log_path, 'a', encoding='utf-8') as log_file:
                            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            log_file.write(f"[{end_time}] 训练完成，输出文件已生成\n")
                        
                        current_task.status = "已完成"
                        try:
                            process.terminate()
                            await asyncio.sleep(1)
                            if process.returncode is None:
                                process.kill()
                        except Exception as e:
                            with open(log_path, 'a', encoding='utf-8') as log_file:
                                log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 终止进程时出错: {str(e)}\n")
                        break
                    
                    await asyncio.sleep(1)
                
                if not os.path.exists(save_path):
                    with open(log_path, 'a', encoding='utf-8') as log_file:
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        log_file.write(f"[{end_time}] 训练失败，未生成输出文件\n")
                    current_task.status = "失败"
                
            except Exception as e:
                with open(log_path, 'a', encoding='utf-8') as log_file:
                    error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{error_time}] 执行出错: {str(e)}\n")
            
            finally:
                with task_lock:
                    if task_queue and task_queue[0] == current_task:
                        task_queue.pop(0)
                    current_task = None
                    
        except Exception as e:
            print(f"任务处理循环出错: {str(e)}")
            await asyncio.sleep(5)

def start_task_processing():
    """启动任务处理"""
    async def run_async():
        while True:
            await process_task_queue()
            await asyncio.sleep(5)

    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_async())

    # 在新线程中运行异步循环
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(run_in_thread)

# 修改启动代码
# threading.Thread(target=process_task_queue, daemon=True).start()
start_task_processing()

@bp.route('/train')
def train():
    return render_template('train.html')

@bp.route('/train/upload', methods=['POST'])
def upload():
    try:
        video = request.files['video']
        audio = request.files['audio']
        name = request.form['name']
        
        if not video or not audio or not name:
            return jsonify({'error': '请提供所有必需的文件和信息'})
        
        if not name.replace(' ', '').isalnum():
            return jsonify({'error': '训练对象名称只能包含字母、数字、汉字'})
        
        task_id = generate_task_id()
        task_dir = os.path.join(TRAIN_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            video_path = os.path.join(task_dir, f"{task_id}.mp4")
            audio_path = os.path.join(task_dir, f"{task_id}.wav")
            convert_video(video, video_path)
            convert_audio(audio, audio_path)
        except Exception as e:
            shutil.rmtree(task_dir)
            return jsonify({'error': f'文件转换失败: {str(e)}'})
        
        # 创建任务对象
        task = TrainTask(task_id, name, video.filename, audio.filename)
        
        # 创建YAML文件
        create_yaml_file(task_id, task.new_video_name, task.new_audio_name)
        
        # 存储到内存中
        train_tasks[task_id] = task
        
        # 添加到任务队列
        with task_lock:
            task_queue.append(task)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)})

@bp.route('/train/tasks')
def get_tasks():
    return jsonify({task_id: task.to_dict() for task_id, task in train_tasks.items()})

@bp.route('/train/task_status/<task_id>')
def task_status(task_id):
    if task_id not in train_tasks:
        return jsonify({'error': '任务不存在'})
    
    task = train_tasks[task_id]
    log_path = task.log_file
    
    # 读取日志文件
    logs = []
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = f.readlines()
    
    return jsonify({
        'status': task.status,
        'logs': logs  # 始终返回完整的日志
    })

@bp.route('/train/update_name', methods=['POST'])
def update_name():
    task_id = request.form['task_id']
    new_name = request.form['name']
    
    if not new_name.replace(' ', '').isalnum():
        return jsonify({'error': '名称只能包含字母、数字、汉字'})
    
    config = load_config()
    if task_id not in config:
        return jsonify({'error': '任务不存在'})
    
    config[task_id]['name'] = new_name
    save_config(config)
    
    return jsonify({'success': True})

@bp.route('/train/delete_task', methods=['POST'])
def delete_task():
    task_id = request.form['task_id']
    
    if task_id not in train_tasks:
        return jsonify({'error': '任务不存在'})
    
    try:
        # 如果任务正在训练中，需要先终止进程
        with task_lock:
            if current_task and current_task.task_id == task_id:
                if current_task.process:
                    try:
                        current_task.process.terminate()
                        current_task.process.wait()
                    except:
                        pass
                current_task = None
            
            # 从任务队列中移除
            task_queue[:] = [t for t in task_queue if t.task_id != task_id]
        
        # 删除任务目录
        task_dir = os.path.join(TRAIN_DIR, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
        
        # 从内存中删除
        del train_tasks[task_id]
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': f'删除任务失败: {str(e)}'}) 

@bp.route('/train/save_person', methods=['POST'])
def save_person():
    try:
        task_id = request.form['task_id']
        
        if task_id not in train_tasks:
            return jsonify({'error': '任务不存在'})
            
        task = train_tasks[task_id]
        if task.status != "已完成":
            return jsonify({'error': '只能保存已完成的任务'})
            
        # 确保目标目录存在
        sync_yaml_dir = os.path.join(ROOT_DIR, 'file/sync/yaml')
        os.makedirs(sync_yaml_dir, exist_ok=True)
        
        # 复制yaml文件
        yaml_filename = f"{task_id}.yaml"
        source_yaml = task.yaml_file
        target_yaml = os.path.join(sync_yaml_dir, yaml_filename)
        shutil.copy2(source_yaml, target_yaml)
        
        # 创建txt文件
        txt_filename = f"{task_id}.txt"
        txt_path = os.path.join(sync_yaml_dir, txt_filename)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(task.name)
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}) 

# 添加文件访问路由
@bp.route('/file/train/<path:filename>')
def serve_file(filename):
    """提供文件下载服务"""
    try:
        return send_from_directory('file/train', filename)
    except Exception as e:
        return jsonify({'error': f'文件访问失败: {str(e)}'}), 404 