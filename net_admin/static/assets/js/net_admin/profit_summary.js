(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';
    function _isDark() { return document.documentElement.getAttribute('data-bs-theme') === 'dark'; }
    function T(l, d) { return _isDark() ? d : l; }

    var profitTable = null;
    var chartTop10 = null;
    var chartRevPur = null;
    var chartProfitDist = null;
    var chartMonthly = null;

    // 금액 포맷
    function formatPrice(val) {
        if (val === null || val === undefined || val === '') return '-';
        return Number(val).toLocaleString() + '원';
    }

    var _savedProfitTrend = null;

    function fmtCompact(v) {
        if (v === 0) return '0';
        var s = v >= 0 ? '+' : '';
        if (Math.abs(v) >= 100000000) return s + (v / 100000000).toFixed(1) + '억';
        if (Math.abs(v) >= 10000) return s + (v / 10000).toFixed(0) + '만';
        return s + v.toLocaleString();
    }

    // 요약 통계 업데이트
    function updateSummary(data) {
        // trend가 아직 로드 안 됐으면 대기
        if (!_savedProfitTrend) {
            _pendingSummaryData = data;
        }

        var memberSet = {};
        data.forEach(function(r) { memberSet[r.member_code] = true; });
        var totalMembers = Object.keys(memberSet).length;
        var totalRevenue = 0, totalPurchase = 0, totalProfit = 0;
        data.forEach(function(r) {
            totalRevenue += Number(r.revenue_total) || 0;
            totalPurchase += Number(r.purchase_total) || 0;
            totalProfit += Number(r.profit) || 0;
        });
        $('#stat_members').text(totalMembers.toLocaleString());

        // 작년 12월 대비 증감
        var baseLine = null;
        if (_savedProfitTrend && _savedProfitTrend.length > 0) {
            var lastYear = String(Number(_savedProfitTrend[_savedProfitTrend.length - 1].month.substring(0, 4)) - 1);
            for (var i = 0; i < _savedProfitTrend.length; i++) {
                if (_savedProfitTrend[i].month === lastYear + '-12') {
                    baseLine = _savedProfitTrend[i];
                    break;
                }
            }
        }

        if (baseLine) {
            var bRev = Number(baseLine.revenue_total) || 0;
            var bPur = Number(baseLine.purchase_total) || 0;
            var bPf = Number(baseLine.profit) || 0;
            var rDiff = totalRevenue - bRev, pDiff = totalPurchase - bPur, pfDiff = totalProfit - bPf;
            var rPct = bRev > 0 ? ((rDiff / bRev) * 100).toFixed(1) : '0.0';
            var pPct = bPur > 0 ? ((pDiff / bPur) * 100).toFixed(1) : '0.0';
            var pfPct = bPf > 0 ? ((pfDiff / Math.abs(bPf)) * 100).toFixed(1) : '0.0';

            var dc = function(v) { return v >= 0 ? '#dc2626' : '#2563eb'; };
            $('#stat_revenue').html(totalRevenue.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + dc(rDiff) + ';font-weight:600;">(' + fmtCompact(rDiff) + ', ' + (rDiff >= 0 ? '+' : '') + rPct + '%)</span>');
            $('#stat_purchase').html(totalPurchase.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + dc(pDiff) + ';font-weight:600;">(' + fmtCompact(pDiff) + ', ' + (pDiff >= 0 ? '+' : '') + pPct + '%)</span>');
            $('#stat_profit').html(totalProfit.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + dc(pfDiff) + ';font-weight:600;">(' + fmtCompact(pfDiff) + ', ' + (pfDiff >= 0 ? '+' : '') + pfPct + '%)</span>');
        } else {
            $('#stat_revenue').text(totalRevenue.toLocaleString() + '원');
            $('#stat_purchase').text(totalPurchase.toLocaleString() + '원');
            $('#stat_profit').text(totalProfit.toLocaleString() + '원');
        }

        renderCharts(data, totalRevenue, totalPurchase);
    }

    var _pendingSummaryData = null;

    // 월별 추이 차트 로드
    function loadMonthlyChart() {
        $.getJSON('/profit_summary/get_profit_monthly', function(json) {
            if (!json.success || !json.data) return;
            _savedProfitTrend = json.data;
            renderMonthlyChart(json.data);
            // trend 로드 후 대기 중인 summary가 있으면 재실행
            if (_pendingSummaryData) {
                updateSummary(_pendingSummaryData);
                _pendingSummaryData = null;
            }
        });
    }

    // 월별 추이 차트 렌더링
    function renderMonthlyChart(data) {
        if (chartMonthly) chartMonthly.destroy();

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        var labels = data.map(function(r) {
            var parts = r.month.split('-');
            return parts[0].slice(2) + '.' + parts[1];
        });
        var revenues = data.map(function(r) { return r.revenue_total; });
        var purchases = data.map(function(r) { return r.purchase_total; });
        var profits = data.map(function(r) { return r.profit; });

        chartMonthly = new Chart(document.getElementById('chartMonthly').getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '매출',
                        data: revenues,
                        borderColor: 'rgba(30, 41, 59, 0.7)',
                        backgroundColor: 'rgba(30, 41, 59, 0.05)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 1.2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: '매입',
                        data: purchases,
                        borderColor: 'rgba(99, 102, 241, 0.7)',
                        backgroundColor: 'rgba(99, 102, 241, 0.05)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 1.2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: '이익',
                        data: profits,
                        borderColor: 'rgba(16, 185, 129, 0.9)',
                        backgroundColor: 'transparent',
                        borderDash: [6, 3],
                        tension: 0.4,
                        borderWidth: 1.5,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 8, boxHeight: 8, padding: 16, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.9)',
                        titleFont: { size: 11 },
                        bodyFont: { size: 11 },
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(ctx) {
                                return ' ' + ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: { color: '#94a3b8', font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: false,
                        title: { display: false },
                        grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false },
                        border: { display: false },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 10 },
                            padding: 8,
                            callback: function(v) {
                                if (v >= 100000000) return (v / 100000000).toFixed(0) + '억';
                                if (v >= 10000) return (v / 10000).toLocaleString() + '만';
                                return v.toLocaleString();
                            }
                        }
                    }
                }
            }
        });

        // 월별 이익 추이 테이블
        var ptbody = document.getElementById('profitTrendBody');
        if (ptbody) {
            function fmtDiffVal(v) {
                if (v === 0) return '';
                var s = v >= 0 ? '+' : '';
                if (Math.abs(v) >= 100000000) return s + (v / 100000000).toFixed(1) + '억';
                if (Math.abs(v) >= 10000) return s + (v / 10000).toFixed(0) + '만';
                return s + v.toLocaleString();
            }
            var rev = data.slice().reverse();
            var phtml = '';
            rev.forEach(function(d, i) {
                var rv = Number(d.revenue_total) || 0;
                var pu = Number(d.purchase_total) || 0;
                var pf = Number(d.profit) || 0;
                var hasPrev = i < rev.length - 1;
                var prevPf = hasPrev ? (Number(rev[i + 1].profit) || 0) : 0;
                var pfDiff = hasPrev ? pf - prevPf : 0;
                var pfPct = hasPrev && prevPf !== 0 ? ((pfDiff / Math.abs(prevPf)) * 100).toFixed(1) : '0.0';

                var rvSub = '', puSub = '', pfSub = '';
                if (hasPrev) {
                    var prevRv = Number(rev[i + 1].revenue_total) || 0;
                    var prevPu = Number(rev[i + 1].purchase_total) || 0;
                    var rvDiff = rv - prevRv, puDiff = pu - prevPu;
                    if (rvDiff !== 0) rvSub = ' <span style="font-size:0.6rem;color:' + (rvDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiffVal(rvDiff) + ')</span>';
                    if (puDiff !== 0) puSub = ' <span style="font-size:0.6rem;color:' + (puDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiffVal(puDiff) + ')</span>';
                    if (pfDiff !== 0) pfSub = ' <span style="font-size:0.6rem;color:' + (pfDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiffVal(pfDiff) + ')</span>';
                }

                var diffStr = '';
                if (hasPrev && pfDiff !== 0) {
                    var arrow = pfDiff >= 0 ? '<span style="color:#dc2626;">▲</span>' : '<span style="color:#2563eb;">▼</span>';
                    diffStr = arrow + ' ' + (pfDiff >= 0 ? '+' : '') + pfPct + '%';
                }

                phtml += '<tr style="border-bottom:1px solid #f5f5f5;">' +
                    '<td class="text-center py-2" style="font-weight:600; color:' + T('#475569','#94a3b8') + ';">' + d.month + '</td>' +
                    '<td class="py-2" style="color:' + T('#1e293b','#e2e8f0') + '; font-weight:600;">' + rv.toLocaleString() + '원' + rvSub + '</td>' +
                    '<td class="py-2" style="color:' + T('#1e293b','#e2e8f0') + '; font-weight:600;">' + pu.toLocaleString() + '원' + puSub + '</td>' +
                    '<td class="py-2" style="color:#059669; font-weight:700;">' + pf.toLocaleString() + '원' + pfSub + '</td>' +
                    '<td class="text-center py-2" style="font-size:0.78rem; font-weight:600;">' + diffStr + '</td>' +
                    '</tr>';
            });
            ptbody.innerHTML = phtml;
        }
    }

    // 차트 렌더링
    function renderCharts(data, totalRevenue, totalPurchase) {
        // chartTop10은 리스트 방식으로 변경됨
        if (chartRevPur) chartRevPur.destroy();
        if (chartProfitDist) chartProfitDist.destroy();

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        // 회원사별 이익 합산
        var profitByMember = {};
        data.forEach(function(r) {
            var key = r.member_code;
            if (!profitByMember[key]) {
                profitByMember[key] = { company_name: r.company_name, profit: 0, revenue: 0, purchase: 0 };
            }
            profitByMember[key].profit += Number(r.profit) || 0;
            profitByMember[key].revenue += Number(r.revenue_total) || 0;
            profitByMember[key].purchase += Number(r.purchase_total) || 0;
        });

        // 1. 이익 TOP 10 (세로 막대)
        var memberList = Object.keys(profitByMember).map(function(k) { return profitByMember[k]; });
        memberList.sort(function(a, b) { return b.profit - a.profit; });
        var top10 = memberList.slice(0, 10);
        var top10Labels = top10.map(function(r) { return r.company_name; });
        var top10Revenue = top10.map(function(r) { return r.revenue; });
        var top10Purchase = top10.map(function(r) { return r.purchase; });
        var top10Profit = top10.map(function(r) { return r.profit; });

        // 이익 TOP 10 리스트
        var top10El = document.getElementById('chartTop5');
        if (top10El) {
            var maxProfit = top10.length > 0 ? top10[0].profit : 1;
            var listHtml = '';
            top10.forEach(function(m, i) {
                var barW = maxProfit > 0 ? Math.round(m.profit / maxProfit * 100) : 0;
                var profitStr = Number(m.profit).toLocaleString();
                listHtml += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">' +
                    '<span style="min-width:18px;font-size:0.75rem;font-weight:600;color:#94a3b8;text-align:right;">' + (i + 1) + '</span>' +
                    '<span style="min-width:72px;font-size:0.78rem;font-weight:600;color:' + T('#1e293b','#e2e8f0') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + m.company_name + '</span>' +
                    '<div style="flex:1;height:12px;background:rgba(0,0,0,0.03);border-radius:6px;overflow:hidden;">' +
                    '<div style="height:100%;width:' + barW + '%;background:rgba(239,68,68,0.45);border-radius:6px;transition:width 0.4s;"></div>' +
                    '</div>' +
                    '<span style="min-width:85px;text-align:right;font-size:0.78rem;font-weight:700;color:#dc2626;">' + profitStr + '원</span>' +
                    '</div>';
            });
            top10El.innerHTML = listHtml;
            top10El.style.height = 'auto';
        }

        // 2. 매출 vs 매입 비율 (도넛 + 중앙 텍스트)
        var revPurTotal = totalRevenue + totalPurchase;
        var revPct = revPurTotal > 0 ? ((totalRevenue / revPurTotal) * 100).toFixed(1) : '0';
        var centerTextPlugin = {
            id: 'centerText',
            afterDraw: function(chart) {
                var meta = chart.getDatasetMeta(0);
                if (!meta || !meta.data || !meta.data[0]) return;
                var ctx = chart.ctx;
                var centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
                var centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.font = '700 1.3rem -apple-system, sans-serif';
                ctx.fillStyle = isDark ? '#e2e8f0' : '#1e293b';
                ctx.fillText(chart._centerValue || '', centerX, centerY - 8);
                ctx.font = '500 0.68rem -apple-system, sans-serif';
                ctx.fillStyle = '#94a3b8';
                ctx.fillText(chart._centerLabel || '', centerX, centerY + 14);
                ctx.restore();
            }
        };

        chartRevPur = new Chart(document.getElementById('chartRevPur').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['매출', '매입'],
                datasets: [{
                    data: [totalRevenue, totalPurchase],
                    backgroundColor: ['rgba(30, 41, 59, 0.6)', 'rgba(99, 102, 241, 0.5)'],
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff',
                    hoverOffset: 8,
                    spacing: 3
                }]
            },
            plugins: [centerTextPlugin],
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                animation: { animateRotate: true, duration: 800 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, padding: 14, boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.9)',
                        cornerRadius: 8,
                        padding: 10,
                        callbacks: {
                            label: function(ctx) {
                                var total = totalRevenue + totalPurchase;
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ' ' + ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
        chartRevPur._centerValue = revPct + '%';
        chartRevPur._centerLabel = '매출 비율';

        // 3. 이익률 분포 (도넛 + 중앙 텍스트)
        var distMap = { '90% 이상': 0, '70~90%': 0, '50~70%': 0, '50% 미만': 0 };
        memberList.forEach(function(m) {
            var rate = m.revenue > 0 ? (m.profit / m.revenue) * 100 : 0;
            if (rate >= 90) distMap['90% 이상']++;
            else if (rate >= 70) distMap['70~90%']++;
            else if (rate >= 50) distMap['50~70%']++;
            else distMap['50% 미만']++;
        });
        var distLabels = Object.keys(distMap);
        var distData = distLabels.map(function(k) { return distMap[k]; });
        var totalMembers = distData.reduce(function(a, b) { return a + b; }, 0);

        chartProfitDist = new Chart(document.getElementById('chartProfitDist').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: distLabels,
                datasets: [{
                    data: distData,
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.6)',
                        'rgba(99, 102, 241, 0.5)',
                        'rgba(245, 158, 11, 0.55)',
                        'rgba(239, 68, 68, 0.45)'
                    ],
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff',
                    hoverOffset: 8,
                    spacing: 3
                }]
            },
            plugins: [centerTextPlugin],
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                animation: { animateRotate: true, duration: 800 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 10 }, padding: 10, boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.9)',
                        cornerRadius: 8,
                        padding: 10,
                        callbacks: {
                            label: function(ctx) {
                                var pct = totalMembers > 0 ? ((ctx.raw / totalMembers) * 100).toFixed(1) : 0;
                                return ' ' + ctx.label + ': ' + ctx.raw + '개사 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
        chartProfitDist._centerValue = totalMembers + '개사';
        chartProfitDist._centerLabel = '전체 회원사';
    }

    // 알림 표시
    function showAlert(message, type) {
        type = type || 'info';
        var alertHtml = '<div class="alert alert-' + type + ' alert-dismissible fade show position-fixed" role="alert" ' +
            'style="top: 80px; right: 20px; z-index: 9999; min-width: 300px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); border-radius: 10px;">' +
            message +
            '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
        $('body').append(alertHtml);
        setTimeout(function() { $('.alert').fadeOut(400, function() { $(this).remove(); }); }, 3000);
    }

    var initTable = function() {
        profitTable = $('#profitTable').DataTable({
            responsive: true,
            paging: true,
            pageLength: 100,
            searching: true,
            ordering: true,
            order: [],
            language: {
                search: "검색:",
                lengthMenu: "페이지당 _MENU_ 개씩 표시",
                info: "전체 _TOTAL_개 중 _START_-_END_개 표시",
                infoEmpty: "데이터가 없습니다",
                infoFiltered: "(전체 _MAX_개 중 필터링됨)",
                paginate: { first: "처음", last: "마지막", next: "다음", previous: "이전" },
                emptyTable: "검색 결과가 없습니다",
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: " "
            },
            dom: '<"row align-items-center"<"col-sm-12 col-md-3"l><"col-sm-12 col-md-9 d-flex justify-content-end align-items-center gap-2"fB>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '회원사 이익내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회원사 이익내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                }
            ],
            ajax: {
                url: '/profit_summary/get_profit_summary',
                type: 'GET',
                dataSrc: function(json) {
                    if (json.success) {
                        updateSummary(json.data);
                        return json.data;
                    } else {
                        showAlert('데이터 로드 실패: ' + json.error, 'danger');
                        return [];
                    }
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'member_number' },
                { data: 'member_code' },
                { data: 'company_name' },
                { data: 'subscription_type' },
                { data: 'is_pb' },
                { data: 'phase' },
                { data: 'ord_total' },
                { data: 'mpr_total' },
                { data: 'revenue_total' },
                { data: 'purchase_total' },
                { data: 'profit' },
                { data: 'profit_rate' }
            ],
            columnDefs: [
                {
                    targets: 0, // 회원번호
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 회원사코드
                    width: '7%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회사명
                    width: '10%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 3, // 가입유형
                    width: '7%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // PB
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === true || data === 'true' || data === 't') {
                            return '<span class="badge badge-phoenix badge-phoenix-danger">PB</span>';
                        }
                        return '-';
                    }
                },
                {
                    targets: 5, // Phase
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-success">' + data + '</span>';
                    }
                },
                {
                    targets: 6, // ORD매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #1f2937; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 7, // MPR매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #1f2937; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 8, // 총매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    createdCell: function(td) {
                        td.style.background = 'rgba(30, 41, 59, 0.04)';
                    },
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #1e293b; font-weight: 700;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 9, // 총매입
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    createdCell: function(td) {
                        td.style.background = 'rgba(99, 102, 241, 0.05)';
                    },
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #6366f1; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 10, // 이익
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    createdCell: function(td, cellData) {
                        var val = Number(cellData) || 0;
                        td.style.background = val >= 0 ? 'rgba(239, 68, 68, 0.05)' : 'rgba(148, 163, 184, 0.08)';
                    },
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        var val = Number(data);
                        var color = val >= 0 ? '#dc2626' : '#94a3b8';
                        return '<span style="color: ' + color + '; font-weight: 700; font-size: 0.85rem;">' + val.toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 11, // 이익률
                    width: '7%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === null || data === undefined) return '-';
                        var val = Number(data);
                        var color, bg;
                        if (val >= 70) { color = '#059669'; bg = 'rgba(16,185,129,0.1)'; }
                        else if (val >= 50) { color = '#d97706'; bg = 'rgba(245,158,11,0.1)'; }
                        else { color = '#dc2626'; bg = 'rgba(239,68,68,0.1)'; }
                        return '<span style="color: ' + color + '; font-weight: 700; background: ' + bg + '; padding: 2px 8px; border-radius: 6px;">' + val.toFixed(1) + '%</span>';
                    }
                }
            ],
            drawCallback: function(settings) {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.style.display = 'none'; }, 400);
                }

                var api = this.api();
                var data = api.rows({ page: 'current' }).data();
                if (!data.length) return;

                var tRevenue = 0, tPurchase = 0, tProfit = 0, tOrd = 0, tMpr = 0;
                data.each(function(row) {
                    tOrd += Number(row.ord_total) || 0;
                    tMpr += Number(row.mpr_total) || 0;
                    tRevenue += Number(row.revenue_total) || 0;
                    tPurchase += Number(row.purchase_total) || 0;
                    tProfit += Number(row.profit) || 0;
                });
                var tRate = tRevenue > 0 ? ((tProfit / tRevenue) * 100).toFixed(1) : '0.0';

                $('#profitTable tbody tr.grand-total-row').remove();
                var grandRow = '<tr class="grand-total-row" style="background: #1e293b !important; pointer-events: none;">' +
                    '<td colspan="6" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                    '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + data.length + '건)</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #cbd5e1;">' + tOrd.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #cbd5e1;">' + tMpr.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 800; color: #f1f5f9;">' + tRevenue.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #a5b4fc;">' + tPurchase.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #fca5a5;">' + tProfit.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #fca5a5;">' + tRate + '%</td>' +
                    '</tr>';
                $('#profitTable tbody').append(grandRow);
            },
            initComplete: function() {
                this.api().columns().every(function() {
                    var column = this;
                    var header = $(column.footer());
                    var title = header.text().trim();
                    header.html('<input type="text" class="form-control form-control-sm text-center" placeholder="' + title + '" style="font-size:0.65rem; min-width:50px;" />');
                    $('input', header).on('keyup change', function() {
                        if (column.search() !== this.value) {
                            column.search(this.value).draw();
                        }
                    }).on('click', function(e) {
                        e.stopPropagation();
                    });
                });
            }
        });
    };

    // PDF 다운로드
    window.downloadPdf = function() {
        showAlert('이익내역 보고서를 생성 중...', 'info');
        window.open('/profit_summary/download_profit_pdf', '_blank');
    };

    // 새로고침
    window.refreshTable = function() {
        if (profitTable) {
            profitTable.ajax.reload();
            loadMonthlyChart();
            showAlert('데이터를 새로고침했습니다.', 'success');
        }
    };

    // 초기화
    document.addEventListener('DOMContentLoaded', function() {
        initTable();
        loadMonthlyChart();
    });

}));
