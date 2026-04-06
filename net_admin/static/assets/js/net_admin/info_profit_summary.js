(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

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

    // 요약 통계 업데이트
    function updateSummary(data) {
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
        $('#stat_revenue').text(totalRevenue.toLocaleString() + '원');
        $('#stat_purchase').text(totalPurchase.toLocaleString() + '원');
        $('#stat_profit').text(totalProfit.toLocaleString() + '원');

        renderCharts(data, totalRevenue, totalPurchase);
    }

    // 월별 추이 차트 로드
    function loadMonthlyChart() {
        $.getJSON('/info_profit_summary/get_info_profit_monthly', function(json) {
            if (!json.success || !json.data) return;
            renderMonthlyChart(json.data);
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
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '매출',
                        data: revenues,
                        backgroundColor: 'rgba(59, 130, 246, 0.15)',
                        borderColor: 'rgba(59, 130, 246, 0.9)',
                        borderWidth: 1.5,
                        borderRadius: 4,
                        yAxisID: 'y',
                        order: 2
                    },
                    {
                        label: '매입',
                        data: purchases,
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        borderColor: 'rgba(239, 68, 68, 0.9)',
                        borderWidth: 1.5,
                        borderRadius: 4,
                        yAxisID: 'y',
                        order: 3
                    },
                    {
                        label: '이익',
                        type: 'line',
                        data: profits,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2.5,
                        pointRadius: 4,
                        pointBackgroundColor: '#f59e0b',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y1',
                        order: 1
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
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 12, padding: 16, usePointStyle: true }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 10 } }
                    },
                    y: {
                        position: 'left',
                        title: { display: true, text: '매출 / 매입', color: textColor, font: { size: 10 } },
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 10 },
                            callback: function(v) {
                                if (v >= 100000000) return (v / 100000000).toFixed(0) + '억';
                                if (v >= 10000) return (v / 10000).toLocaleString() + '만';
                                return v.toLocaleString();
                            }
                        }
                    },
                    y1: {
                        position: 'right',
                        title: { display: true, text: '이익', color: '#f59e0b', font: { size: 10, weight: 'bold' } },
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#f59e0b',
                            font: { size: 10 },
                            callback: function(v) {
                                if (v >= 100000000) return (v / 100000000).toFixed(1) + '억';
                                if (v >= 10000) return (v / 10000).toLocaleString() + '만';
                                return v.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    // 차트 렌더링
    function renderCharts(data, totalRevenue, totalPurchase) {
        if (chartTop10) chartTop10.destroy();
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

        chartTop10 = new Chart(document.getElementById('chartTop5').getContext('2d'), {
            type: 'bar',
            data: {
                labels: top10Labels,
                datasets: [
                    {
                        label: '매출',
                        data: top10Revenue,
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderRadius: 3,
                        barPercentage: 0.7,
                        categoryPercentage: 0.8
                    },
                    {
                        label: '매입',
                        data: top10Purchase,
                        backgroundColor: 'rgba(239, 68, 68, 0.7)',
                        borderRadius: 3,
                        barPercentage: 0.7,
                        categoryPercentage: 0.8
                    },
                    {
                        label: '이익',
                        data: top10Profit,
                        backgroundColor: 'rgba(245, 158, 11, 0.85)',
                        borderRadius: 3,
                        barPercentage: 0.7,
                        categoryPercentage: 0.8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { size: 10 }, boxWidth: 10, padding: 8 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원'; }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: textColor,
                            font: { size: 8 },
                            maxRotation: 45,
                            minRotation: 25
                        }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 9 },
                            callback: function(v) {
                                if (v >= 100000000) return (v / 100000000).toFixed(1) + '억';
                                if (v >= 10000) return (v / 10000).toLocaleString() + '만';
                                return v.toLocaleString();
                            }
                        }
                    }
                }
            }
        });

        // 2. 매출 vs 매입 비율 (도넛)
        chartRevPur = new Chart(document.getElementById('chartRevPur').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['매출', '매입'],
                datasets: [{
                    data: [totalRevenue, totalPurchase],
                    backgroundColor: ['rgba(59, 130, 246, 0.85)', 'rgba(239, 68, 68, 0.85)'],
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, padding: 12, boxWidth: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                var total = totalRevenue + totalPurchase;
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });

        // 3. 이익률 분포 (도넛)
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
        var distColors = [
            'rgba(16, 185, 129, 0.85)',
            'rgba(99, 102, 241, 0.85)',
            'rgba(245, 158, 11, 0.85)',
            'rgba(239, 68, 68, 0.85)'
        ];

        chartProfitDist = new Chart(document.getElementById('chartProfitDist').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: distLabels,
                datasets: [{
                    data: distData,
                    backgroundColor: distColors,
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, padding: 12, boxWidth: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.label + ': ' + ctx.raw + '개사';
                            }
                        }
                    }
                }
            }
        });
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
                    title: '정보이용사 이익내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '정보이용사 이익내역_' + new Date().toISOString().slice(0,10),
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
                url: '/info_profit_summary/get_info_profit_summary',
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
                { data: 'mkd_count' },
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
                    targets: 6, // MKD회선수
                    width: '8%',
                    className: 'text-center py-2 align-middle fw-bold',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 7, // MKD매출
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #2563eb; font-weight: 700;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 8, // 총매입
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #dc2626; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 9, // 이익
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    createdCell: function(td, cellData) {
                        var val = Number(cellData) || 0;
                        td.style.background = val >= 0 ? 'rgba(5, 150, 105, 0.08)' : 'rgba(220, 38, 38, 0.08)';
                    },
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        var val = Number(data);
                        var color = val >= 0 ? '#059669' : '#dc2626';
                        return '<span style="color: ' + color + '; font-weight: 700; font-size: 0.85rem;">' + val.toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 10, // 이익률
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

                var tMkdCount = 0, tRevenue = 0, tPurchase = 0, tProfit = 0;
                data.each(function(row) {
                    tMkdCount += Number(row.mkd_count) || 0;
                    tRevenue += Number(row.revenue_total) || 0;
                    tPurchase += Number(row.purchase_total) || 0;
                    tProfit += Number(row.profit) || 0;
                });
                var tRate = tRevenue > 0 ? ((tProfit / tRevenue) * 100).toFixed(1) : '0.0';

                $('#profitTable tbody tr.grand-total-row').remove();
                var grandRow = '<tr class="grand-total-row" style="background: #1e293b !important; pointer-events: none;">' +
                    '<td colspan="6" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                    '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + data.length + '건)</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + tMkdCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #6ee7b7;">' + tRevenue.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #fca5a5;">' + tPurchase.toLocaleString() + '원</td>' +
                    '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #fbbf24;">' + tProfit.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #fbbf24;">' + tRate + '%</td>' +
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
        showAlert('정보이용사 이익내역 보고서는 준비 중입니다.', 'info');
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
