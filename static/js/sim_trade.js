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

    loadSimAccount(); // 刷新账户
            } else {
                showToast('执行失败：' + d.message);
            }
        })
        .catch(e => {
            btn.disabled = false;
            btn.innerText = oldText;
            showToast('请求异常：' + e.message);
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

    
function toggleAutoTrade(checked) {
        simAutoTrade = checked;
        document.getElementById('autoTradeLabel').innerText = checked ? '已开启' : '已暂停';
        fetch(`/api/sim/toggle_auto?account_id=${currentAccountId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auto_trade: checked })
        });
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

    let allTradeLogs = [];
    
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

    loadSimAccount();
    setInterval(loadSimAccount, 3000); // 3秒刷新一次模拟账户
    setInterval(() => {
        if (simAutoTrade) {
            fetch(`/api/sim/step?account_id=${currentAccountId}`, { method: 'POST' }).then(() => loadSimAccount());
        }
    }, 60000); // 如果开启了自动，每分钟触发一次交易判定


    // ========== 新闻 ==========
    let newsMode = 'all'; // 默认为全部，防止筛选逻辑导致空白
    let allNewsData = [];
    
