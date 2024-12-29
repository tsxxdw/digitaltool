from flask import Blueprint, render_template, request, jsonify, send_from_directory
import os
import subprocess
import uuid
from datetime import datetime
import threading
import json
import platform
import shutil
from collections import deque
import time

bp = Blueprint('sync', __name__)

# 存储生成任务信息
sync_tasks = {}
# 任务队列
task_queue = deque()
# 任务锁
task_lock = threading.Lock()
# 任务处理线程
task_thread = None
# 是否正在处理任务
is_processing = False

# 添加配置文件路径
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(ROOT_DIR, 'config', 'system_setting.json')


class SyncTask:
    def __init__(self, task_id, trained_video_id, audio_name, person_name):
        self.task_id = task_id
        self.trained_video_id = trained_video_id
        self.audio_name = audio_name
        self.person_name = person_name
        self.status = "等待中"  # 只有三种状态：等待中、生成中、已失败
        self.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.output_file = None
        self.log = []
        self.yaml_path = None
        self.output_path = None
        
        # 添加日志文件路径
        task_dir = os.path.join('file', 'sync', 'out', task_id)
        self.log_file = os.path.abspath(os.path.join(task_dir, f'{task_id}.log'))

def update_yaml_audio_path(yaml_path, new_audio_path):
    """更新YAML文件中的音频路径和preparation参数"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml_content = f.readlines()
            
        new_yaml_content = []
        for line in yaml_content:
            if 'audio_0:' in line:
                # 保持缩进
                indent = len(line) - len(line.lstrip())
                new_yaml_content.append(' ' * indent + f'audio_0: {new_audio_path}\n')
            elif 'preparation:' in line:
                # 保持缩进
                indent = len(line) - len(line.lstrip())
                new_yaml_content.append(' ' * indent + 'preparation: False\n')
            else:
                new_yaml_content.append(line)
                
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.writelines(new_yaml_content)
            
    except Exception as e:
        raise Exception(f"更新YAML文件失败: {str(e)}")

@bp.route('/sync')
def sync():
    # 获取所有已训练的视频文件
    trained_videos = []
    yaml_dir = os.path.join('file', 'sync', 'yaml')
    
    if os.path.exists(yaml_dir):
        for file in os.listdir(yaml_dir):
            if file.endswith('.txt'):
                task_id = file[:-4]  # 移除.txt后缀
                txt_path = os.path.join(yaml_dir, file)
                yaml_path = os.path.join(yaml_dir, f"{task_id}.yaml")
                
                # 确保对应的yaml文件存在
                if os.path.exists(yaml_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            name = f.read().strip()
                        trained_videos.append({
                            'id': task_id,
                            'name': name
                        })
                    except Exception as e:
                        print(f"读取{txt_path}失败: {str(e)}")
    
    return render_template('sync.html', trained_videos=trained_videos)

@bp.route('/sync/upload', methods=['POST'])
def upload():
    try:
        if 'audio' not in request.files or 'trained_video' not in request.form:
            return jsonify({'error': '请选择训练好的视频和上传新的音频文件'})
            
        audio = request.files['audio']
        trained_video_id = request.form['trained_video']
        
        # 验证训练文件是否存在
        yaml_path = os.path.join('file', 'sync', 'yaml', f'{trained_video_id}.yaml')
        txt_path = os.path.join('file', 'sync', 'yaml', f'{trained_video_id}.txt')
        
        if not os.path.exists(yaml_path):
            return jsonify({'error': '所选视频的训练数据不存在'})
            
        # 读取训练对象名称
        with open(txt_path, 'r', encoding='utf-8') as f:
            person_name = f.read().strip()
            
        # 生成任务ID
        task_id = generate_task_id()
        
        # 创建任务专属目录
        task_dir = os.path.join('file', 'sync', 'out', task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 保存并转换音频文件到任务目录
        converted_audio_path = os.path.join(task_dir, f'{task_id}.wav')
        audio.save(converted_audio_path)
        
        # 转换音频为WAV格式
        try:
            if not converted_audio_path.lower().endswith('.wav'):
                temp_path = converted_audio_path + '.temp'
                os.rename(converted_audio_path, temp_path)
                cmd = f'ffmpeg -i "{temp_path}" "{converted_audio_path}"'
                subprocess.run(cmd, shell=True, check=True)
                os.remove(temp_path)
        except Exception as e:
            shutil.rmtree(task_dir)
            return jsonify({'error': f'音频转换失败: {str(e)}'})

        # 复制并修改yaml文件
        new_yaml_path = os.path.join(task_dir, f'{task_id}.yaml')
        shutil.copy2(yaml_path, new_yaml_path)
        
        # 获取项目根目录的绝对路径
        root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        # 获取音频文件的绝对路径
        abs_audio_path = os.path.abspath(converted_audio_path)
        
        # 更新yaml文件中的音频路径
        update_yaml_audio_path(new_yaml_path, abs_audio_path)
        
        # 生成输出视频文件路径
        output_path = os.path.join(task_dir, f'{task_id}_output.mp4')
        
        # 创建任务对象
        task = SyncTask(task_id, trained_video_id, audio.filename, person_name)
        task.yaml_path = os.path.abspath(new_yaml_path)  # 使用新的yaml文件路径
        task.output_path = os.path.abspath(output_path)
        
        # 存储任务并加入队列
        sync_tasks[task_id] = task
        with task_lock:
            task_queue.append(task)
            queue_position = len(task_queue)
            if queue_position > 1:
                task.log.append(f"任务已加入队列,当前位置: {queue_position}")
            else:
                task.log.append("任务已加入队列,即将开始处理...")
        
        # 启动任务处理
        start_task_processing()
            
        return jsonify({
            'task_id': task_id,
            'message': '任务已创建'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

def detect_encoding(text):
    """检测文本编码"""
    if isinstance(text, str):
        return 'utf-8'
    
    # 尝试常见的编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'ascii', 'iso-8859-1', 'utf-16', 'big5']
    
    # 首先尝试 chardet 检测
    try:
        import chardet
        result = chardet.detect(text)
        if result and result['encoding']:
            try:
                text.decode(result['encoding'])
                return result['encoding']
            except:
                pass
    except ImportError:
        pass

    # 如果 chardet 检测失败，尝试预定义的编码列表
    for encoding in encodings:
        try:
            text.decode(encoding)
            return encoding
        except:
            continue
            
    # 如果都失败了，使用 latin1（它能解码任何字节序列）
    return 'latin1'

def safe_decode(text):
    """安全解码文本"""
    if isinstance(text, str):
        return text
        
    encoding = detect_encoding(text)
    return text.decode(encoding)

def monitor_process(process, task, output_path):
    """监控进程输出"""
    task.status = "生成中"
    
    try:
        # 确保日志文件目录存在
        os.makedirs(os.path.dirname(task.log_file), exist_ok=True)
        
        # 打开日志文件
        with open(task.log_file, 'w', encoding='utf-8') as log_file:
            # 写入任务开始信息
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_file.write(f"[{start_time}] 开始处理任务\n")
            log_file.write(f"[{start_time}] 使用配置文件: {task.yaml_path}\n")
            log_file.flush()
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                    
                if line:
                    # 使用safe_decode处理输出
                    decoded_line = safe_decode(line)
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_message = f"[{timestamp}] {decoded_line.strip()}"
                    
                    # 添加到内存日志
                    task.log.append(log_message)
                    
                    # 写入日志文件
                    log_file.write(log_message + '\n')
                    log_file.flush()
                    
                    # 更新进度（如果有进度信息）
                    if "Progress:" in decoded_line:
                        try:
                            progress = int(decoded_line.split("Progress:")[1].strip().rstrip('%'))
                            task.progress = progress
                        except:
                            pass
                            
            # 写入任务完成状态
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if process.returncode == 0:
                task.status = "已完成"
                task.output_file = os.path.relpath(output_path).replace('\\', '/')
                log_file.write(f"[{end_time}] 任务完成\n")
            else:
                task.status = "生成失败"
                log_file.write(f"[{end_time}] 任务失败，返回码: {process.returncode}\n")
                
    except Exception as e:
        task.status = "生成失败"
        # 如果发生异常，尝试记录到日志文件
        try:
            with open(task.log_file, 'a', encoding='utf-8') as log_file:
                error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_file.write(f"[{error_time}] 发生错误: {str(e)}\n")
        except:
            pass

@bp.route('/sync/tasks')
def get_tasks():
    """获取所有任务"""
    tasks_dict = {}
    for task_id, task in sync_tasks.items():
        tasks_dict[task_id] = {
            'id': task.task_id,
            'person_name': task.person_name,
            'audio_name': task.audio_name,
            'status': task.status,
            'create_time': task.create_time,
            'output_file': task.output_file,
            'log': task.log
        }
    return jsonify(tasks_dict)

@bp.route('/sync/task_status/<task_id>')
def get_task_status(task_id):
    """获取单个任务状态"""
    if task_id not in sync_tasks:
        return jsonify({'error': '任务不存在'})

    task = sync_tasks[task_id]
    logs = []
    if os.path.exists(task.log_file):
        with open(task.log_file, 'r', encoding='utf-8') as f:
            logs = f.readlines()
    return jsonify({
        'status': task.status,
        'output_file': task.output_file,
        'logs': logs
    })

def generate_random_string(length):
    """生成指定长度的随机字符串"""
    import random
    import string
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(length))

def generate_task_id():
    """生成任务ID: 年月日时分秒_4位随机字符"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = generate_random_string(4)
    return f"{timestamp}_{random_str}" 

def start_task_processing():
    """启动定时任务处理"""
    def run_timer():
        while True:
            process_task_queue()
            time.sleep(5)  # 每5秒检查一次
            
    timer_thread = threading.Thread(target=run_timer)
    timer_thread.daemon = True
    timer_thread.start()

def process_task_queue():
    """处理任务队列"""
    current_task = None
    try:
        with task_lock:
            # 检查队列是否为空
            if not task_queue:
                return
            
            # 获取当前任务
            current_task = task_queue[0]
            
            # 如果当前任务正在生成中，检查是否已完成
            if current_task.status == "生成中":
                if os.path.exists(current_task.output_path):
                    current_task.status = "已完成"
                    current_task.output_file = os.path.relpath(current_task.output_path).replace(os.sep, '/')
                    task_queue.popleft()
                return
            
            # 开始处理新任务
            current_task.status = "生成中"
            current_task.log.append("开始处理任务...")
        
        # 以下操作不需要加锁
        # 读取配置文件
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        # 获取MUSETALK路径
        MUSETALK = config.get('windows_musetalk_path' if platform.system() == 'Windows' else 'linux_musetalk_path', '')
        if not MUSETALK:
            raise Exception("MUSETALK路径未配置")

        # 构建命令
        if platform.system() == 'Windows':
            cmd = f'cmd /c "cd /d {MUSETALK} && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {current_task.yaml_path} --save_path {current_task.output_path}"'
        else:
            cmd = f'cd {MUSETALK} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {current_task.yaml_path} --save_path {current_task.output_path}"'

        # 启动进程
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace'
        )
        
        # 写入日志
        log_dir = os.path.dirname(current_task.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # 在Linux下设置目录权限
        if platform.system() != 'Windows':
            os.chmod(log_dir, 0o755)
            
        with open(current_task.log_file, 'w', encoding='utf-8') as log_file:
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_file.write(f"[{start_time}] 开始处理任务\n")
            log_file.write(f"[{start_time}] 使用配置文件: {current_task.yaml_path}\n")
            log_file.flush()
            
            while process.poll() is None:
                if os.path.exists(current_task.output_path):
                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{end_time}] 生成完成，输出文件已生成\n")
                    with task_lock:
                        current_task.status = "已完成"
                        current_task.output_file = os.path.relpath(current_task.output_path).replace(os.sep, '/')
                        task_queue.popleft()
                    break
                
                # 读取并记录日志
                line = process.stdout.readline()
                if line:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_message = f"[{timestamp}] {line.strip()}"
                    current_task.log.append(log_message)
                    log_file.write(log_message + '\n')
                    log_file.flush()
                
                time.sleep(1)

    except Exception as e:
        if current_task:
            with task_lock:
                current_task.status = "生成失败"
                current_task.log.append(f"任务执行出错: {str(e)}")
            try:
                with open(current_task.log_file, 'a', encoding='utf-8') as log_file:
                    error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{error_time}] 发生错误: {str(e)}\n")
            except:
                pass

# 添加文件访问路由
@bp.route('/file/sync/out/<path:filename>')
def serve_file(filename):
    """提供文件下载服务"""
    try:
        return send_from_directory('file/sync/out', filename)
    except Exception as e:
        return jsonify({'error': f'文件访问失败: {str(e)}'}), 404


def init_delete_file():
    """初始化动作模块"""
    # 确保目录存在
    upload_dir = os.path.join('file', 'sync',"out")
    os.makedirs(upload_dir, exist_ok=True)

    # 清空上传目录
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"删除文件或目录失败: {file_path} - {str(e)}")