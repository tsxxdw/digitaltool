let globalTasks = {};
const POLLING_INTERVAL = 5000;  // 5秒
let pollingTimer = null;

// 获取状态对应的CSS类
function getStatusClass(status) {
    switch(status) {
        case '等待中':
            return 'status-waiting';
        case '生成中':
            return 'status-generating';
        case '已完成':
            return 'status-complete';
        case '生成失败':
            return 'status-failed';
        default:
            return '';
    }
}

// 更新任务列表
function updateTasks() {
    $.get('/sync/tasks', function(tasks) {
        globalTasks = tasks;
        renderTasks();
        startPolling();
    });
}

// 渲染任务列表
function renderTasks() {
    const taskContainer = $('#taskContainer');
    taskContainer.empty();
    
    const taskArray = Object.values(globalTasks).sort((a, b) => 
        new Date(b.create_time) - new Date(a.create_time)
    );
    
    taskArray.forEach(task => {
        const taskHtml = `
            <div class="task-item">
                <div class="task-header">
                    <span class="task-id">#${task.id}</span>
                    <span class="task-time">${task.create_time}</span>
                    <span class="task-status ${getStatusClass(task.status)}">${task.status}</span>
                </div>
                <div class="task-info">
                    <div>训练对象：${task.person_name}</div>
                    <div>音频文件：${task.audio_name}</div>
                    ${task.progress ? `<div class="progress-bar"><div class="progress" style="width: ${task.progress}%"></div></div>` : ''}
                </div>
                ${task.output_file ? `
                    <div class="task-actions">
                        <a href="/${task.output_file}" class="download-btn" target="_blank">下载视频</a>
                        <button onclick="showDownloadModal('${task.output_file}')" class="copy-link-btn">复制链接</button>
                    </div>
                ` : ''}
                <div class="log-container">
                    ${task.log.join('<br>')}
                </div>
            </div>
        `;
        taskContainer.append(taskHtml);
    });
}

// 表单提交处理
$(document).ready(function() {
    $('#syncForm').on('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        
        $.ajax({
            url: '/sync/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.error) {
                    alert(response.error);
                } else {
                    updateTasks();
                    $('#syncForm')[0].reset();
                }
            },
            error: function() {
                alert('上传失败，请重试');
            }
        });
    });
    
    // 初始加载任务列表
    updateTasks();
});

// 开始轮询
function startPolling() {
    // 清除现有的轮询
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
    
    // 设置新的轮询
    pollingTimer = setInterval(() => {
        $.get('/sync/tasks', function(tasks) {
            globalTasks = tasks;
            renderTasks();
        });
    }, POLLING_INTERVAL);
}

// 停止轮询
function stopPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
}

// 显示下载链接模态框
function showDownloadModal(filePath) {
    const normalizedPath = filePath.replace(/\\/g, '/');
    const fullUrl = `${window.location.origin}/${normalizedPath}`;
    
    navigator.clipboard.writeText(fullUrl).then(function() {
        alert('下载链接已复制到剪贴板');
    }).catch(function(err) {
        console.error('复制失败:', err);
        // 降级处理：创建临时输入框
        const tempInput = document.createElement('input');
        tempInput.value = fullUrl;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        alert('下载链接已复制到剪贴板');
    });
} 