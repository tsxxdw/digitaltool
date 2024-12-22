// 更新任务列表
function updateTasks() {
    $.get('/sync/tasks', function(tasks) {
        $('#taskContainer').empty();
        tasks.forEach(function(task) {
            let taskHtml = `
                <div class="task-item">
                    <div><strong>任务ID:</strong> ${task.task_id}</div>
                    <div><strong>状态:</strong> ${task.status}</div>
                    <div><strong>创建时间:</strong> ${task.create_time}</div>
                    <div class="log-container" id="log-${task.task_id}"></div>
                    ${task.output_file ? `
                        <div class="download-actions">
                            <a href="${task.output_file}" class="download-btn" download>下载视频</a>
                            <span class="copy-link-btn" onclick="showDownloadLink('${task.output_file}')">复制下载链接</span>
                        </div>
                    ` : ''}
                </div>
            `;
            $('#taskContainer').append(taskHtml);
            
            // 获取任务状态和日志
            pollTaskStatus(task.task_id);
        });
    });
}

// 轮询任务状态
function pollTaskStatus(taskId) {
    $.get(`/sync/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        $(`#log-${taskId}`).html(response.log.join('<br>'));
        
        if (response.status === "处理中") {
            setTimeout(() => pollTaskStatus(taskId), 2000);
        }
    });
}

// 显示下载链接模态框
function showDownloadLink(link) {
    const fullLink = window.location.origin + link;
    $('#downloadLink').text(fullLink);
    $('#linkModal').show();
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
    $('#syncForm').submit(function(e) {
        e.preventDefault();
        
        let formData = new FormData(this);
        
        // 禁用提交按钮
        let submitButton = $(this).find('button[type="submit"]');
        submitButton.prop('disabled', true);
        submitButton.text('提交中...');
        
        $.ajax({
            url: '/sync/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                alert('生成任务已提交，任务ID: ' + response.task_id);
                updateTasks();
            },
            error: function(xhr) {
                alert('提交失败: ' + xhr.responseJSON.error);
            },
            complete: function() {
                // 恢复提交按钮
                submitButton.prop('disabled', false);
                submitButton.text('开始生成');
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

    // 页面加载时更新任务列表
    updateTasks();
    
    // 定期更新任务列表
    setInterval(updateTasks, 5000);
}); 