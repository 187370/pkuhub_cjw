/**
 * PKUHUB CSRF保护辅助脚本
 */

// 页面加载时从meta标签获取CSRF令牌
document.addEventListener('DOMContentLoaded', function () {
    console.log('CSRF辅助脚本初始化');
    window.globalCsrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    console.log('全局CSRF令牌设置:', window.globalCsrfToken ? '成功' : '失败');

    // 为所有fetch请求添加CSRF令牌
    const originalFetch = window.fetch;
    window.fetch = function (url, options = {}) {
        options = options || {};
        options.headers = options.headers || {};

        // 对POST/PUT/DELETE请求添加CSRF令牌
        if (!/^(GET|HEAD)$/i.test(options.method || 'GET') && window.globalCsrfToken) {
            options.headers['X-CSRFToken'] = window.globalCsrfToken;
        }

        return originalFetch(url, options);
    };
});
