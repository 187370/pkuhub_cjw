/**
 * PKUHUB Markdown 和 LaTeX 渲染工具
 * 提供评论内容的格式化和公式渲染功能
 */

// 初始化Markdown和LaTeX渲染器
function initMarkdownLatexRenderer() {
    // 配置marked选项以避免干扰LaTeX公式
    marked.setOptions({
        gfm: true,
        breaks: true,
        smartLists: true,
        smartypants: false, // 关闭这个以避免干扰LaTeX中的引号
    });
}

// 用于防抖的定时器
let mathJaxRenderTimer;

// 渲染Markdown内容，保护LaTeX公式不被处理
function renderMarkdown(text) {
    if (!text) return '';

    // 保护LaTeX公式不被Markdown渲染器更改
    // 1. 首先保存所有公式
    const displayMathPairs = [];
    const inlineMathPairs = [];

    // 保存所有块级公式 - 支持$$...$$格式
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, function (match, formula) {
        const id = displayMathPairs.length;
        displayMathPairs.push({ id: id, formula: formula });
        return `DISPLAY_MATH_${id}`;
    });

    // 保存所有块级公式 - 支持\[...\]格式 - 修复反斜杠问题
    text = text.replace(/(\\)\[([\s\S]*?)(\\)\]/g, function (match, leftSlash, formula, rightSlash) {
        const id = displayMathPairs.length;
        displayMathPairs.push({ id: id, formula: formula });
        return `DISPLAY_MATH_${id}`;
    });

    // 保存所有行内公式 - 支持$...$格式
    text = text.replace(/\$(.+?)\$/g, function (match, formula) {
        const id = inlineMathPairs.length;
        inlineMathPairs.push({ id: id, formula: formula });
        return `INLINE_MATH_${id}`;
    });

    // 2. 渲染Markdown
    let renderedText = marked.parse(text);

    // 3. 恢复所有公式
    // 恢复块级公式 - 转换为$$...$$格式以便MathJax识别
    displayMathPairs.forEach(function (pair) {
        renderedText = renderedText.replace(`DISPLAY_MATH_${pair.id}`, `$$${pair.formula}$$`);
    });

    // 恢复行内公式
    inlineMathPairs.forEach(function (pair) {
        renderedText = renderedText.replace(`INLINE_MATH_${pair.id}`, `$${pair.formula}$`);
    });

    return renderedText;
}

// 使用防抖技术优化MathJax渲染
function renderMathWithDebounce(element) {
    // 清除之前的定时器
    if (mathJaxRenderTimer) {
        clearTimeout(mathJaxRenderTimer);
    }

    // 设置新的定时器，延迟300毫秒后渲染
    mathJaxRenderTimer = setTimeout(() => {
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([element])
                .catch((err) => console.error('MathJax渲染错误:', err));
        }
    }, 300);
}

// 优化后的函数：渲染元素中的LaTeX公式
function renderMathInElementCustom(element) {
    if (!element) return;
    renderMathWithDebounce(element);
}

// 渲染页面上所有markdown内容中的数学公式
function renderAllMarkdownContent() {
    document.querySelectorAll('.raw-content').forEach(element => {
        const rawContent = element.textContent;
        element.innerHTML = renderMarkdown(rawContent);
        element.classList.remove('raw-content');
    });

    // 使用MathJax渲染页面上所有公式
    if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise().catch(function (err) {
            console.error('初始MathJax渲染错误:', err);
        });
    }
}

// HTML 转义，防止 XSS
function escapeHTML(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function () {
    initMarkdownLatexRenderer();
    setTimeout(renderAllMarkdownContent, 100);
});
