(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var revenueTable = null;
    var allDetails = [];
    var chartTop5 = null;
    var chartOrdMpr = null;
    var chartSubType = null;
    var chartTrend = null;
    var currentMonth = ''; // '' = 전체(누적)

    // 금액 포맷
    function formatPrice(val) {
        if (val === null || val === undefined || val === '') return '-';
        return Number(val).toLocaleString() + '원';
    }

    // 요약 통계 업데이트
    function updateSummary(summary) {
        var memberSet = {};
        summary.forEach(function(r) { memberSet[r.member_code] = true; });
        var totalMembers = Object.keys(memberSet).length;
        var grandTotal = 0, ordTotal = 0, mprTotal = 0;
        summary.forEach(function(r) {
            grandTotal += Number(r.grand_total) || 0;
            ordTotal += Number(r.ord_total) || 0;
            mprTotal += Number(r.mpr_total) || 0;
        });
        $('#stat_members').text(totalMembers.toLocaleString());
        $('#stat_grand_total').text(grandTotal.toLocaleString() + '원');
        $('#stat_ord_total').text(ordTotal.toLocaleString() + '원');
        $('#stat_mpr_total').text(mprTotal.toLocaleString() + '원');

        renderCharts(summary, ordTotal, mprTotal);
    }

    // 차트 렌더링
    function renderCharts(summary, ordTotal, mprTotal) {
        // 기존 차트 파괴
        if (chartTop5) chartTop5.destroy();
        if (chartOrdMpr) chartOrdMpr.destroy();
        if (chartSubType) chartSubType.destroy();

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        // 1. 매출 TOP 5 (가로 막대, ORD/MPR 스택)
        var sorted = summary.slice().sort(function(a, b) { return (Number(b.grand_total) || 0) - (Number(a.grand_total) || 0); });
        var top5 = sorted.slice(0, 5);
        var top5Labels = top5.map(function(r) { return r.company_name; });
        var top5Ord = top5.map(function(r) { return Number(r.ord_total) || 0; });
        var top5Mpr = top5.map(function(r) { return Number(r.mpr_total) || 0; });

        chartTop5 = new Chart(document.getElementById('chartTop5').getContext('2d'), {
            type: 'bar',
            data: {
                labels: top5Labels,
                datasets: [
                    {
                        label: 'ORD',
                        data: top5Ord,
                        backgroundColor: 'rgba(37, 99, 235, 0.8)',
                        borderRadius: 4,
                        barPercentage: 0.6
                    },
                    {
                        label: 'MPR',
                        data: top5Mpr,
                        backgroundColor: 'rgba(245, 158, 11, 0.8)',
                        borderRadius: 4,
                        barPercentage: 0.6
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 12, padding: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원'; }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 }, callback: function(v) { return (v / 10000).toLocaleString() + '만'; } }
                    },
                    y: {
                        stacked: true,
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 11 } }
                    }
                }
            }
        });

        // 2. ORD vs MPR 매출 비율 (도넛)
        chartOrdMpr = new Chart(document.getElementById('chartOrdMpr').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['ORD', 'MPR'],
                datasets: [{
                    data: [ordTotal, mprTotal],
                    backgroundColor: ['rgba(37, 99, 235, 0.85)', 'rgba(245, 158, 11, 0.85)'],
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
                                var total = ordTotal + mprTotal;
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });

        // 3. 가입유형별 매출 (도넛)
        var subTypeMap = {};
        summary.forEach(function(r) {
            var st = r.subscription_type || '미분류';
            if (!subTypeMap[st]) subTypeMap[st] = 0;
            subTypeMap[st] += Number(r.grand_total) || 0;
        });
        var subTypeLabels = Object.keys(subTypeMap);
        var subTypeData = subTypeLabels.map(function(k) { return subTypeMap[k]; });
        var subTypeColors = [
            'rgba(16, 185, 129, 0.85)',
            'rgba(99, 102, 241, 0.85)',
            'rgba(236, 72, 153, 0.85)',
            'rgba(14, 165, 233, 0.85)',
            'rgba(245, 158, 11, 0.85)',
            'rgba(139, 92, 246, 0.85)'
        ];

        chartSubType = new Chart(document.getElementById('chartSubType').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: subTypeLabels,
                datasets: [{
                    data: subTypeData,
                    backgroundColor: subTypeColors.slice(0, subTypeLabels.length),
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
                                var total = subTypeData.reduce(function(a, b) { return a + b; }, 0);
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
    }

    // 상세 모달 표시
    function showDetailModal(memberCode, companyName, summaryRow) {
        var details = allDetails.filter(function(d) { return d.member_code === memberCode; });

        $('#detailSubtitle').text(companyName + ' (' + memberCode + ')');
        $('#modal_ord_total').text(formatPrice(summaryRow.ord_total));
        $('#modal_mpr_total').text(formatPrice(summaryRow.mpr_total));
        $('#modal_grand_total').text(formatPrice(summaryRow.grand_total));

        var html = '';
        details.forEach(function(d) {
            var usageBadge = d.usage === 'ORD'
                ? '<span class="badge badge-phoenix badge-phoenix-primary">ORD</span>'
                : '<span class="badge badge-phoenix badge-phoenix-warning">MPR</span>';
            html += '<tr>' +
                '<td class="text-center py-2">' + (d.datacenter_code || '-') + '</td>' +
                '<td class="text-center py-2">' + usageBadge + '</td>' +
                '<td class="text-center py-2">' + (d.product || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.bandwidth || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.additional_circuit ? 'Y' : 'N') + '</td>' +
                '<td class="text-center py-2">' + (d.phase || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.provider || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.circuit_id || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.fee_description || '-') + '</td>' +
                '<td class="text-center py-2 fw-bold">' + formatPrice(d.fee_price) + '</td>' +
                '</tr>';
        });

        if (!html) {
            html = '<tr><td colspan="10" class="text-center py-3 text-muted">상세 데이터가 없습니다.</td></tr>';
        }

        $('#detailTableBody').html(html);
        new bootstrap.Modal(document.getElementById('detailModal')).show();
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
        revenueTable = $('#revenueTable').DataTable({
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
                    title: '회원사 매출내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회원사 매출내역_' + new Date().toISOString().slice(0,10),
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
                url: '/revenue_summary/get_revenue_summary',
                type: 'GET',
                dataSrc: function(json) {
                    if (json.success) {
                        allDetails = json.details || [];
                        updateSummary(json.summary);
                        return json.summary;
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
                { data: 'ord_count' },
                { data: 'ord_total' },
                { data: 'mpr_count' },
                { data: 'mpr_total' },
                { data: 'total_count' },
                { data: 'grand_total' }
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
                    width: '11%',
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
                    width: '5%',
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
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-success">' + data + '</span>';
                    }
                },
                {
                    targets: 6, // ORD회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 7, // ORD매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #2563eb; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 8, // MPR회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 9, // MPR매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #d97706; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 10, // 총회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle fw-bold',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 11, // 총매출
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #059669; font-weight: 700; font-size: 0.8rem;">' + Number(data).toLocaleString() + '원</span>';
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
                var allData = api.rows({ search: 'applied' }).data();
                if (!allData.length) return;

                var totalOrdCount = 0, totalOrdAmount = 0, totalMprCount = 0, totalMprAmount = 0, totalCount = 0, grandTotal = 0;
                allData.each(function(row) {
                    totalOrdCount += Number(row.ord_count) || 0;
                    totalOrdAmount += Number(row.ord_total) || 0;
                    totalMprCount += Number(row.mpr_count) || 0;
                    totalMprAmount += Number(row.mpr_total) || 0;
                    totalCount += Number(row.total_count) || 0;
                    grandTotal += Number(row.grand_total) || 0;
                });

                // 기존 합계 행 제거 후 재삽입
                $('#revenueTable tbody tr.grand-total-row').remove();
                var grandRow = '<tr class="grand-total-row" style="background: #1e293b !important; pointer-events: none;">' +
                    '<td colspan="6" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                    '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + allData.length + '개 회원사)</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + totalOrdCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + totalOrdAmount.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #fcd34d;">' + totalMprCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #fcd34d;">' + totalMprAmount.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #fff;">' + totalCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #fbbf24; padding-right: 12px !important;">' + grandTotal.toLocaleString() + '원</td>' +
                    '</tr>';
                $('#revenueTable tbody').append(grandRow);
            },
            initComplete: function() {
                // tfoot 개별 열 검색
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

        // 행 클릭 시 상세 모달 (합계 행 제외)
        $('#revenueTable tbody').on('click', 'tr:not(.grand-total-row)', function() {
            var data = revenueTable.row(this).data();
            if (data) {
                showDetailModal(data.member_code, data.company_name, data);
            }
        });

        // 행 호버 스타일
        $('#revenueTable tbody').on('mouseenter', 'tr', function() {
            $(this).css('cursor', 'pointer');
        });
    };

    // 월 필터 초기화 (최근 12개월)
    function initMonthFilter() {
        var sel = document.getElementById('monthFilter');
        var now = new Date();
        for (var i = 0; i < 12; i++) {
            var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            var ym = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            var label = d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월';
            var opt = document.createElement('option');
            opt.value = ym;
            opt.textContent = label;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', onMonthChange);
    }

    // 월 변경 이벤트
    function onMonthChange() {
        var ym = document.getElementById('monthFilter').value;
        currentMonth = ym;
        document.getElementById('btnDownloadPdf').disabled = !ym;

        if (!ym) {
            // 전체(누적) → 기존 API + 추이 차트는 현재 월 기준으로 로드
            revenueTable.ajax.url('/revenue_summary/get_revenue_summary').load();
            loadTrendOnly();
        } else {
            // 월별 → 새 API
            loadMonthlyData(ym);
        }
    }

    // 추이 차트만 로드 (전체 모드에서 현재 월 기준)
    function loadTrendOnly() {
        var now = new Date();
        var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
        $.ajax({
            url: '/revenue_summary/get_revenue_monthly',
            data: { year_month: ym },
            type: 'GET',
            success: function(json) {
                if (json.success && json.trend) {
                    renderTrendChart(json.trend);
                }
            }
        });
    }

    // 월별 데이터 로드
    function loadMonthlyData(yearMonth) {
        var overlay = document.getElementById('pageLoadingOverlay');
        if (overlay) { overlay.style.display = 'flex'; overlay.style.opacity = '1'; }

        $.ajax({
            url: '/revenue_summary/get_revenue_monthly',
            data: { year_month: yearMonth },
            type: 'GET',
            success: function(json) {
                if (json.success) {
                    allDetails = json.details || [];
                    updateSummary(json.summary);
                    renderTrendChart(json.trend);

                    // DataTable 갱신
                    revenueTable.clear();
                    revenueTable.rows.add(json.summary);
                    revenueTable.draw();
                } else {
                    showAlert('월별 데이터 로드 실패: ' + json.error, 'danger');
                }
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.style.display = 'none'; }, 400); }
            },
            error: function(xhr, error) {
                console.error('Monthly AJAX Error:', error);
                showAlert('월별 데이터 로드 중 오류가 발생했습니다.', 'danger');
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.style.display = 'none'; }, 400); }
            }
        });
    }

    // 12개월 추이 차트
    function renderTrendChart(trend) {
        if (chartTrend) chartTrend.destroy();
        if (!trend || !trend.length) return;

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        var labels = trend.map(function(t) { return t.month; });
        var ordData = trend.map(function(t) { return Number(t.ord_total) || 0; });
        var mprData = trend.map(function(t) { return Number(t.mpr_total) || 0; });
        var totalData = trend.map(function(t) { return Number(t.grand_total) || 0; });

        var ctx = document.getElementById('chartTrend').getContext('2d');
        chartTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'ORD 매출',
                        data: ordData,
                        borderColor: 'rgba(37, 99, 235, 0.9)',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2
                    },
                    {
                        label: 'MPR 매출',
                        data: mprData,
                        borderColor: 'rgba(245, 158, 11, 0.9)',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2
                    },
                    {
                        label: '합계',
                        data: totalData,
                        borderColor: 'rgba(16, 185, 129, 0.9)',
                        backgroundColor: 'transparent',
                        borderDash: [6, 3],
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        borderWidth: 2
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
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 14, padding: 15 }
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
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 } }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 10 },
                            callback: function(v) { return (v / 10000).toLocaleString() + '만'; }
                        }
                    }
                }
            }
        });
    }

    // PDF 다운로드
    window.downloadPdf = function() {
        if (!currentMonth) {
            showAlert('PDF 다운로드는 월을 선택한 후 가능합니다.', 'warning');
            return;
        }
        showAlert(currentMonth + ' 보고서 PDF를 생성 중...', 'info');
        window.open('/revenue_summary/download_revenue_pdf?year_month=' + currentMonth, '_blank');
    };

    // 새로고침
    window.refreshTable = function() {
        if (revenueTable) {
            var ym = document.getElementById('monthFilter').value;
            if (ym) {
                loadMonthlyData(ym);
            } else {
                revenueTable.ajax.url('/revenue_summary/get_revenue_summary').load();
            }
            showAlert('데이터를 새로고침했습니다.', 'success');
        }
    };

    // 초기화
    document.addEventListener('DOMContentLoaded', function() {
        initMonthFilter();
        initTable();
        // 전체 모드에서도 추이 차트 표시
        loadTrendOnly();
    });

}));
