from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime
import shutil
import json
import platform
import threading
import queue
from collections import deque
import sys

bp = Blueprint('action', __name__)

# 存储生成任务信息
action_tasks = {}
# 任务队列
task_queue = deque()
# 任务锁
task_lock = threading.Lock()
# 任务处理线程
task_thread = None
# 是否正在处理任务
is_processing = False

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
    """安全地解码文本"""
    if isinstance(text, str):
        return text
        
    if isinstance(text, bytes):
        encoding = detect_encoding(text)
        try:
            return text.decode(encoding, errors='replace')
        except:
            # 如果检测到的编码仍然失败，使用 latin1
            return text.decode('latin1', errors='replace')
    
    return str(text)

class ActionTask:
    def __init__(self, task_id, video_path, audio_path):
        self.task_id = task_id
        self.video_path = video_path
        self.video_name = os.path.basename(video_path)
        self.audio_path = audio_path
        self.audio_name = os.path.basename(audio_path)
        self.status = "等待中"
        self.log = []
        self.output_file = None
        self.create_time = datetime.now()
        self.process = None
        self.log_queue = queue.Queue()
        self.log_file = os.path.join('static', 'action_uploads', task_id, 'task.log')
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def add_log(self, message):
        """添加日志并写入文件"""
        try:
            # 确保消息是字符串并正确编码
            message = safe_decode(message)
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{timestamp}] {message}"
            
            # 添加到内存日志
            self.log.append(log_entry)
            self.log_queue.put(log_entry)

            # 写入文件
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
            except UnicodeEncodeError:
                # 如果 UTF-8 编码失败，尝试使用系统默认编码
                with open(self.log_file, 'a', encoding=sys.getdefaultencoding(), errors='replace') as f:
                    f.write(log_entry + '\n')
                    
        except Exception as e:
            print(f"写入日志错误: {str(e)}")

    def load_logs(self):
        """从文件加载日志"""
        try:
            if os.path.exists(self.log_file):
                try:
                    # 首先尝试 UTF-8
                    with open(self.log_file, 'r', encoding='utf-8') as f:
                        self.log = [line.strip() for line in f.readlines()]
                except UnicodeDecodeError:
                    # 如果失败，尝试系统默认编码
                    with open(self.log_file, 'r', encoding=sys.getdefaultencoding(), errors='replace') as f:
                        self.log = [line.strip() for line in f.readlines()]
        except Exception as e:
            print(f"加载日志错误: {str(e)}")
            self.log = [f"加载日志出错: {str(e)}"]
        return self.log

def get_file_extension(filename):
    """获取文件扩展名（小写）"""
    return os.path.splitext(filename)[1].lower()

def convert_video_to_mp4(input_path, output_path):
    """将视频转换为MP4格式"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频转换错误: {e.stderr.decode()}")
        return False

def convert_audio_to_wav(input_path, output_path):
    """将音频转换为WAV格式"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            output_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频转换错误: {e.stderr.decode()}")
        return False

def process_output(task, pipe, is_error=False):
    """处理进程输出"""
    try:
        # 设置管道的编码为 utf-8
        if hasattr(pipe, 'reconfigure'):
            pipe.reconfigure(encoding='utf-8', errors='replace')
            
        while True:
            try:
                line = pipe.readline()
                if not line:
                    break
                    
                # 安全解码
                line = safe_decode(line).strip()
                
                if line:
                    task.add_log(line)
                    if is_error:
                        print(f"Error: {line}")
                    else:
                        print(f"Output: {line}")
            except Exception as e:
                error_msg = f"处理单行输出错误: {str(e)}"
                task.add_log(error_msg)
                print(error_msg)
                continue  # 继续处理下一行
                
    except Exception as e:
        error_msg = f"处理输出流错误: {str(e)}"
        task.add_log(error_msg)
        print(error_msg)

def process_task_queue():
    """处理任务队列"""
    global is_processing
    while True:
        with task_lock:
            if not task_queue:
                is_processing = False
                break
            
            # 检查队首任务的状态
            current_task = task_queue[0]
            if current_task.status != "等待中":
                # 如果不是等待中的任务，说明已经在处理或完成了
                if current_task.status == "完成":
                    # 如果完成了，移除任务
                    task_queue.popleft()
                    continue
                # 如果是处理中，等待处理完成
                break
            
            # 开始处理新任务
            current_task.status = "处理中"
            current_task.add_log("开始处理任务...")

        try:
            # 执行任务
            process = current_task.process
            if process:
                process.wait()  # 等待当前任务完成
                
                # 检查进程返回码
                if process.returncode == 0:
                    current_task.status = "完成"
                    current_task.add_log("任务处理完成")
                else:
                    current_task.status = "失败"
                    current_task.add_log(f"任务执行失败，返回码: {process.returncode}")
        except Exception as e:
            current_task.status = "失败"
            current_task.add_log(f"任务执行异常: {str(e)}")
        finally:
            with task_lock:
                if current_task.status in ["完成", "失败"]:
                    task_queue.popleft()  # 移除已完成或失败的任务

def start_task_processing():
    """启动任务处理"""
    global task_thread, is_processing
    with task_lock:
        if not is_processing and task_queue:
            # 检查是否有正在处理中的任务
            processing_tasks = [t for t in task_queue if t.status == "处理中"]
            if not processing_tasks:
                is_processing = True
                task_thread = threading.Thread(target=process_task_queue)
                task_thread.daemon = True
                task_thread.start()

@bp.route('/action')
def action():
    return render_template('action.html')

@bp.route('/action/upload', methods=['POST'])
def upload():
    if 'video' not in request.files or 'audio' not in request.files:
        return jsonify({'error': '请上传视频和音频文件'}), 400
        
    video = request.files['video']
    audio = request.files['audio']
    
    # 生成带时间戳的任务ID
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = str(uuid.uuid4())[:6]
    task_id = f"{current_time}-{random_str}"
    
    # 创建上传目录
    upload_dir = os.path.join('static', 'action_uploads', task_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 获取文件扩展名
    video_ext = get_file_extension(video.filename)
    audio_ext = get_file_extension(audio.filename)
    
    # 保存原始文件
    original_video_path = os.path.join(upload_dir, 'original_' + video.filename)
    original_audio_path = os.path.join(upload_dir, 'original_' + audio.filename)
    
    video.save(original_video_path)
    audio.save(original_audio_path)
    
    # 转换后的文件路径
    converted_video_path = os.path.join(upload_dir, f'{task_id}.mp4')
    converted_audio_path = os.path.join(upload_dir, f'{task_id}.wav')
    
    # 处理视频文件
    if video_ext == '.mp4':
        # 如果已经是MP4格式，直接复制
        shutil.copy2(original_video_path, converted_video_path)
        task_log = "视频已经是MP4格式，无需转换"
    else:
        # 需要转换为MP4格式
        if not convert_video_to_mp4(original_video_path, converted_video_path):
            shutil.rmtree(upload_dir)  # 清理临时文件
            return jsonify({'error': '视频格式转换失败'}), 400
        task_log = "视频已转换为MP4格式"
    
    # 处理音频文件
    if audio_ext == '.wav':
        # 如果已经是WAV格式，直接复制
        shutil.copy2(original_audio_path, converted_audio_path)
        task_log += "\n音频已经是WAV格式，无需转换"
    else:
        # 需要转换为WAV格式
        if not convert_audio_to_wav(original_audio_path, converted_audio_path):
            shutil.rmtree(upload_dir)  # 清理临时文件
            return jsonify({'error': '音频格式转换失败'}), 400
        task_log += "\n音频已转换为WAV格式"
    
    # 调用外部生成项目
    try:
        # 获取当前项目的根目录
        current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        
        # 从配置文件读取TANGO路径
        config_file = os.path.join('config', 'system_setting.json')
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        # 设置输出文件路径（使用绝对路径）
        output_video = os.path.abspath(os.path.join(current_dir, upload_dir, f'{task_id}_output.mp4'))
        
        # 转换音频和视频路径为绝对路径
        converted_audio_path_abs = os.path.abspath(converted_audio_path)
        converted_video_path_abs = os.path.abspath(converted_video_path)
            
        if platform.system() == 'Windows':
            tango_path = config.get('windows_tango_path', '')
            cmd = f'cmd /c "cd /d {tango_path} && conda activate tango && python tsxxdw/inference.py --audio_path {converted_audio_path_abs} --video_path {converted_video_path_abs} --save_path {output_video}"'
        else:
            tango_path = config.get('linux_tango_path', '')
            cmd = f'cd {tango_path} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate tango && python tsxxdw/inference.py --audio_path {converted_audio_path_abs} --video_path {converted_video_path_abs} --save_path {output_video}'
            
        if not tango_path:
            raise Exception("TANGO路径未配置")
            
        # 打印命令
        print("执行的命令：")
        print(cmd)
        print("文件路径：")
        print(f"音频文件: {converted_audio_path_abs}")
        print(f"视频文件: {converted_video_path_abs}")
        print(f"输出文件: {output_video}")
        
        task_log += f"\n执行的命令：\n{cmd}"
        task_log += f"\n音频文件: {converted_audio_path_abs}"
        task_log += f"\n视频文件: {converted_video_path_abs}"
        task_log += f"\n输出文件: {output_video}"
            
        # 创建新任务
        task = ActionTask(task_id, converted_video_path, converted_audio_path)
        task.log.append(f"原始视频文件: {video.filename}")
        task.log.append(f"原始音频文件: {audio.filename}")
        task.log.append(task_log)
        task.output_file = output_video
        action_tasks[task_id] = task

        # 使用 Popen 启动进程，并捕获输出
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True
        )
        task.process = process

        # 创建线程处理输出
        stdout_thread = threading.Thread(
            target=process_output,
            args=(task, process.stdout, False)
        )
        stderr_thread = threading.Thread(
            target=process_output,
            args=(task, process.stderr, True)
        )

        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # 将任务添加到队列
        with task_lock:
            task_queue.append(task)
            queue_position = len(task_queue)
            if queue_position > 1:
                task.add_log(f"任务已加入队列，当前位置：{queue_position}")
            else:
                task.add_log("任务已加入队列，即将开始处理...")
        
        # 启动任务处理
        start_task_processing()
        
    except Exception as e:
        task.log.append(f"启动任务失败: {str(e)}")
        task.status = "失败"
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'task_id': task_id})

@bp.route('/action/tasks')
def get_tasks():
    task_list = []
    for task in action_tasks.values():
        position = -1
        with task_lock:
            try:
                position = list(task_queue).index(task) + 1
            except ValueError:
                pass
            
        task_info = {
            'task_id': task.task_id,
            'status': task.status,
            'video_name': task.video_name,
            'audio_name': task.audio_name,
            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'output_file': task.output_file,
            'queue_position': position if position > 0 else None
        }
        task_list.append(task_info)
    return jsonify(task_list)

@bp.route('/action/task_status/<task_id>')
def task_status(task_id):
    task = action_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 检查进程状态
    if task.process:
        return_code = task.process.poll()
        if return_code is not None:
            if return_code == 0:
                task.status = "完成"
            else:
                task.status = "失败"
    
    # 加载历史日志
    logs = task.load_logs()
    
    # 获取新的日志消息
    new_logs = []
    try:
        while True:
            new_logs.append(task.log_queue.get_nowait())
    except queue.Empty:
        pass
    
    # 如果是页面刷新（通过查询参数判断）
    is_refresh = request.args.get('refresh', 'false') == 'true'
    if is_refresh:
        # 返回完整的历史日志
        return jsonify({
            'status': task.status,
            'log': logs,
            'new_logs': [],  # 页面刷新时不需要新日志
            'output_file': task.output_file
        })
    else:
        # 正常轮询时只返回新日志
        return jsonify({
            'status': task.status,
            'log': [],  # 正常轮询时不需要历史日志
            'new_logs': new_logs,
            'output_file': task.output_file
        }) 