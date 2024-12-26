// 全局变量
const POLLING_INTERVAL = 5000;      // 5秒
let globalTasks = [];              // 存储所有任务
let pollingTimer = null;           // 轮询定时器

// 更新任务列表（只在页面加载和新任务上传时调用）
function updateTasks() {
    $.get('/action/tasks', function(tasks) {
        globalTasks = tasks;  // 更新全局任务列表
        renderTasks();        // 渲染任务列表
        startPolling();       // 启动轮询
    });
}

// 渲染任务列表
function renderTasks() {
    $('#taskContainer').empty();
    
    // 对任务进行排序（按创建时间倒序）
    const sortedTasks = [...globalTasks].sort((a, b) => {
        return new Date(b.create_time) - new Date(a.create_time);
    });
    
    // 计算序号（最早的任务从1开始）
    const totalTasks = sortedTasks.length;
    
    // 创建一个容器来包裹所有任务
    const tasksWrapper = $('<div class="tasks-wrapper"></div>');
    
    sortedTasks.forEach((task, index) => {
        const taskNumber = totalTasks - index;
        
        let taskHtml = `
            <div class="task-item">
                <div class="task-header">
                    <div class="task-info">
                        <div><strong>序号:</strong> ${taskNumber}</div>
                        <div><strong>任务ID:</strong> ${task.task_id}</div>
                        <div><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                        <div><strong>创建时间:</strong> ${task.create_time}</div>
                    </div>
                </div>
                <div class="file-info">
                    <div class="file-item">${task.video_name}</div>
                    <div class="file-item">${task.audio_name}</div>
                </div>
                <div class="log-container" id="log-${task.task_id}"></div>
                ${task.status === "完成" && task.output_file ? `
                    <div class="download-actions">
                        <a href="/static/${task.output_file}" class="download-btn" download>下载视频</a>
                        <span class="copy-link-btn" onclick="copyDownloadLink('${task.output_file}')">复制下载链接</span>
                    </div>
                ` : ''}
            </div>
        `;
        tasksWrapper.append(taskHtml);
        
        // 初始加载任务日志
        pollTaskStatus(task.task_id, true);
    });
    
    $('#taskContainer').append(tasksWrapper);
}

// 启动轮询
function startPolling() {
    // 清除现有的轮询定时器
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
    
    // 设置新的轮询定时器
    pollingTimer = setInterval(() => {
        // 只为进行中的任务更新状态
        globalTasks.forEach(task => {
            if (task.status !== "完成" && task.status !== "失败") {
                pollTaskStatus(task.task_id, false);
            }
        });
    }, POLLING_INTERVAL);
}

// 轮询任务状态
function pollTaskStatus(taskId, isRefresh = false) {
    const url = isRefresh 
        ? `/action/task_status/${taskId}?refresh=true`
        : `/action/task_status/${taskId}`;

    $.get(url, function(response) {
        if (response.error) return;
        
        const logContainer = $(`#log-${taskId}`);
        
        // 如果是页面刷新，清空并显示完整的历史日志
        if (isRefresh) {
            logContainer.empty();
            response.log.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        }
        // 否则只添加新的日志
        else if (response.new_logs && response.new_logs.length > 0) {
            response.new_logs.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        }
        
        // 滚动到底部
        logContainer.scrollTop(logContainer[0].scrollHeight);
        
        // 更新任务状态和界面显示
        const taskItem = logContainer.closest('.task-item');
        const statusBadge = taskItem.find('.status-badge');
        
        // 如果状态发生变化
        if (statusBadge.text() !== response.status) {
            // 更新状态标签
            statusBadge.text(response.status);
            statusBadge.attr('class', `status-badge ${getStatusClass(response.status)}`);
            
            // 更新全局任务列表中的状态
            const taskIndex = globalTasks.findIndex(t => t.task_id === taskId);
            if (taskIndex !== -1) {
                globalTasks[taskIndex].status = response.status;
                
                // 如果任务完成且有输出文件，添加下载按钮
                if (response.status === "完成" && response.output_file) {
                    globalTasks[taskIndex].output_file = response.output_file;
                    
                    // 添加下载按钮
                    const downloadHtml = `
                        <div class="download-actions">
                            <a href="/static/${response.output_file}" class="download-btn" download>下载视频</a>
                            <span class="copy-link-btn" onclick="copyDownloadLink('${response.output_file}')">复制下载链接</span>
                        </div>
                    `;
                    taskItem.append(downloadHtml);
                }
            }
        }
        
        // 只有任务正在进行中时才继续轮询
        if (response.status !== "完成" && response.status !== "失败") {
            setTimeout(() => pollTaskStatus(taskId, false), POLLING_INTERVAL);
        }
    }).fail(function(xhr) {
        console.error('获取任务状态失败:', xhr);
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    // 初始加载任务列表
    updateTasks();

    // 监听表单提交
    $('#uploadForm').on('submit', function(e) {
        e.preventDefault();
        
        const videoFile = $('#video')[0].files[0];
        const audioFile = $('#audio')[0].files[0];
        
        if (!videoFile || !audioFile) {
            alert('请选择视频和音频文件');
            return false;
        }

        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('audio', audioFile);

        $('#submitBtn').prop('disabled', true);

        $.ajax({
            url: '/action/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.task_id) {
                    $('#uploadForm')[0].reset();
                    updateTasks();  // 更新任务列表
                } else {
                    alert('上传失败：' + (response.error || '未知错误'));
                }
            },
            error: function(xhr) {
                alert('上传失败：' + (xhr.responseJSON?.error || '服务器错误'));
            },
            complete: function() {
                $('#submitBtn').prop('disabled', false);
            }
        });

        return false;
    });
});

// 在页面卸载时清除定时器
$(window).on('unload', function() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
});

function getStatusClass(status) {
    switch(status) {
        case '等待中':
            return 'status-waiting';
        case '处理中':
            return 'status-processing';
        case '完成':
            return 'status-complete';
        case '失败':
            return 'status-failed';
        default:
            return '';
    }
}

// 修改复制链接功能
function copyDownloadLink(filePath) {
    // 确保filePath是从file/action开始的路径
    const normalizedPath = filePath.startsWith('file/action') 
        ? filePath 
        : filePath.substring(filePath.indexOf('file/action'));
        
    // 直接使用规范化后的路径
    const fullUrl = `${window.location.origin}/${normalizedPath}`;
    
    navigator.clipboard.writeText(fullUrl).then(function() {
        alert('下载链接已复制到剪贴板');
    }).catch(function(err) {
        console.error('复制失败:', err);
        const tempInput = document.createElement('input');
        tempInput.value = fullUrl;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        alert('下载链接已复制到剪贴板');
    });
} 