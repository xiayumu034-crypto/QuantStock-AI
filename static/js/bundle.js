
// ========== QuantStock-AI CORE BUNDLE v1.0.3 ==========
let selectedStock = '300201';
let autoRefresh = true;
let refreshInterval = 3;
let charts = {};
let lastReq = { realtime: 0, minute: 0, technical: 0, predict: 0 };
const INTERVALS = { realtime: 3000, minute: 60000, technical: 60000, predict: 300000 };
const stocks = [
    { code: '300201', name: '海伦哲' }, { code: '000001', name: '平安银行' },
    { code: '600519', name: '贵州茅台' }, { code: '300750', name: '宁德时代' },
    { code: '002594', name: '比亚迪' }
];
let currentAccountId = 'default';
let simAutoTrade = false;
let allMLData = [];
let filteredMLData = [];
let currentMLPage = 1;
const mlPageSize = 15;
let currentMLVersion = 'v20';
let allNewsData = [];
let newsMode = 'important';
let customStocks = JSON.parse(localStorage.getItem('customStocks') || '[]');
let watchlistCollapsed = false;
let allTradeLogs = [];
let backtestChart = null;
let trainPollInterval = null;


function addCustomStock(code, name, market) {
        if (customStocks.find(s => s.code === code)) { showToast('已在自选中'); return; }
        customStocks.push({ code, name, market: market || (code.startsWith('6') ? 'sh' : 'sz') });
        localStorage.setItem('customStocks', JSON.stringify(customStocks));
        updateCustomStocksUI();
        document.getElementById('searchResults').style.display = 'none';
        document.getElementById('searchInput').value = '';
    }

function analyzeFundamentals(code, name) {
        const modal = new bootstrap.Modal(document.getElementById('aiAnalyzeModal'));
        const content = document.getElementById('aiAnalyzeContent');
        content.innerHTML = `<div class="text-center py-5"><div class="spinner-border text-primary"></div><div class="mt-2 small text-white-50">正在深度研判 [${name}] ...</div></div>`;
        modal.show();

        fetch(`/api/ai_analyze/${code}`)
            .then(r => r.json())
            .then(d => {
                if (d.status === 'success') {
                    const data = d.data;
                    content.innerHTML = `
                        <div class="mb-3">
                            <div class="small text-white-50 mb-1">基本面画像:</div>
                            <div class="p-2 rounded bg-white-5 d-flex justify-content-between align-items-center">
                                <span>营收增长: <span class="text-danger">${data.fundamental.revenue_growth}</span></span>
                                <span>净利增长: <span class="text-danger">${data.fundamental.net_profit_growth}</span></span>
                            </div>
                        </div>
                        <div class="mb-3">
                            <div class="small text-white-50 mb-1">周一走势预测:</div>
                            <div class="p-2 rounded border border-secondary">
                                <div class="h5 text-warning mb-2">建议: ${data.monday_prediction.action}</div>
                                <div class="small text-white-80">· 支撑: ${data.monday_prediction.support_level}</div>
                                <div class="small text-white-80">· 压力: ${data.monday_prediction.resistance_level}</div>
                            </div>
                        </div>
                        <div class="mb-1">
                            <div class="small text-white-50 mb-1">AI 综合结论:</div>
                            <div class="p-3 rounded" style="background: rgba(13, 110, 253, 0.1); border-left: 4px solid #0d6efd;">
                                ${data.ai_conclusion}
                            </div>
                        </div>
                    `;
                } else {
                    content.innerHTML = `<div class="alert alert-danger">研判失败: ${d.message}</div>`;
                }
            })
            .catch(e => {
                content.innerHTML = `<div class="alert alert-danger">分析引擎响应超时</div>`;
            });
    }

function analyzeNews(newsText) {
        document.getElementById('rankAnalysisTitle').innerText = '🧠 MiMo 事件驱动多跳推演';
        document.getElementById('rankAnalysisContent').innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-purple" role="status" style="color: #6f42c1;"></div>
                <div class="mt-3 text-muted" style="font-size: 0.9rem;">MiMo 正在构建事件知识图谱<br/>( 新闻 ➡️ 宏观 ➡️ 板块 ➡️ 龙头 )<br/>请稍候...</div>
            </div>
        `;
        const modal = new bootstrap.Modal(document.getElementById('rankAnalysisModal'));
        modal.show();

        fetch('/api/news/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: newsText})
        })
        .then(r => r.json())
        .then(res => {
            if (res.status === 'success') {
                document.getElementById('rankAnalysisContent').innerHTML = res.data;
                
                // 渲染 ECharts 树状图
                if (res.graph_data) {
                    const container = document.getElementById('echartsTreeContainer');
                    if (container) {
                        const myChart = echarts.init(container);
                        const option = {
                            tooltip: { 
                                trigger: 'item', 
                                triggerOn: 'mousemove',
                                confine: true,
                                enterable: true,
                                extraCssText: 'max-width: 300px; white-space: normal; word-break: break-all;'
                            },
                            series: [
                                {
                                    type: 'tree',
                                    roam: true,
                                    data: [res.graph_data],
                                    top: '5%',
                                    left: '25%',
                                    bottom: '5%',
                                    right: '25%',
                                    symbolSize: 12,
                                    label: {
                                        position: 'left',
                                        verticalAlign: 'middle',
                                        align: 'right',
                                        fontSize: 14,
                                        color: '#e5e7eb',
                                        backgroundColor: '#1a1a2e',
                                        padding: [4, 8],
                                        borderRadius: 4,
                                        borderWidth: 1,
                                        borderColor: '#6f42c1'
                                    },
                                    leaves: {
                                        label: {
                                            position: 'right',
                                            verticalAlign: 'middle',
                                            align: 'left',
                                            color: '#10b981',
                                            borderColor: '#10b981'
                                        }
                                    },
                                    emphasis: { focus: 'descendant' },
                                    expandAndCollapse: true,
                                    animationDuration: 550,
                                    animationDurationUpdate: 750,
                                    lineStyle: {
                                        color: '#4b5563',
                                        width: 2,
                                        curveness: 0.5
                                    }
                                }
                            ]
                        };
                        myChart.setOption(option);
                    }
                }
            } else {
                document.getElementById('rankAnalysisContent').innerHTML = `<div class="alert alert-danger">${res.message}</div>`;
            }
        })
        .catch(err => {
            document.getElementById('rankAnalysisContent').innerHTML = `<div class="alert alert-danger">网络或接口异常</div>`;
        });
    }

function analyzeNewsByIndex(index) {
        let newsModeFiltered = newsMode === 'important' 
            ? allNewsData.filter(n => n.is_important || n.is_important === undefined)
            : allNewsData;
        const limit = newsMode === 'important' ? 15 : 30;
        newsModeFiltered = newsModeFiltered.slice(0, limit);
        
        if (index >= 0 && index < newsModeFiltered.length) {
            const newsItem = newsModeFiltered[index];
            const textToAnalyze = newsItem.content || newsItem.title || "无内容";
            analyzeNews(textToAnalyze);
        }
    }

function analyzeRankStock(code, name, isMonster, useAI) {
        const modal = new bootstrap.Modal(document.getElementById('rankAnalysisModal'));
        document.getElementById('rankAnalysisTitle').innerHTML = `${name} (${code}) - ${useAI ? '<i class="bi bi-robot text-danger"></i> AI深度分析' : '基本面简报'}`;
        document.getElementById('rankAnalysisContent').innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border ${useAI ? 'text-danger' : 'text-primary'}" role="status"></div>
                <div class="mt-2 text-muted">${useAI ? '正在调用 MiMo-Quant 深度推理基本面与逻辑...' : '正在获取最新基本面数据...'}</div>
            </div>`;
        modal.show();

        fetch(`/api/rank_analysis/${code}?name=${encodeURIComponent(name)}&is_monster=${isMonster}&use_ai=${useAI}`)
            .then(r => r.json())
            .then(d => {
                if (d.status === 'success') {
                    document.getElementById('rankAnalysisContent').innerHTML = `<div class="analysis-result">${d.data}</div>`;
                } else {
                    document.getElementById('rankAnalysisContent').innerHTML = `<div class="alert alert-danger">分析失败: ${d.message}</div>`;
                }
            })
            .catch(e => {
                document.getElementById('rankAnalysisContent').innerHTML = `<div class="alert alert-danger">网络请求失败</div>`;
            });
    }

function buildStockList() {
        const el = document.getElementById('stockList');
        el.innerHTML = stocks.map(s => 
            `<span class="stock-chip ${s.code === selectedStock ? 'active' : ''}" onclick="selectStock('${s.code}')">${s.name} ${s.code}</span>`
        ).join('');
    }

function buyStockFromNews(code, name) {
        // 设置到顶部的输入框
        document.getElementById('stockSearch').value = code;
        selectStock(code);
        showToast('已锁定标的，请在左上角控制面板选择策略或直接点击【执行买入】。');
    }

function changeAccount(id) {
        currentAccountId = id;
        loadSimAccount();
    }

function changeMLPage(delta) {
        const totalPages = Math.ceil(filteredMLData.length / mlPageSize);
        const newPage = currentMLPage + delta;
        if (newPage >= 1 && newPage <= totalPages) {
            currentMLPage = newPage;
            renderMLPage();
        }
    }

function fetchJSON(url, cb) { fetch(url).then(r => r.json()).then(cb).catch(e => console.error(url, e)); }

function fetchWatchlist() {
            const container = document.getElementById('watchlistContent');
            container.innerHTML = '<div class="text-center opacity-50 my-4"><i class="fas fa-spinner fa-spin"></i> 正在加载潜力标的...</div>';
            
            fetch('/api/sim/watchlist')
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success' && data.data.length > 0) {
                        let html = '';
                        data.data.forEach(item => {
                            let icon = '🔥';
                            let color = '#fca5a5';
                            if (item.type === 'ml') {
                                icon = '🤖';
                                color = '#a7f3d0';
                            } else if (item.type === 'washout') {
                                icon = '💧';
                                color = '#93c5fd';
                            }
                            const changePct = item.change_pct || 0;
                            const pctColor = changePct >= 0 ? '#ef4444' : '#10b981';
                            const pctStr = changePct > 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`;
                            
                            html += `
                                <div class="p-2 mb-2" style="background: rgba(255,255,255,0.05); border-left: 3px solid ${color}; border-radius: 4px;">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <strong style="color: ${color};">${icon} ${item.name} 
                                            <span style="font-size:0.75rem; color:#9ca3af; margin-right: 5px;">(${item.code})</span>
                                            <span style="font-size:0.8rem; color:${pctColor}; font-weight:bold; padding: 2px 4px; background: rgba(0,0,0,0.2); border-radius: 3px;">${pctStr}</span>
                                        </strong>
                                        <button class="btn btn-sm btn-outline-light py-0 px-2" style="font-size: 0.65rem;" onclick="analyzeFundamentals('${item.code}', '${item.name}')">诊断</button>
                                    </div>
                                    <div class="mt-1" style="font-size: 0.75rem; color: #d1d5db;">${item.reason}</div>
                                </div>
                            `;
                        });
                        container.innerHTML = html;
                    } else {
                        container.innerHTML = '<div class="text-center opacity-50 my-4">暂无高确定性标的</div>';
                    }
                })
                .catch(e => {
                    console.error(e);
                    container.innerHTML = '<div class="text-center text-danger my-4">加载失败</div>';
                });
        }

function filterTradeLogs() {
        const dateFilter = document.getElementById('tradeLogDate').value;
        const tbody = document.getElementById('tradeLogTableBody');
        
        if (!allTradeLogs || allTradeLogs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center opacity-50">暂无历史交易记录</td></tr>';
            return;
        }

        let filtered = allTradeLogs;
        if (dateFilter) {
            filtered = allTradeLogs.filter(log => log.time.startsWith(dateFilter));
        }

        if (filtered.length > 0) {
            let html = '';
            filtered.forEach(log => {
                const isBuy = log.action === 'buy';
                const color = isBuy ? '#ef4444' : '#10b981';
                const displayDir = isBuy ? '买入' : '卖出';

                const isFloating = isBuy && log.pnl !== undefined;
                const pnlColor = log.pnl >= 0 ? '#ef4444' : '#10b981';
                const pnl = (log.pnl !== undefined && log.pnl !== null) 
                    ? `<span style="color: ${pnlColor}">${log.pnl >= 0 ? '+' : ''}${log.pnl.toFixed(2)}</span>${isFloating ? '<br><small class="opacity-50" style="font-size:0.7rem">浮动</small>' : ''}` 
                    : '<span class="opacity-25">--</span>';
                
                const duration = log.duration 
                    ? `${log.duration}${isFloating ? '<br><small class="opacity-50" style="font-size:0.7rem">已持</small>' : ''}` 
                    : '<span class="opacity-25">--</span>';
                const amount = log.amount ? `¥${log.amount.toFixed(0)}` : '--';

                html += `<tr>
                    <td style="padding-left: 1.5rem;">${log.time}</td>
                    <td style="color:${color}; font-weight:bold">${displayDir}</td>
                    <td><span class="fw-bold">${log.name}</span><br><small class="text-secondary">${log.code}</small></td>
                    <td>¥${log.price.toFixed(2)}</td>
                    <td>${log.vol}</td>
                    <td>${amount}</td>
                    <td style="color:#fbbf24">¥${log.fee ? log.fee.toFixed(2) : '0.00'}</td>
                    <td style="font-weight: 500">${pnl}</td>
                    <td>${duration}</td>
                    <td class="text-white-50 small" style="max-width: 300px; white-space: normal; padding-right: 1.5rem;">${log.reason}</td>
                </tr>`;
            });
            tbody.innerHTML = html;
        } else {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center opacity-50">${dateFilter} 暂无历史交易记录</td></tr>`;
        }
    }

function formatVolume(vol) {
        if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿';
        if (vol >= 10000) return (vol / 10000).toFixed(0) + '万';
        return vol.toString();
    }

function handleMLFilterChange() {
        const filter = document.getElementById('mlSignalFilter').value;
        if (filter === 'all') {
            filteredMLData = allMLData;
        } else if (filter === 'strong') {
            filteredMLData = allMLData.filter(s => s.signal === '强烈看涨');
        } else if (filter === 'bull') {
            filteredMLData = allMLData.filter(s => s.signal.includes('看涨'));
        } else if (filter === 'neutral') {
            filteredMLData = allMLData.filter(s => s.signal === '中性');
        } else if (filter === 'bear') {
            filteredMLData = allMLData.filter(s => s.signal === '看跌');
        }
        currentMLPage = 1;
        renderMLPage();
    }

function handleSearchInput(input) {
        const query = input.value.trim();
        const suggestionsBox = document.getElementById('searchSuggestions');
        if (!query) { suggestionsBox.style.display = 'none'; return; }
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            fetch(`/api/search?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(d => {
                    if (d.status === 'success' && d.data.length > 0) {
                        let html = '';
                        d.data.forEach(item => {
                            html += `<div class="suggestion-item" onclick="selectSuggestion('${item.code}', '${item.name}')">
                                <span>${item.name}</span>
                                <span class="s-code">${item.code}</span>
                            </div>`;
                        });
                        suggestionsBox.innerHTML = html;
                        suggestionsBox.style.display = 'block';
                    } else { suggestionsBox.style.display = 'none'; }
                });
        }, 300);
    }

function handleSearchKey(event) { if (event.key === 'Enter') searchStock(); }

function initAllCharts() {
        charts.price = makeChart('priceChart', 'line', [
            { label: '价格', data: [], borderColor: '#00e5ff', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false, order: 1 },
            { label: 'VWAP', data: [], borderColor: '#ffea00', borderWidth: 1.5, borderDash: [4,2], pointRadius: 0, fill: false, order: 2 },
            { label: '布林上轨', data: [], borderColor: 'rgba(255, 82, 82, 0.7)', borderWidth: 1, pointRadius: 0, fill: false, order: 3 },
            { label: '布林中轨', data: [], borderColor: 'rgba(255, 255, 255, 0.3)', borderWidth: 1, borderDash: [4,2], pointRadius: 0, fill: false, order: 3 },
            { label: '布林下轨', data: [], borderColor: 'rgba(0, 230, 118, 0.7)', borderWidth: 1, pointRadius: 0, fill: '+1', backgroundColor: 'rgba(0, 230, 118, 0.05)', order: 3 }
        ], { plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: false }, x: { ticks: { maxTicksLimit: 10 } } } });

        charts.volume = makeChart('volumeChart', 'bar', [
            { label: '成交量(万)', data: [], backgroundColor: [], borderWidth: 0 }
        ], { plugins: { legend: { display: false } } });

        charts.macd = makeChart('macdChart', 'bar', [
            { label: 'MACD', data: [], backgroundColor: [], borderWidth: 0, order: 2 },
            { label: 'DIF', data: [], borderColor: '#00e5ff', borderWidth: 1.5, type: 'line', fill: false, order: 1 },
            { label: 'DEA', data: [], borderColor: '#ffea00', borderWidth: 1.5, type: 'line', fill: false, order: 1 }
        ]);

        charts.kdj = makeChart('kdjChart', 'line', [
            { label: 'K', data: [], borderColor: '#00e5ff', borderWidth: 1.5, pointRadius: 0, fill: false },
            { label: 'D', data: [], borderColor: '#ffea00', borderWidth: 1.5, pointRadius: 0, fill: false },
            { label: 'J', data: [], borderColor: '#ff4081', borderWidth: 1.5, pointRadius: 0, fill: false }
        ], { scales: { y: { beginAtZero: false } } });

        charts.rsi = makeChart('rsiChart', 'line', [
            { label: 'RSI14', data: [], borderColor: '#e040fb', borderWidth: 2, pointRadius: 0, fill: false }
        ], { scales: { y: { min: 0, max: 100 } }, plugins: { legend: { display: false } } });

        charts.cci = makeChart('cciChart', 'line', [
            { label: 'CCI', data: [], borderColor: '#00e676', borderWidth: 2, pointRadius: 0, fill: false }
        ], { scales: { y: { beginAtZero: false } }, plugins: { legend: { display: false } } });

        charts.dmi = makeChart('dmiChart', 'line', [
            { label: '+DI', data: [], borderColor: '#ff5252', borderWidth: 2, pointRadius: 0, fill: false },
            { label: '-DI', data: [], borderColor: '#00e676', borderWidth: 2, pointRadius: 0, fill: false },
            { label: 'ADX', data: [], borderColor: '#aaa', borderWidth: 1.5, borderDash: [4,2], pointRadius: 0, fill: false }
        ]);
    }

function loadAccountList() {
        fetch('/api/sim/accounts').then(r => r.json()).then(d => {
            if (d.status === 'success') {
                const sel = document.getElementById('accountSelector');
                sel.innerHTML = '';
                d.accounts.forEach(acc => {
                    const opt = document.createElement('option');
                    opt.value = acc;
                    opt.innerText = acc === 'default' ? '默认 V19' : acc.replace('douyin_', '游资-');
                    sel.appendChild(opt);
                });
                sel.value = currentAccountId;
            }
        });
    }

function loadBacktestData() {
        fetch('/api/backtest_report')
        .then(r => r.json())
        .then(res => {
            if(res.status !== 'success') {
                document.getElementById('backtestStats').innerHTML = `<div class="text-danger">${res.message}</div>`;
                return;
            }
            
            const d = res.data;
            // 渲染汇总卡片
            let statsHtml = '';
            d.summary.forEach(s => {
                const color = s.name.includes('V20') ? 'text-danger' : (s.name.includes('V19') ? 'text-info' : 'text-white-50');
                statsHtml += `
                <div class="mb-3 border-bottom border-secondary pb-2">
                    <div class="${color} fw-bold">${s.name}</div>
                    <div class="d-flex justify-content-between mt-1">
                        <span>累计收益:</span> <span class="text-white">${s.cum_ret}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span>夏普比率:</span> <span class="text-white">${s.sharpe}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span>最大回撤:</span> <span class="text-white">${s.mdd}</span>
                    </div>
                </div>`;
            });
            document.getElementById('backtestStats').innerHTML = statsHtml;
            
            // 渲染图表
            const ctx = document.getElementById('backtestChart').getContext('2d');
            if(backtestChart) backtestChart.destroy();
            
            backtestChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: d.chart.dates,
                    datasets: [
                        { label: 'V20 (AFML)', data: d.chart.v20, borderColor: '#ef4444', borderWidth: 2, fill: false, pointRadius: 0 },
                        { label: 'V19 (Primary)', data: d.chart.v19, borderColor: '#3b82f6', borderWidth: 2, fill: false, pointRadius: 0 },
                        { label: 'Market (HS300)', data: d.chart.market, borderColor: '#9ca3af', borderWidth: 1, borderDash: [5, 5], fill: false, pointRadius: 0 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#aaa' } } },
                    scales: {
                        x: { grid: { color: '#222' }, ticks: { color: '#666', maxTicksLimit: 10 } },
                        y: { grid: { color: '#222' }, ticks: { color: '#666', callback: v => (v * 100).toFixed(0) + '%' } }
                    }
                }
            });
        });
    }

function loadMLSignals() {
        fetch(`/api/ml_predict_all?version=${currentMLVersion}`).then(r => r.json()).then(d => {
            if (d.status !== 'success' || !d.data) {
                document.getElementById('mlSignalContent').innerHTML = '<div class="col text-center text-white-50">信号暂不可用 (可能未进行跑批)</div>';
                document.getElementById('modelReportBadge').innerHTML = '暂无报告';
                document.getElementById('modelReportBadge').className = 'badge text-secondary me-2';
                document.getElementById('mlModelInfo').innerHTML = '未就绪';
                return;
            }
            if(d.meta && d.meta.sample) {
                document.getElementById('mlModelInfo').innerHTML = `<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> 样例数据 (请运行 inference)</span>`;
            } else {
                document.getElementById('mlModelInfo').textContent = `${d.meta.model} · ${d.meta.stocks}只`;
            }
            
            // 获取模型评估简报
            fetch(`/api/model_report?version=${currentMLVersion}`).then(rr => rr.json()).then(rd => {
                let badge = document.getElementById('modelReportBadge');
                if(rd.status === 'success' && rd.data && rd.data.health_check) {
                    let uniqueStr = rd.data.prediction_distribution ? rd.data.prediction_distribution.unique_values : "?";
                    let warnIcon = rd.data.health_check.warnings.length > 0 ? '⚠️' : '✅';
                    badge.innerHTML = `${warnIcon} 唯一值 ${uniqueStr}/${rd.data.stock_count}`;
                    if(rd.data.health_check.warnings.length > 0) {
                        badge.className = "badge text-warning me-2";
                        badge.title = rd.data.health_check.warnings.join("\n");
                    } else {
                        badge.className = "badge text-success me-2";
                        badge.title = "预测分布正常";
                    }
                } else {
                    badge.innerHTML = '暂无报告';
                    badge.className = "badge text-secondary me-2";
                }
            }).catch(e => console.log('获取评估报告失败', e));
            
            allMLData = d.data;
            handleMLFilterChange(); // 初始调用一次过滤（默认全部）
        }).catch(e => {
            console.error('ML Data Error:', e);
            document.getElementById('mlSignalContent').innerHTML = '<div class="col text-center text-white-50">加载失败</div>';
        });
    }

function loadNews() {
        fetch('/api/news').then(r => r.json()).then(d => {
            if (d.status !== 'success' || !d.data) {
                document.getElementById('newsContent').innerHTML = '<div class="text-muted small">新闻暂不可用</div>';
                return;
            }
            allNewsData = d.data;
            const importantCount = d.meta ? d.meta.important_count : d.data.length;
            document.getElementById('newsCount').textContent = `${d.data.length}条 (重要${importantCount}条)`;
            renderNews();
        }).catch(e => {
            document.getElementById('newsContent').innerHTML = '<div class="text-muted small">加载失败</div>';
        });
    }

function loadPreviousScreenerStatus(useAI) {
        fetch('/api/screener/status?use_ai=' + useAI)
        .then(r => r.json())
        .then(res => {
            if(res.status === 'success' && res.data.status === 'finished') {
                document.getElementById('v0StatusBadge').className = 'badge bg-success me-2';
                document.getElementById('v0StatusBadge').innerText = useAI ? '筛选完成(AI缓存)' : '筛选完成(技术缓存)';
                renderV0Table(res.data.data);
                document.getElementById('v0NextStep').style.setProperty('display', 'flex', 'important');
                showToast(`成功加载${useAI ? 'AI' : '技术'}雷达缓存数据！`);
            } else if (res.status === 'success' && res.data.status === 'running') {
                showToast(`后台任务似乎还在运行中或之前被异常中断 (进度: ${res.data.progress}/${res.data.total})，请点击红色的【强制拉取】按钮重新覆盖生成。`);
            } else {
                document.getElementById('v0StatusBadge').className = 'badge bg-secondary me-2';
                document.getElementById('v0StatusBadge').innerText = '无缓存';
                showToast(`未找到完整的${useAI ? 'AI' : '技术'}缓存，请重新运行海选。`);
            }
        }).catch(e => {
            console.error(e);
            showToast('读取缓存失败，网络或后端异常。');
        });
    }

function loadSignalQuality(ver) {
        fetch(`/api/signal_quality?version=${ver}`)
        .then(r => r.json())
        .then(res => {
            if (res.status === 'success' && res.data && res.data.metrics) {
                const m = res.data.metrics;
                const fmt = (val) => {
                    if (val === undefined || val === null) return '--';
                    return typeof val === 'number' ? val.toFixed(4) : val;
                };
                const fmtPct = (val) => {
                    if (val === undefined || val === null) return '--';
                    return typeof val === 'number' ? (val * 100).toFixed(2) + '%' : val;
                };
                
                document.getElementById('metric-ic').innerText = fmt(m.ic_mean);
                document.getElementById('metric-rank-ic').innerText = fmt(m.rank_ic_mean);
                document.getElementById('metric-icir').innerText = fmt(m.icir);
                
                const tbRetEl = document.getElementById('metric-tb-ret');
                tbRetEl.innerText = fmtPct(m.long_short_return);
                tbRetEl.className = m.long_short_return > 0 ? "fw-bold text-success" : "fw-bold text-danger";
                
                const acRetEl = document.getElementById('metric-after-cost');
                acRetEl.innerText = fmtPct(m.return_after_cost);
                acRetEl.className = m.return_after_cost > 0 ? "fw-bold text-success" : "fw-bold text-danger";
            } else {
                ['metric-ic', 'metric-rank-ic', 'metric-icir', 'metric-tb-ret', 'metric-after-cost'].forEach(id => {
                    const el = document.getElementById(id);
                    el.innerText = '未生成';
                    el.className = 'fw-bold text-muted';
                });
            }
        })
        .catch(err => {
            console.error("Failed to load signal quality:", err);
            ['metric-ic', 'metric-rank-ic', 'metric-icir', 'metric-tb-ret', 'metric-after-cost'].forEach(id => {
                    const el = document.getElementById(id);
                    el.innerText = '错误';
                    el.className = 'fw-bold text-danger';
            });
        });
    }

function loadSimAccount() {
        fetch(`/api/sim/info?account_id=${currentAccountId}`).then(r => r.json()).then(d => {
            if (d.status === 'success') {
                const acc = d.data;
                document.getElementById('simTotalAsset').innerText = acc.total_asset.toFixed(2);
                document.getElementById('simCash').innerText = acc.cash.toFixed(2);
                simAutoTrade = acc.auto_trade;
                const toggle = document.getElementById('autoTradeSwitch');
                if (toggle.checked !== simAutoTrade) {
                    toggle.checked = simAutoTrade;
                    document.getElementById('autoTradeLabel').innerText = simAutoTrade ? '已开启' : '已暂停';
                }
                
                // 渲染持仓
                let holdingsHtml = '';
                const hKeys = Object.keys(acc.holdings);
                if (hKeys.length === 0) {
                    holdingsHtml = '<div class="text-center opacity-50 pt-2">空仓中</div>';
                } else {
                    hKeys.forEach(k => {
                        const h = acc.holdings[k];
                        const pl = (h.current_price - h.cost_price) / h.cost_price * 100;
                        const color = pl > 0 ? '#ef4444' : (pl < 0 ? '#10b981' : '#9ca3af');
                        
                        const sl = h.stop_loss ? h.stop_loss.toFixed(2) : '--';
                        const tp = h.take_profit ? h.take_profit.toFixed(2) : '--';
                        
                        holdingsHtml += `<div class="mb-1 pb-1" style="border-bottom: 1px dashed rgba(255,255,255,0.1);">
                            <div class="d-flex justify-content-between">
                                <span>${h.name}(${k})</span>
                                <span>${h.vol}股</span>
                                <span style="color:${color}">${pl > 0 ? '+' : ''}${pl.toFixed(2)}%</span>
                            </div>
                            <div class="d-flex justify-content-between mt-1" style="font-size: 0.8rem; opacity: 0.8;">
                                <span><span style="color:#10b981">止损: ${sl}</span></span>
                                <span><span style="color:#ef4444">止盈: ${tp}</span></span>
                                <span>当前: ${h.current_price.toFixed(2)}</span>
                            </div>
                        </div>`;
                    });
                }
                document.getElementById('simHoldings').innerHTML = holdingsHtml;
                
                // 渲染日志
                const container = document.getElementById('tradeLogsContent');
                if (!acc.logs || acc.logs.length === 0) {
                    container.innerHTML = '<div class="text-center py-2" style="opacity:0.7">暂无交易日志</div>';
                } else {
                    let html = '';
                    acc.logs.forEach(log => {
                        const isBuy = log.action === 'buy';
                        const color = isBuy ? '#ef4444' : '#10b981';
                        const displayDir = isBuy ? '买入' : '卖出';
                        
                        html += `<div style="margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 3px;">
                            <span style="color: #6b7280;">${log.time}</span>
                            <span style="color: ${color}; font-weight: bold; margin: 0 5px;">${displayDir}</span>
                            <span style="color: white;">${log.name}</span>
                            <span style="margin-left: 5px; opacity: 0.8;">${log.vol}股</span>
                            <span style="float: right; font-size: 0.7rem; color: #fbbf24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 90px;" title="${log.reason}">${log.reason}</span>
                        </div>`;
                    });
                    container.innerHTML = html;
                }
            }
        }).catch(e => console.error('Failed to load sim account', e));
    }

function makeChart(canvasId, type, datasets, extraOpts) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        const gridConfig = { color: 'rgba(255, 255, 255, 0.05)', borderColor: 'rgba(255, 255, 255, 0.1)' };
        
        return new Chart(ctx, {
            type, data: { labels: [], datasets },
            options: Object.assign({ 
                responsive: true, 
                maintainAspectRatio: false, 
                animation: { duration: 300 }, 
                scales: {
                    x: { grid: gridConfig, ticks: { color: '#888' } },
                    y: { grid: gridConfig, ticks: { color: '#888' } }
                },
                plugins: { 
                    legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 }, color: '#aaa' } } 
                } 
            }, extraOpts || {})
        });
    }

function manualRefreshNews() {
        const container = document.getElementById('newsContent');
        container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary spinner-border-sm" role="status"></div><div class="mt-2 text-muted" style="font-size:0.75rem">正在全网捕获最新大事件...</div></div>';
        loadNews();
    }

function openAISettings() {
            const modal = new bootstrap.Modal(document.getElementById('aiSettingsModal'));
            modal.show();
            // 获取当前设置
            fetch('/api/settings/ai')
            .then(r => r.json())
            .then(res => {
                if(res.status === 'success') {
                    document.getElementById('aiBaseUrl').value = res.data.base_url || '';
                    document.getElementById('aiApiKey').value = res.data.api_key || '';
                    document.getElementById('aiModelName').value = res.data.model || '';
                }
            }).catch(e => console.error(e));
        }

function openSimAiModal() {
        const modal = new bootstrap.Modal(document.getElementById('simAiModal'));
        const content = document.getElementById('simAiContent');
        content.innerHTML = `<div class="text-center py-5"><div class="spinner-border text-warning"></div><div class="mt-2 small text-white-50">小米大模型 mimo-v2.5-pro 正在深度诊断您的模拟盘...</div></div>`;
        modal.show();

        fetch(`/api/sim/analyze?account_id=${currentAccountId}`)
            .then(r => r.json())
            .then(d => {
                if (d.status === 'success') {
                    content.innerHTML = d.html;
                } else {
                    content.innerHTML = `<div class="text-danger">分析失败: ${d.msg}</div>`;
                }
            })
            .catch(e => {
                content.innerHTML = `<div class="text-danger">网络请求失败: ${e.message}</div>`;
            });
    }

function openTradeLogModal() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const todayStr = `${year}-${month}-${day}`;
        document.getElementById('tradeLogDate').value = todayStr;
        
        fetch(`/api/sim/logs?account_id=${currentAccountId}`).then(r => r.json()).then(d => {
            if (d.status === 'success') {
                allTradeLogs = d.data;
                filterTradeLogs();
            } else {
                showToast('获取记录失败');
            }
            new bootstrap.Modal(document.getElementById('tradeLogModal')).show();
        }).catch(e => {
            showToast('获取记录失败');
        });
    }

function pollPipelineStatus() {
        fetch('/api/pipeline/status')
        .then(r => r.json())
        .then(res => {
            if(res.status === 'success') {
                const d = res.data;
                document.getElementById('pipeProgressBar').style.width = d.progress + '%';
                document.getElementById('pipeProgressMsg').innerText = d.message;
                
                if(d.status === 'error') {
                    clearInterval(pipePollInterval);
                    document.getElementById('pipeProgressBar').className = 'progress-bar bg-danger';
                    document.getElementById('btnRunPipeline').disabled = false;
                }
                else if(d.status === 'finished') {
                    clearInterval(pipePollInterval);
                    document.getElementById('pipeProgressBar').className = 'progress-bar bg-success';
                    document.getElementById('btnRunPipeline').disabled = false;
                    setTimeout(() => {
                        // 强制折叠 V0 并展开 V20，并刷新数据
                        document.querySelector('[data-bs-target="#collapseV0"]').click();
                        document.querySelector('[data-bs-target="#collapseML"]').click();
                        document.getElementById('modelVersionSelect').value = 'v20';
                        switchModelVersion('v20');
                        fetchPredictions(); // 刷新潜力池
                    }, 2000);
                }
            }
        }).catch(e => console.error(e));
    }

function pollTrainStatus() {
            fetch('/api/weekly_train/status')
                .then(r => r.json())
                .then(res => {
                    if(res.status === 'success') {
                        const s = res.data.status;
                        const p = res.data.progress;
                        const el = document.getElementById('v21TrainStatus');
                        el.textContent = `${s === 'running' ? '训练中 ' + p + '%' : s}`;
                        
                        const pContainer = document.getElementById('v21ProgressContainer');
                        const pBar = document.getElementById('v21ProgressBar');
                        
                        if(s === 'running') {
                            pContainer.style.display = 'flex';
                            pBar.style.width = p + '%';
                            pBar.className = 'progress-bar progress-bar-striped progress-bar-animated bg-warning';
                        } else if(s === 'success' || s === 'finished') {
                            pContainer.style.display = 'flex';
                            pBar.style.width = '100%';
                            pBar.className = 'progress-bar bg-success';
                            setTimeout(() => { pContainer.style.display = 'none'; }, 2000);
                            clearInterval(trainPollInterval);
                        } else if(s === 'error') {
                            pContainer.style.display = 'flex';
                            pBar.style.width = '100%';
                            pBar.className = 'progress-bar bg-danger';
                            setTimeout(() => { pContainer.style.display = 'none'; }, 3000);
                            clearInterval(trainPollInterval);
                        } else if(s === 'idle') {
                            pContainer.style.display = 'none';
                        }
                    }
                });
        }

function pollV0Status() {
        fetch('/api/screener/status?use_ai=' + currentV0UseAI)
        .then(r => r.json())
        .then(res => {
            if(res.status === 'success') {
                const d = res.data;
                const pct = d.total > 0 ? Math.round((d.progress / d.total) * 100) : 0;
                
                document.getElementById('v0ProgressBar').style.width = pct + '%';
                document.getElementById('v0ProgressBar').innerText = pct + '%';
                document.getElementById('v0ProgressMsg').innerText = d.message;
                
                if(d.status === 'error') {
                    clearInterval(v0PollInterval);
                    document.getElementById('v0StatusBadge').className = 'badge bg-danger me-2';
                    document.getElementById('v0StatusBadge').innerText = '异常中断';
                }
                else if(d.status === 'finished') {
                    clearInterval(v0PollInterval);
                    document.getElementById('v0StatusBadge').className = 'badge bg-success me-2';
                    document.getElementById('v0StatusBadge').innerText = '筛选完成';
                    document.getElementById('v0ProgressContainer').style.display = 'none';
                    document.getElementById('v0ProgressMsg').style.display = 'none';
                    renderV0Table(d.data);
                    document.getElementById('v0NextStep').style.setProperty('display', 'flex', 'important');
                }
            }
        }).catch(e => console.error(e));
    }

function refreshAll() {
        if (!autoRefresh) return;
        const now = Date.now();
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });

        if (now - lastReq.realtime >= INTERVALS.realtime) {
            lastReq.realtime = now;
            fetchJSON(`/api/realtime/${selectedStock}`, updateMetrics);
        }
        if (now - lastReq.minute >= INTERVALS.minute) {
            lastReq.minute = now;
            fetchJSON(`/api/minute/${selectedStock}?scale=5&datalen=48`, resp => {
                if (resp.status === 'success') updateMinuteCharts(resp.data);
            });
        }
        if (now - lastReq.technical >= INTERVALS.technical) {
            lastReq.technical = now;
            fetchJSON(`/api/technical/${selectedStock}?datalen=100`, resp => {
                if (resp.status === 'success') updateTechnicalCharts(resp.data);
            });
        }
        if (now - lastReq.predict >= INTERVALS.predict) {
            lastReq.predict = now;
            fetchJSON(`/api/predict/${selectedStock}`, resp => {
                if (resp.status === 'success') updatePrediction(resp.data);
            });
        }
    }

function refreshWatchlist() {
        const tbody = document.getElementById('watchlistTable');
        if (customStocks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">暂无自选股票</td></tr>';
            return;
        }
        
        // Render rows with IDs for each stock
        tbody.innerHTML = customStocks.map(s => 
            `<tr id="watchlist-${s.code}">
                <td><strong>${s.code}</strong></td>
                <td>${s.name || '--'}</td>
                <td class="watchlist-price">--</td>
                <td class="watchlist-change">--</td>
                <td class="watchlist-volume">--</td>
                <td class="watchlist-pred">--</td>
                <td class="watchlist-signal">--</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="viewStock('${s.code}')" title="查看分析">📊</button>
                    <button class="btn btn-sm btn-outline-info" onclick="analyzeFundamentals('${s.code}','${s.name}')" title="基本面研判">🧠</button>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeCustomStock('${s.code}')" title="删除">✕</button>
                </td>
            </tr>`
        ).join('');
        
        // Fetch real-time data for each stock
        customStocks.forEach(stock => {
            fetch(`/api/realtime/${stock.code}`).then(r => r.json()).then(d => {
                if (d.status === 'success') {
                    updateWatchlistStock(stock.code, d);
                }
            }).catch(() => {});
            
            // Fetch ML prediction
            const version = localStorage.getItem('modelVersion') || 'v19';
            fetch(`/api/ml_predict/${stock.code}?version=${version}`).then(r => r.json()).then(d => {
                if (d.status === 'success' && d.data) {
                    updateWatchlistPrediction(stock.code, d.data);
                } else {
                    const row = document.getElementById(`watchlist-${stock.code}`);
                    if (row) {
                        row.querySelector('.watchlist-pred').textContent = 'N/A';
                        row.querySelector('.watchlist-signal').innerHTML = '<span class="badge bg-secondary opacity-50" style="font-size:0.6rem">非池内</span>';
                    }
                }
            }).catch(() => {});
        });
    }

function refreshWeeklyPool() {
            const tbody = document.getElementById('weeklySwingTable');
            tbody.innerHTML = '<tr><td colspan="10" class="text-center opacity-50 py-3">加载中...</td></tr>';
            fetch(`/api/weekly_predict_all?t=${new Date().getTime()}`)
                .then(r => r.json())
                .then(res => {
                    if(res.status === 'success') {
                        let html = '';
                        const stocks = Object.values(res.data);
                        stocks.sort((a, b) => b.win_prob - a.win_prob);
                        for(const info of stocks) {
                            if(info.name.includes('ST') || info.name.includes('退')) continue;
                            const signalClass = info.signal.includes('看涨') ? 'text-danger' : 'text-success';
                            html += `
                                <tr>
                                    <td>${info.code}</td>
                                    <td>${info.name}</td>
                                    <td>${(info.win_prob * 100).toFixed(1)}%</td>
                                    <td class="text-danger">+${(info.expected_5d_return * 100).toFixed(2)}%</td>
                                    <td>${info.meta_score.toFixed(3)}</td>
                                    <td class="text-danger">+${info.take_profit_pct}%</td>
                                    <td class="text-success">${info.stop_loss_pct}%</td>
                                    <td>${info.max_holding_days} 天</td>
                                    <td class="${signalClass} fw-bold">${info.signal}</td>
                                    <td class="small opacity-75">${info.reason_factors}</td>
                                </tr>
                            `;
                        }
                        if(html === '') html = '<tr><td colspan="10" class="text-center opacity-50 py-3">符合条件的标的为空</td></tr>';
                        tbody.innerHTML = html;
                    } else {
                        tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger py-3">${res.message}</td></tr>`;
                    }
                })
                .catch(e => {
                    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger py-3">网络错误</td></tr>`;
                });
        }

function removeCustomStock(code) {
        if (!confirm(`确定从自选中删除 ${code}？`)) return;
        customStocks = customStocks.filter(s => s.code !== code);
        localStorage.setItem('customStocks', JSON.stringify(customStocks));
        updateCustomStocksUI();
        showToast(`已从自选中移除 ${code}`);
    }

function renderMLPage() {
        const dataToRender = filteredMLData;
        
        const start = (currentMLPage - 1) * mlPageSize;
        const end = start + mlPageSize;
        const pageData = dataToRender.slice(start, end);
        const totalPages = Math.ceil(dataToRender.length / mlPageSize);

        const generateCardHtml = (s) => {
            const isV20 = document.getElementById('modelVersionSelect').value === 'v20';
            const icon = s.predicted_return > 0.02 ? '🔥' : s.predicted_return > 0 ? '📈' : s.predicted_return < 0 ? '📉' : '➡️';
            const rsMom = s.relative_strength ? s.relative_strength.momentum : 0;
            const momIcon = rsMom > 0.5 ? '↑' : rsMom < -0.5 ? '↓' : '→';
            
            // 颜色逻辑优化：红色看涨，黄色中性，绿色下跌
            let badgeClass = 'bg-secondary';
            if (s.signal.includes('看涨')) badgeClass = 'bg-danger';
            else if (s.signal === '中性') badgeClass = 'bg-warning text-dark';
            else if (s.signal === '看跌') badgeClass = 'bg-success';
            
            // 显示文本: v20 显示胜率，其他显示预期收益率
            let showText = isV20 ? `${s.predicted_return > 0 ? '+' : ''}${(s.predicted_return * 100).toFixed(1)}% 胜率` : `${s.predicted_return > 0 ? '+' : ''}${(s.predicted_return * 100).toFixed(2)}%`;

            return `
            <div class="col">
                <div class="ml-stock text-center py-3">
                    <div class="name h5 mb-2">${s.name}</div>
                    <div class="pred h3 mb-2">${showText}</div>
                    <div class="meta text-white-50 mb-2 small">${isV20 ? '🛡️ AFML元阻击' : icon + ' 动量' + momIcon + (rsMom > 0 ? '+' : '') + rsMom.toFixed(1)}</div>
                    <span class="badge ${badgeClass} px-3" style="font-weight:bold">${s.signal}</span>
                </div>
            </div>`;
        };

        // 渲染全量卡片
        let contentHtml = '';
        pageData.forEach(s => {
            contentHtml += generateCardHtml(s);
        });
        document.getElementById('mlSignalContent').innerHTML = contentHtml || '<div class="col-12 text-center py-4 text-white-50">无匹配信号</div>';
        
        // 3. 更新分页信息
        document.getElementById('mlPaginationInfo').textContent = `第 ${currentMLPage} / ${totalPages || 1} 页 (共 ${dataToRender.length} 只)`;
        document.getElementById('mlPrevBtn').disabled = currentMLPage <= 1;
        document.getElementById('mlNextBtn').disabled = currentMLPage >= totalPages;
    }

function renderNews() {
        const container = document.getElementById('newsContent');
        if (!allNewsData || allNewsData.length === 0) {
            container.innerHTML = '<div class="text-muted small">暂无新闻</div>';
            return;
        }
        
        // 根据模式筛选
        let filtered = newsMode === 'important' 
            ? allNewsData.filter(n => n.is_important || n.is_important === undefined) // 兼容老数据
            : allNewsData;
        
        // 限制显示数量
        const limit = newsMode === 'important' ? 15 : 30;
        filtered = filtered.slice(0, limit);
        
        let html = '';
        filtered.forEach((news, index) => {
            // 鲁棒性检查：如果字段缺失给出默认值
            const sentiment = news.sentiment || '中性';
            const icon = sentiment === '利好' ? '🟢' : (sentiment === '利空' ? '🔴' : '⚪');
            const cls = sentiment === '利好' ? 'positive' : (sentiment === '利空' ? 'negative' : '');
            const source = news.source || '新浪财经';
            const time = news.time || '--:--';
            const title = news.title || '无标题';
            
            let stockTagHtml = '';
            if (news.related_stocks && news.related_stocks.length > 0) {
                const stock = news.related_stocks[0];
                const codeWithoutPrefix = stock.code.replace(/^[a-zA-Z]+/, '');
                stockTagHtml = `<span class="badge bg-primary ms-1" style="font-size:0.6rem; cursor: pointer;" onclick="event.stopPropagation(); buyStockFromNews('${codeWithoutPrefix}', '${stock.name}')">🎯 买入 ${stock.name}</span>`;
            }
            
            const isImportant = news.is_important || false;
            const importantBadge = isImportant ? '<span class="badge bg-danger ms-1" style="font-size:0.55rem">重要</span>' : '';
            
            // 为了安全，不在 onclick 传超大文本，而是传 index
            const aiButton = `<span class="badge bg-purple ms-1" style="font-size:0.6rem; cursor: pointer; background-color:#6f42c1" onclick="event.stopPropagation(); analyzeNewsByIndex(${index})">🧠 AI 推演</span>`;

            html += `
            <div class="news-item ${cls}" style="cursor: pointer;" onclick="window.open('${news.url || '#'}', '_blank')">
                <div style="font-size:0.8rem;font-weight:600">${icon} ${title}${importantBadge}</div>
                <div style="font-size:0.65rem;color:#888;display:flex;justify-content:space-between;align-items:center;">
                    <span>[${source}] ${time} ${stockTagHtml} ${aiButton}</span>
                    <span class="text-primary-emphasis" style="font-size:0.6rem">详情 ></span>
                </div>
            </div>`;
        });
        container.innerHTML = html || '<div class="text-muted small">暂无匹配新闻</div>';
    }

function renderV0Table(data) {
        const tbody = document.getElementById('v0TableBody');
        tbody.innerHTML = '';
        if(!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary">暂无符合条件的活水标的</td></tr>';
        } else {
            let html = '';
            data.forEach(item => {
                let aiScoreHtml = item.ai_score ? `<span class="badge ${item.ai_score > 85 ? 'bg-danger' : 'bg-warning text-dark'}">${item.ai_score}</span>` : '<span class="text-secondary">-</span>';
                let changeColor = item.change_pct > 0 ? 'text-danger' : 'text-success';
                html += `<tr>
                    <td>${item.code}</td>
                    <td>${item.name}</td>
                    <td class="${changeColor}">${item.price}</td>
                    <td class="${changeColor}">${item.change_pct}%</td>
                    <td>${item.turnover}%</td>
                    <td>${aiScoreHtml}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-info py-0 px-2" style="font-size: 0.75rem;" onclick="showV0Logic(this)" data-name="${item.name}" data-code="${item.code}" data-logic="${encodeURIComponent(item.logic)}">
                            <i class="fas fa-file-alt me-1"></i>查看详情
                        </button>
                    </td>
                </tr>`;
            });
            tbody.innerHTML = html;
        }
        document.getElementById('v0Table').style.display = 'table';
    }

function runBacktest() {
        const startDate = document.getElementById('btStartDate').value;
        const endDate = document.getElementById('btEndDate').value;
        document.getElementById('backtestStats').innerHTML = '<div class="text-warning spinner-border spinner-border-sm" role="status"></div> 正在运行回测，请稍候 (可能需要几十秒)...';
        
        fetch('/api/run_backtest', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({start_date: startDate, end_date: endDate})
        })
        .then(r => r.json())
        .then(res => {
            if(res.status === 'success') {
                document.getElementById('btChartTitle').innerText = `累计收益率对冲曲线 (${startDate} 至 ${endDate})`;
                loadBacktestData();
            } else {
                document.getElementById('backtestStats').innerHTML = `<div class="text-danger">${res.message}</div>`;
            }
        })
        .catch(err => {
            document.getElementById('backtestStats').innerHTML = `<div class="text-danger">请求失败: ${err}</div>`;
        });
    }

function saveAISettings() {
            const data = {
                base_url: document.getElementById('aiBaseUrl').value.trim(),
                api_key: document.getElementById('aiApiKey').value.trim(),
                model: document.getElementById('aiModelName').value.trim()
            };
            fetch('/api/settings/ai', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(res => {
                if(res.status === 'success') {
                    showToast('大模型配置保存成功！后续的研判将自动切换至新模型。');
                    bootstrap.Modal.getInstance(document.getElementById('aiSettingsModal')).hide();
                } else {
                    showToast('保存失败: ' + res.message);
                }
            })
            .catch(e => showToast('网络异常'));
        }

function searchStock() {
        const keyword = document.getElementById('searchInput').value.trim();
        if (!keyword) return;
        const container = document.getElementById('searchResults');
        container.style.display = 'block';
        container.innerHTML = '<div class="text-center p-2"><div class="spinner-border spinner-border-sm"></div> 搜索中...</div>';
        
        fetch(`/api/search?q=${encodeURIComponent(keyword)}`).then(r => r.json()).then(d => {
            if (d.status !== 'success' || !d.data || d.data.length === 0) {
                container.innerHTML = '<div class="text-muted p-2">未找到</div>';
                return;
            }
            let html = '';
            d.data.forEach(s => {
                const isAdded = customStocks.find(c => c.code === s.code);
                html += `
                <div class="d-flex justify-content-between align-items-center p-2 border-bottom">
                    <div>
                        <strong>${s.code}</strong> ${s.name}
                        <span class="badge bg-secondary ms-1" style="font-size:0.65rem">${s.type || 'A股'}</span>
                    </div>
                    <button class="btn btn-sm ${isAdded ? 'btn-outline-secondary' : 'btn-dark'}" 
                            onclick="addCustomStock('${s.code}','${s.name}','${s.market}')" ${isAdded ? 'disabled' : ''}>
                        ${isAdded ? '已添加' : '+ 添加'}
                    </button>
                </div>`;
            });
            container.innerHTML = html;
        }).catch(e => { container.innerHTML = '<div class="text-danger p-2">搜索失败</div>'; });
    }

function selectStock(code) {
        selectedStock = code;
        buildStockList();
        lastReq = { realtime: 0, minute: 0, technical: 0, predict: 0 };
        refreshAll();
    }

function selectSuggestion(code, name) {
        document.getElementById('searchInput').value = code;
        document.getElementById('searchSuggestions').style.display = 'none';
        searchStock();
    }

function setupEvents() {
        document.getElementById('autoRefresh').addEventListener('change', function() { autoRefresh = this.checked; });
        document.getElementById('refreshInterval').addEventListener('input', function() {
            refreshInterval = parseInt(this.value);
            document.getElementById('intervalValue').textContent = refreshInterval;
        });
    }

function showBacktestReport() {
        const modal = new bootstrap.Modal(document.getElementById('backtestModal'));
        modal.show();
        loadBacktestData();
    }

function showToast(message) {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            
            const toast = document.createElement('div');
            toast.className = 'bg-dark text-white border border-secondary rounded shadow';
            toast.style.minWidth = '300px';
            toast.style.maxWidth = '500px';
            toast.style.animation = 'toastFadeIn 0.3s ease-in-out';
            toast.style.padding = '15px';
            toast.style.pointerEvents = 'auto'; // allow text selection
            
            let displayMsg = message;
            if (typeof message === 'object') {
                displayMsg = JSON.stringify(message, null, 2);
            }
            
            // Format like the browser alert
            const msgDiv = document.createElement('div');
            msgDiv.innerHTML = `
                <div style="font-weight: 500; font-size: 1rem; margin-bottom: 8px;">127.0.0.1:5000 显示</div>
                <div style="white-space: pre-wrap; font-size: 0.9rem; color: #e9ecef; max-height: 400px; overflow-y: auto;">${displayMsg}</div>
            `;
            toast.appendChild(msgDiv);
            
            container.appendChild(toast);
            
            // Auto remove after 3 seconds
            setTimeout(() => {
                if(toast.parentNode) {
                    toast.style.animation = 'toastFadeOut 0.3s ease-in-out forwards';
                    setTimeout(() => {
                        if(toast.parentNode) toast.remove();
                    }, 300);
                }
            }, 3000);
        }

function showV0Logic(btn) {
        const name = btn.getAttribute('data-name');
        const code = btn.getAttribute('data-code');
        const logicRaw = btn.getAttribute('data-logic');
        const logicHTML = decodeURIComponent(logicRaw);
        
        document.getElementById('rankAnalysisTitle').textContent = `入选逻辑: ${name} (${code})`;
        document.getElementById('rankAnalysisContent').innerHTML = `
            <div class="p-3" style="font-size: 0.95rem; line-height: 1.6; color: #e5e7eb;">
                ${logicHTML}
            </div>
        `;
        const modal = new bootstrap.Modal(document.getElementById('rankAnalysisModal'));
        modal.show();
    }

function startPipeline() {
        if(pipePollInterval) clearInterval(pipePollInterval);
        document.getElementById('pipeProgressContainer').style.display = 'flex';
        document.getElementById('pipeProgressMsg').style.display = 'block';
        document.getElementById('btnRunPipeline').disabled = true;
        
        fetch('/api/pipeline/start', { method: 'POST' })
        .then(r => r.json()).then(d => {
            pipePollInterval = setInterval(pollPipelineStatus, 2000);
        });
    }

function startV0Screener(useAI, forceRefresh=false) {
        if(v0PollInterval) clearInterval(v0PollInterval);
        currentV0UseAI = useAI;
        
        document.getElementById('v0ProgressContainer').style.display = 'flex';
        document.getElementById('v0ProgressMsg').style.display = 'block';
        document.getElementById('v0StatusBadge').className = 'badge bg-warning text-dark me-2';
        document.getElementById('v0StatusBadge').innerText = '扫描中...';
        document.getElementById('v0Table').style.display = 'none';
        document.getElementById('v0NextStep').style.setProperty('display', 'none', 'important');
        
        fetch('/api/screener/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({use_ai: useAI, force_refresh: forceRefresh})
        }).then(r => r.json()).then(d => {
            v0PollInterval = setInterval(pollV0Status, 2000);
        });
    }

function startWeeklyTrain() {
            if (!confirm("确定要启动 V21 模型训练吗？这可能需要几分钟。")) return;
            document.getElementById('v21ProgressContainer').style.display = 'flex';
            document.getElementById('v21ProgressBar').style.width = '0%';
            document.getElementById('v21ProgressBar').className = 'progress-bar progress-bar-striped progress-bar-animated bg-warning';
            fetch('/api/weekly_train/start', { method: 'POST' })
                .then(r => r.json())
                .then(res => {
                    showToast(res.message);
                    if(res.status === 'success' || res.message.includes('运行中')) {
                        if(trainPollInterval) clearInterval(trainPollInterval);
                        trainPollInterval = setInterval(pollTrainStatus, 2000);
                        // Also do an immediate poll so UI updates instantly
                        pollTrainStatus();
                    } else {
                        document.getElementById('v21ProgressContainer').style.display = 'none';
                    }
                }).catch(() => {
                    document.getElementById('v21ProgressContainer').style.display = 'none';
                });
        }

function switchModelVersion(ver) {
        currentMLVersion = ver;
        const btnExecute = document.getElementById('btnExecuteV20');
        if(ver === 'v20') {
            btnExecute.style.display = 'inline-block';
        } else {
            btnExecute.style.display = 'none';
        }
        document.getElementById('mlSignalContent').innerHTML = '<div class="col text-center text-white-50">切换模型并重新加载中...</div>';
        loadMLSignals();
        loadSignalQuality(ver);
    }

function toggleAutoTrade(checked) {
        simAutoTrade = checked;
        document.getElementById('autoTradeLabel').innerText = checked ? '已开启' : '已暂停';
        fetch(`/api/sim/toggle_auto?account_id=${currentAccountId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auto_trade: checked })
        });
    }

function toggleNewsMode() {
        newsMode = newsMode === 'important' ? 'all' : 'important';
        document.getElementById('newsToggle').textContent = newsMode === 'important' ? '全部' : '重要';
        renderNews();
    }

function toggleWatchlistPanel() {
        const body = document.getElementById('watchlistBody');
        const btn = document.querySelector('#watchlistPanel .btn-outline-secondary');
        watchlistCollapsed = !watchlistCollapsed;
        body.style.display = watchlistCollapsed ? 'none' : 'block';
        btn.textContent = watchlistCollapsed ? '展开' : '收起';
    }

function triggerSimStep() {
        const btn = event.currentTarget;
        const oldText = btn.innerHTML;
        btn.innerHTML = '处理中...';
        btn.disabled = true;
        
        fetch(`/api/sim/step?account_id=${currentAccountId}`, { 
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ force: true })
        })
        .then(r => r.json())
        .then(d => {
            if (d.status === 'success') {
                // success
            } else if (d.status === 'skip') {
                showToast('提示: ' + d.msg);
            }
            
    function changeAccount(id) {
        currentAccountId = id;
        loadSimAccount();
    }

    function loadAccountList() {
        fetch('/api/sim/accounts').then(r => r.json()).then(d => {
            if (d.status === 'success') {
                const sel = document.getElementById('accountSelector');
                sel.innerHTML = '';
                d.accounts.forEach(acc => {
                    const opt = document.createElement('option');
                    opt.value = acc;
                    opt.innerText = acc === 'default' ? '默认 V19' : acc.replace('douyin_', '游资-');
                    sel.appendChild(opt);
                });
                sel.value = currentAccountId;
            }
        });
    }
    loadAccountList();

    loadSimAccount(); // 强制刷新状态
        })
        .finally(() => {
            btn.innerHTML = oldText;
            btn.disabled = false;
        });
    }

function updateChartData(chart, labels, datasets) {
        chart.data.labels = labels;
        datasets.forEach((ds, i) => { chart.data.datasets[i].data = ds; });
        chart.update('none');
    }

function updateCustomStocksUI() {
        const panel = document.getElementById('watchlistPanel');
        const count = document.getElementById('watchlistCount');
        
        if (customStocks.length === 0) {
            panel.style.display = 'none';
            return;
        }
        
        panel.style.display = 'block';
        count.textContent = customStocks.length;
        refreshWatchlist();
    }

function updateMetrics(d) {
        const cls = d.change >= 0 ? 'positive' : 'negative';
        document.getElementById('m-price').className = `value ${cls}`;
        document.getElementById('m-price').textContent = d.current.toFixed(2);
        document.getElementById('m-name').textContent = d.name;
        document.getElementById('m-change').className = `value ${cls}`;
        document.getElementById('m-change').textContent = (d.change_percent >= 0 ? '+' : '') + d.change_percent.toFixed(2) + '%';
        document.getElementById('m-change-val').textContent = (d.change >= 0 ? '+' : '') + d.change.toFixed(2);
        document.getElementById('m-volume').textContent = (d.volume / 10000).toFixed(0);
        document.getElementById('m-amount').textContent = (d.amount / 1e8).toFixed(2);

        document.getElementById('dataTable').innerHTML = `<tr><td>${d.code}</td><td>${d.name}</td>
            <td class="${cls}">${d.current.toFixed(2)}</td><td class="${cls}">${d.change_percent.toFixed(2)}%</td>
            <td>${(d.volume/10000).toFixed(0)}万</td><td>${(d.amount/1e8).toFixed(2)}亿</td><td>${d.time}</td></tr>`;
    }

function updateMinuteCharts(data) {
        if (!data || !data.length) return;
        const labels = data.map(i => i.day.split(' ')[1].substring(0, 5));
        const prices = data.map(i => parseFloat(i.close));
        const vols = data.map(i => parseFloat(i.volume));
        const volColors = data.map((item, idx) => {
            if (idx === 0) return 'rgba(30,60,114,0.7)';
            return parseFloat(item.close) >= parseFloat(data[idx-1].close) ? 'rgba(255,75,75,0.7)' : 'rgba(0,213,107,0.7)';
        });
        updateChartData(charts.price, labels, [prices, [], [], [], []]);
        updateChartData(charts.volume, labels, [vols]);
        charts.volume.data.datasets[0].backgroundColor = volColors;
        charts.volume.update('none');
    }

function updatePrediction(d) {
        // 处理已收盘状态
        if (d.is_market_closed) {
            document.getElementById('pred-action').className = 'neutral';
            document.getElementById('pred-action').textContent = '⏸️ 已收盘';
            document.getElementById('pred-time').textContent = '非交易时段 · 信号仅供参考';
            document.getElementById('prob-up').style.width = '50%';
            document.getElementById('prob-up').textContent = '暂停';
            document.getElementById('prob-down').style.width = '50%';
            document.getElementById('prob-down').textContent = '暂停';
            document.getElementById('signalContent').innerHTML = '<span class="signal-tag signal-neutral">当前非交易时间</span><span class="signal-tag signal-neutral">技术面信号仅供参考</span>';
            document.getElementById('indicatorDetails').innerHTML = '<div class="indicator-item"><div class="name">状态</div><div class="value">已收盘</div><div class="desc">明日开盘后更新</div></div>';
            return;
        }
        
        const cls = d.action_class === 'positive' ? 'positive' : d.action_class === 'negative' ? 'negative' : 'neutral';
        document.getElementById('pred-action').className = '';
        document.getElementById('pred-action').classList.add(cls);
        document.getElementById('pred-action').textContent = d.action;
        document.getElementById('pred-time').textContent = `${d.prediction_time} · 强度 ${d.signal_strength > 0 ? '+' : ''}${d.signal_strength}`;
        document.getElementById('prob-up').style.width = d.up_probability + '%';
        document.getElementById('prob-up').textContent = '涨 ' + d.up_probability + '%';
        document.getElementById('prob-down').style.width = d.down_probability + '%';
        document.getElementById('prob-down').textContent = '跌 ' + d.down_probability + '%';

        let sigHtml = '';
        d.signals.forEach(s => {
            let c = 'signal-neutral';
            if (/向上|金叉|超卖|上涨|多头|支撑|反弹|流入|底背离|强趋势↑/.test(s)) c = 'signal-bullish';
            else if (/向下|死叉|超买|下跌|空头|压力|回调|流出|顶背离|强趋势↓/.test(s)) c = 'signal-bearish';
            sigHtml += `<span class="signal-tag ${c}">${s}</span>`;
        });
        document.getElementById('signalContent').innerHTML = sigHtml;

        if (d.indicators) {
            const ind = d.indicators;
            const items = [
                { name: '布林%B', value: ind.BB_PCT ? ind.BB_PCT.toFixed(2) : '--', desc: ind.BB_PCT > 1 ? '超买' : ind.BB_PCT < 0 ? '超卖' : '正常' },
                { name: 'VWAP', value: ind.VWAP ? ind.VWAP.toFixed(2) : '--', desc: d.current_price > ind.VWAP ? '多头' : '空头' },
                { name: '量比', value: ind.VOL_RATIO ? ind.VOL_RATIO.toFixed(2) : '--', desc: ind.VOL_RATIO > 2 ? '放量' : ind.VOL_RATIO < 0.5 ? '缩量' : '正常' },
                { name: 'CCI', value: ind.CCI ? ind.CCI.toFixed(0) : '--', desc: ind.CCI > 100 ? '超买' : ind.CCI < -100 ? '超卖' : '中性' },
                { name: 'ADX', value: ind.ADX ? ind.ADX.toFixed(0) : '--', desc: ind.ADX > 25 ? '有趋势' : '无趋势' },
                { name: '+DI/-DI', value: `${(ind.PLUS_DI||0).toFixed(0)}/${(ind.MINUS_DI||0).toFixed(0)}`, desc: ind.PLUS_DI > ind.MINUS_DI ? '多头' : '空头' },
                { name: 'OBV', value: ind.OBV ? (ind.OBV/10000).toFixed(0)+'万' : '--', desc: '能量潮' },
                { name: 'ATR', value: ind.ATR ? ind.ATR.toFixed(3) : '--', desc: '波幅' }
            ];
            let html = '';
            items.forEach(i => {
                html += `<div class="indicator-item"><div class="name">${i.name}</div><div class="value">${i.value}</div><div class="desc">${i.desc}</div></div>`;
            });
            document.getElementById('indicatorDetails').innerHTML = html;
        }
    }

function updateRankings() {
        fetch('/api/market_rankings')
            .then(r => r.json())
            .then(d => {
                if (d.status === 'success') {
                    const monsterBody = document.getElementById('monsterRankingBody');
                    const firstBody = document.getElementById('firstLimitRankingBody');
                    
                    if (d.data.monster && d.data.monster.length > 0) {
                        monsterBody.innerHTML = d.data.monster.map(s => `
                            <tr onclick="selectStock('${s['代码']}')" style="cursor:pointer">
                                <td><span class="text-warning fw-bold">${s['名称']}</span><br/><small class="text-muted">${s['代码']}</small></td>
                                <td><span class="badge bg-danger">${s['连板数']}连板</span></td>
                                <td><small>${s['所属行业']}</small></td>
                                <td onclick="event.stopPropagation()">
                                    <button class="btn btn-xs btn-outline-secondary" onclick="analyzeRankStock('${s['代码']}', '${s['名称']}', true, false)">基本面</button>
                                    <button class="btn btn-xs btn-outline-danger" onclick="analyzeRankStock('${s['代码']}', '${s['名称']}', true, true)">AI分析</button>
                                </td>
                            </tr>
                        `).join('');
                    } else {
                        monsterBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-muted">暂无符合条件的妖股</td></tr>';
                    }
                    
                    if (d.data.first_limit && d.data.first_limit.length > 0) {
                        firstBody.innerHTML = d.data.first_limit.map(s => `
                            <tr onclick="selectStock('${s['代码']}')" style="cursor:pointer">
                                <td><span class="text-info fw-bold">${s['名称']}</span><br/><small class="text-muted">${s['代码']}</small></td>
                                <td>${(s['成交额']/100000000).toFixed(1)}亿</td>
                                <td><small>${s['所属行业']}</small></td>
                                <td onclick="event.stopPropagation()">
                                    <button class="btn btn-xs btn-outline-secondary" onclick="analyzeRankStock('${s['代码']}', '${s['名称']}', false, false)">基本面</button>
                                    <button class="btn btn-xs btn-outline-primary" onclick="analyzeRankStock('${s['代码']}', '${s['名称']}', false, true)">AI分析</button>
                                </td>
                            </tr>
                        `).join('');
                    } else {
                        firstBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-muted">暂无首板股</td></tr>';
                    }
                }
            })
            .catch(e => console.error('Rankings error:', e));
    }

function updateTechnicalCharts(data) {
        if (!data || data.length < 20) return;
        const labels = data.map(i => i.time ? i.time.split(' ')[1].substring(0, 5) : '');
        const closes = data.map(i => i.close);
        updateChartData(charts.price, labels, [closes, data.map(i=>i.vwap), data.map(i=>i.bb_upper), data.map(i=>i.bb_mid), data.map(i=>i.bb_lower)]);

        const macdColors = data.map(i => (i.macd||0) >= 0 ? 'rgba(255,75,75,0.7)' : 'rgba(0,213,107,0.7)');
        charts.macd.data.labels = labels;
        charts.macd.data.datasets[0].data = data.map(i => i.macd||0);
        charts.macd.data.datasets[0].backgroundColor = macdColors;
        charts.macd.data.datasets[1].data = data.map(i => i.dif||0);
        charts.macd.data.datasets[2].data = data.map(i => i.dea||0);
        charts.macd.update('none');

        updateChartData(charts.kdj, labels, [data.map(i=>i.k||0), data.map(i=>i.d||0), data.map(i=>i.j||0)]);
        updateChartData(charts.rsi, labels, [data.map(i=>i.rsi14||50)]);
        // 如果数据里有这几项，加上处理逻辑，如果没有就用默认值
        updateChartData(charts.cci, labels, [data.map(i=>i.cci||0)]);
        updateChartData(charts.dmi, labels, [data.map(i=>i.plus_di||0), data.map(i=>i.minus_di||0), data.map(i=>i.adx||0)]);
    }

function updateWatchlistPrediction(code, data) {
        const row = document.getElementById(`watchlist-${code}`);
        if (!row) return;
        
        const up_prob = data.up_probability || (data.meta_score ? data.meta_score * 100 : 0);
        const signal = data.signal || '中性';
        const predClass = up_prob >= 50 ? 'positive' : 'negative';
        
        // 颜色映射逻辑
        let signalClass = 'signal-neutral';
        if (signal.includes('看涨')) signalClass = 'signal-bullish';
        else if (signal === '看跌') signalClass = 'signal-bearish';
        
        row.querySelector('.watchlist-pred').className = `watchlist-pred ${predClass}`;
        if (up_prob > 0) {
            row.querySelector('.watchlist-pred').textContent = `${up_prob.toFixed(1)}%`;
        } else {
            const pred = data.predicted_return || 0;
            row.querySelector('.watchlist-pred').textContent = `${pred >= 0 ? '+' : ''}${(pred*100).toFixed(1)}%`;
        }
        row.querySelector('.watchlist-signal').innerHTML = `<span class="signal-tag ${signalClass}">${signal}</span>`;
    }

function updateWatchlistStock(code, data) {
        const row = document.getElementById(`watchlist-${code}`);
        if (!row) return;
        
        const price = data.current || data.current_price || 0;
        const change = data.change_percent || 0;
        const volume = data.volume || 0;
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const changeSign = change >= 0 ? '+' : '';
        
        row.querySelector('.watchlist-price').textContent = price.toFixed(2);
        row.querySelector('.watchlist-change').className = `watchlist-change ${changeClass}`;
        row.querySelector('.watchlist-change').textContent = `${changeSign}${change.toFixed(2)}%`;
        row.querySelector('.watchlist-volume').textContent = formatVolume(volume);
    }

function viewStock(code) {
        // Switch to this stock as the main monitoring target
        selectStock(code);
    }

function viewWeeklyBacktest() {
            fetch('/api/weekly_backtest_report')
                .then(r => r.json())
                .then(res => {
                    if(res.status === 'success') {
                        showToast(JSON.stringify(res.data, null, 2));
                    } else {
                        showToast(res.message);
                    }
                });
        }

function viewWeeklyReport() {
            fetch('/api/weekly_model_report')
                .then(r => r.json())
                .then(res => {
                    if(res.status === 'success') {
                        showToast(JSON.stringify(res.data, null, 2));
                    } else {
                        showToast(res.message);
                    }
                });
        }


document.addEventListener('DOMContentLoaded', function() {
    console.log("QuantStock-AI Bundle v1.0.3 Initializing...");
    if (typeof buildStockList === 'function') buildStockList();
    if (typeof initAllCharts === 'function') initAllCharts();
    if (typeof setupEvents === 'function') setupEvents();
    if (typeof refreshAll === 'function') refreshAll();
    if (typeof loadPreviousScreenerStatus === 'function') loadPreviousScreenerStatus(false);
    if (typeof refreshWeeklyPool === 'function') refreshWeeklyPool();
    if (typeof pollTrainStatus === 'function') pollTrainStatus();
    if (typeof loadAccountList === 'function') loadAccountList();
    if (typeof updateCustomStocksUI === 'function') updateCustomStocksUI();
    if (typeof loadSimAccount === 'function') loadSimAccount();
    
    setInterval(() => {
        if (autoRefresh && typeof refreshAll === 'function') refreshAll();
    }, refreshInterval * 1000);
});
