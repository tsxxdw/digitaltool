$(document).ready(function() {
    // 页面加载时获取现有设置
    $.get('/system_setting/get', function(data) {
        $('#tango_path').val(data.tango_path || '');
        $('#musetalk_path').val(data.musetalk_path || '');
    });

    // 处理表单提交
    $('#settingsForm').submit(function(e) {
        e.preventDefault();
        
        const formData = {
            tango_path: $('#tango_path').val(),
            musetalk_path: $('#musetalk_path').val()
        };
        
        // 禁用提交按钮
        const submitButton = $(this).find('button[type="submit"]');
        submitButton.prop('disabled', true);
        submitButton.text('保存中...');
        
        $.ajax({
            url: '/system_setting/save',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                // 显示成功消息
                const successMessage = $('<div class="success-message">设置已保存</div>');
                $('body').append(successMessage);
                successMessage.fadeIn();
                
                // 3秒后隐藏消息
                setTimeout(function() {
                    successMessage.fadeOut(function() {
                        successMessage.remove();
                    });
                }, 3000);
            },
            error: function(xhr) {
                alert('保存失败: ' + xhr.responseJSON.error);
            },
            complete: function() {
                // 恢复提交按钮
                submitButton.prop('disabled', false);
                submitButton.text('保存设置');
            }
        });
    });
}); 