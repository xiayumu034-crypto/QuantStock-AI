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

    let pipePollInterval = null;
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

        function refreshWeeklyPool() {
            const tbody = document.getElementById('weeklySwingTable');
            tbody.innerHTML = '<tr><td colspan="10" class="text-center opacity-50 py-3">加载中...</td></tr>';
            fetch(`/api/weekly_predict_all?t=${new Date().getTime()}`)
                .then(r => r.json())
                .then(res => {
                    if(res.status === 'success') {
                        let html = '';
                        // Convert to array and sort by win_prob descending
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
    
