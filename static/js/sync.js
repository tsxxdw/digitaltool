let globalTasks = {};
const POLLING_INTERVAL = 2000;  // 2秒

function renderTasks() {
    const container = $('#taskContainer');
    container.empty();
    
    const taskArray = Object.entries(globalTasks).map(([id, task]) => ({
        id,
        ...task
    })).sort((a, b) => new Date(b.create_time) - new Date(a.create_time));
    
    taskArray.forEach((task, index) => {
        const taskNumber = taskArray.length - index;
        
        let taskHtml = `
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-header">
                    <div class="task-info">
                        <div class="info-row">
                            <div class="info-cell"><strong>序号:</strong> ${taskNumber}</div>
                            <div class="info-cell"><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                            <div class="info-cell"><strong>创建时间:</strong> ${task.create_time}</div>
                        </div>
                        <div class="info-row">
                            <div class="info-cell"><strong>训练对象:</strong> ${task.person_name}</div>
                            <div class="info-cell"><strong>音频文件:</strong> ${task.audio_name}</div>
                        </div>
                        ${task.progress ? `
                        <div class="progress-bar">
                            <div class="progress" style="width: ${task.progress}%"></div>
                            <span class="progress-text">${task.progress}%</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
                <div class="log-container" id="log-${task.id}"></div>
                ${task.output_file ? `
                    <div class="download-actions">
                        <a href="${task.output_file}" class="download-btn" download>下载视频</a>
                        <button onclick="copyDownloadLink('${task.output_file}')" class="copy-link-btn">复制下载链接</button>
                    </div>
                ` : ''}
            </div>
        `;
        container.append(taskHtml);
    });
}

function copyDownloadLink(filePath) {
    const fullUrl = `${window.location.origin}/${filePath}`;
    navigator.clipboard.writeText(fullUrl).then(() => {
        alert('下载链接已复制到剪贴板');
    });
}

// 更新任务列表
function updateTasks() {
    $.get('/sync/tasks', function(tasks) {
        globalTasks = tasks;
        renderTasks();
        startPolling();
    });
}

// 启动轮询
function startPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
    
    pollingTimer = setInterval(() => {
        Object.entries(globalTasks).forEach(([taskId, task]) => {
            if (task.status !== "已完成" && task.status !== "生成失败") {
                pollTaskStatus(taskId);
            }
        });
    }, POLLING_INTERVAL);
}

// 轮询任务状态
function pollTaskStatus(taskId) {
    $.get(`/sync/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        // 更新任务状态
        globalTasks[taskId].status = response.status;
        globalTasks[taskId].progress = response.progress;
        globalTasks[taskId].output_file = response.output_file;
        globalTasks[taskId].log = response.log;
        
        // 重新渲染任务列表
        renderTasks();
    });
}

// 显示下载链接模态框
function showDownloadModal(link) {
    const modal = document.getElementById('linkModal');
    const downloadLink = document.getElementById('downloadLink');
    downloadLink.textContent = `${window.location.origin}/${link}`;
    modal.style.display = 'block';
}

// 关闭模态框
document.querySelector('.close').onclick = function() {
    document.getElementById('linkModal').style.display = 'none';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('linkModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

// 复制下载链接
function copyDownloadLink() {
    const linkText = $('#downloadLink').text();
    navigator.clipboard.writeText(linkText).then(function() {
        alert('链接已复制到剪贴板！');
    }).catch(function(err) {
        console.error('复制失败:', err);
        // 回退方案：选择文本
        const linkElement = document.getElementById('downloadLink');
        const range = document.createRange();
        range.selectNode(linkElement);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand('copy');
        window.getSelection().removeAllRanges();
        alert('链接已复制到剪贴板！');
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    // 处理表单提交
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

    // 关闭模态框
    $('.close').click(function() {
        $('#linkModal').hide();
    });
    
    // 点击模态框外部关闭
    $(window).click(function(e) {
        if (e.target == document.getElementById('linkModal')) {
            $('#linkModal').hide();
        }
    });

    // 初始加载任务列表
    updateTasks();
    
    // 定期更新任务列表
    setInterval(updateTasks, 5000);
});

// 在页面卸载时清除定时器
$(window).on('unload', function() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
}); 