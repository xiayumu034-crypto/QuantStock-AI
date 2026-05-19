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

    function updateChartData(chart, labels, datasets) {
        chart.data.labels = labels;
        datasets.forEach((ds, i) => { chart.data.datasets[i].data = ds; });
        chart.update('none');
    }

    // ========== 核心刷新 ==========
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

