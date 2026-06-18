// ========================================
// Ulearning 配置一键生成脚本
// 请在练习页面的浏览器控制台中运行此代码
// ========================================

(function() {
    console.log('=== Ulearning 配置生成器 ===\n');

    // 从当前请求中提取配置信息
    const config = {
        authorization: '',
        examId: '',
        examUserId: '',
        traceId: '',
        paper_range: {
            start_id: 0,
            end_id: 0
        },
        rate_limiting: {
            delay_seconds: 1.0
        },
        openai: {
            base_url: 'http://127.0.0.1:8081/v1',
            api_key: 'sk-your-key-here',
            model: 'gemini-flash-lite',
            rpm: 30,
            concurrency: 6
        },
        paths: {
            papers_dir: 'papers_json',
            question_bank_json: 'question_bank.json',
            question_bank_md: 'question_bank.md',
            batch_results_jsonl: 'batch_results.jsonl',
            batch_results_md: 'batch_results.md',
            title_tags_jsonl: 'title_tags.jsonl',
            subjective_json: 'subjective.json',
            final_html: 'final_answers.html'
        }
    };


    // 拦截fetch请求获取Authorization
    const originalFetch = window.fetch;
    let captured = false;

    window.fetch = function(...args) {
        const request = args[0];
        const options = args[1] || {};

        if (typeof request === 'string' && request.includes('getPaperForStudent')) {
            const url = new URL(request);
            config.examId = url.searchParams.get('examId') || '';
            config.examUserId = url.searchParams.get('examUserId') || '';
            config.traceId = url.searchParams.get('traceId') || '';

            const paperId = parseInt(url.searchParams.get('paperId') || '0');
            if (paperId > 0) {
                if (config.paper_range.start_id === 0 || paperId < config.paper_range.start_id) {
                    config.paper_range.start_id = paperId;
                }
                if (paperId > config.paper_range.end_id) {
                    config.paper_range.end_id = paperId;
                }
            }

            if (options.headers) {
                config.authorization = options.headers.Authorization || options.headers.authorization || '';
            }

            captured = true;
        }

        return originalFetch.apply(this, args);
    };

    // 拦截XMLHttpRequest获取Authorization
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._url = url;
        return originalOpen.apply(this, [method, url, ...rest]);
    };

    XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
        if (this._url && this._url.includes('getPaperForStudent')) {
            if (header.toLowerCase() === 'authorization') {
                config.authorization = value;

                const url = new URL(this._url, window.location.origin);
                config.examId = url.searchParams.get('examId') || '';
                config.examUserId = url.searchParams.get('examUserId') || '';
                config.traceId = url.searchParams.get('traceId') || '';

                const paperId = parseInt(url.searchParams.get('paperId') || '0');
                if (paperId > 0) {
                    if (config.paper_range.start_id === 0 || paperId < config.paper_range.start_id) {
                        config.paper_range.start_id = paperId;
                    }
                    if (paperId > config.paper_range.end_id) {
                        config.paper_range.end_id = paperId;
                    }
                }

                captured = true;
            }
        }
        return originalSetRequestHeader.apply(this, arguments);
    };

    console.log('✓ 拦截器已就绪');
    console.log('请进行以下操作：');
    console.log('1. 点击"开始做题"或切换到下一题');
    console.log('2. 等待题目加载完成');
    console.log('3. 在控制台输入: showConfig()');
    console.log('');

    // 全局函数：显示配置
    window.showConfig = function() {
        if (!captured || !config.authorization) {
            console.warn('⚠️ 未捕获到配置信息，请先做题触发请求！');
            console.log('提示：点击"开始做题"或"下一题"按钮');
            return;
        }

        // 自动推测试卷范围（通常是连续100套）
        if (config.paper_range.start_id > 0 && config.paper_range.end_id === config.paper_range.start_id) {
            config.paper_range.end_id = config.paper_range.start_id + 99;
            console.log(`ℹ️ 自动设置试卷范围: ${config.paper_range.start_id} - ${config.paper_range.end_id}`);
        }

        console.log('\n=== 配置信息已生成 ===\n');
        console.log(JSON.stringify(config, null, 2));
        console.log('\n=== 使用说明 ===');
        console.log('1. 复制上面的JSON配置');
        console.log('2. 保存为 config.json 文件');
        console.log('3. 放在项目根目录');
        console.log('4. 运行: python src/downloader.py');
        console.log('');
        console.log('💡 提示：如果试卷范围不对，请手动修改 paper_range.end_id');

        // 复制到剪贴板
        const configStr = JSON.stringify(config, null, 2);
        navigator.clipboard.writeText(configStr).then(() => {
            console.log('✓ 配置已自动复制到剪贴板！');
        }).catch(() => {
            console.log('⚠️ 自动复制失败，请手动复制上面的JSON');
        });
    };

    console.log('✓ 脚本加载完成！输入 showConfig() 查看配置');
})();
