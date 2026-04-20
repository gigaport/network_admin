(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var purchaseTable = null;
    var costCodes = [];
    var memberCodes = [];
    var chartProvider = null;
    var chartDC = null;

    function formatPrice(val) {
        if (!val && val !== 0) return '-';
        return Number(val).toLocaleString() + '원';
    }

    function updateSummary(data) {
        var ktCount = 0, lguCount = 0, ktAmount = 0, lguAmount = 0, totalAmount = 0;
        var memberSet = {};
        var memberAmounts = {};
        var dcAmounts = {};

        data.forEach(function(item) {
            var price = item.cost_price || 0;
            totalAmount += price;

            // 회원사 집계
            var mc = item.member_code || '?';
            var cn = item.company_name || mc;
            memberSet[mc] = cn;
            if (!memberAmounts[mc]) memberAmounts[mc] = { name: cn, count: 0, amount: 0 };
            memberAmounts[mc].count++;
            memberAmounts[mc].amount += price;

            // 데이터센터 집계
            var dc = item.datacenter_code || '미분류';
            if (!dcAmounts[dc]) dcAmounts[dc] = { count: 0, amount: 0 };
            dcAmounts[dc].count++;
            dcAmounts[dc].amount += price;

            // 통신사 집계
            if (item.provider === 'KTC') {
                ktCount++;
                ktAmount += price;
            } else if (item.provider === 'LGU') {
                lguCount++;
                lguAmount += price;
            }
        });

        var memberCount = Object.keys(memberSet).length;

        // 카드 업데이트
        $('#stat_total').text(data.length + '건');
        $('#stat_total_amount').text(memberCount + '개 회원사');
        $('#stat_grand_total').text(totalAmount.toLocaleString() + '원');
        $('#stat_kt').text(ktCount + '건');
        $('#stat_kt_amount').text('매입 ' + formatPrice(ktAmount));
        $('#stat_lgu').text(lguCount + '건');
        $('#stat_lgu_amount').text('매입 ' + formatPrice(lguAmount));

        // 차트 렌더링
        renderCharts(memberAmounts, ktAmount, lguAmount, dcAmounts);

        // 월별 변경내역 렌더링
        renderPurchaseChangeTrend(data);
    }

    var _purchaseChangeData = {};

    function renderPurchaseChangeTrend(data) {
        var tbody = document.getElementById('purchaseChangeTrendBody');
        if (!tbody) return;

        var now = new Date();
        var months = [];
        for (var i = 11; i >= 0; i--) {
            var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            var ym = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            months.push(ym);
        }

        // 월별 추가/종료 건수+금액+상세 집계
        var added = {}, ended = {}, addedAmt = {}, endedAmt = {};
        var addedItems = {}, endedItems = {};
        months.forEach(function(m) { added[m] = 0; ended[m] = 0; addedAmt[m] = 0; endedAmt[m] = 0; addedItems[m] = []; endedItems[m] = []; });

        data.forEach(function(item) {
            var price = item.cost_price || 0;
            var info = {
                company_name: item.company_name || item.member_code || '-',
                member_code: item.member_code || '-',
                provider: item.provider || '-',
                datacenter_code: item.datacenter_code || '-',
                cost_standart: item.cost_standart || '-',
                cost_price: price,
                service_id: item.service_id || '-',
                billing_start_date: item.billing_start_date || '-',
                contract_end_date: item.contract_end_date || '-'
            };
            if (item.billing_start_date) {
                var startYm = item.billing_start_date.substring(0, 7);
                if (added.hasOwnProperty(startYm)) {
                    added[startYm]++;
                    addedAmt[startYm] += price;
                    addedItems[startYm].push(info);
                }
            }
            if (item.contract_end_date) {
                var endYm = item.contract_end_date.substring(0, 7);
                if (ended.hasOwnProperty(endYm)) {
                    ended[endYm]++;
                    endedAmt[endYm] += price;
                    endedItems[endYm].push(info);
                }
            }
        });

        _purchaseChangeData = { added: addedItems, ended: endedItems };

        function fmtAmt(v) {
            if (v === 0) return '';
            if (v >= 10000) return (v / 10000).toFixed(0) + '만';
            return v.toLocaleString();
        }

        var html = '';
        months.slice().reverse().forEach(function(m) {
            var a = added[m] || 0;
            var e = ended[m] || 0;
            var aAmt = addedAmt[m] || 0;
            var eAmt = endedAmt[m] || 0;
            var diff = a - e;
            var diffAmt = aAmt - eAmt;
            var diffColor = diff > 0 ? '#059669' : (diff < 0 ? '#dc2626' : '#94a3b8');
            var diffStr = diff > 0 ? '+' + diff : (diff === 0 ? '-' : String(diff));
            var label = m.substring(2).replace('-', '.');
            var hasData = a > 0 || e > 0;
            var cursor = hasData ? 'cursor:pointer;' : '';
            var onclick = hasData ? ' onclick="showPurchaseChangeDetail(\'' + m + '\')"' : '';

            html += '<tr style="border-bottom:1px solid #f5f5f5;' + cursor + '"' + onclick + '>' +
                '<td class="text-center py-2" style="font-weight:600; color:var(--phoenix-tertiary-color, #475569);">' + label + '</td>' +
                '<td class="text-center py-2">' +
                    (a > 0 ? '<span style="color:#059669;font-weight:600;">+' + a + '</span> <span style="font-size:0.6rem;color:#94a3b8;">' + fmtAmt(aAmt) + '</span>' : '<span style="color:#94a3b8;">-</span>') +
                '</td>' +
                '<td class="text-center py-2">' +
                    (e > 0 ? '<span style="color:#dc2626;font-weight:600;">-' + e + '</span> <span style="font-size:0.6rem;color:#94a3b8;">' + fmtAmt(eAmt) + '</span>' : '<span style="color:#94a3b8;">-</span>') +
                '</td>' +
                '<td class="text-center py-2" style="color:' + diffColor + '; font-weight:700;">' + diffStr +
                    (diffAmt !== 0 ? ' <span style="font-size:0.6rem;color:#94a3b8;">(' + (diffAmt >= 0 ? '+' : '') + fmtAmt(diffAmt) + ')</span>' : '') +
                '</td>' +
                '</tr>';
        });
        tbody.innerHTML = html || '<tr><td colspan="4" class="text-center py-3" style="color:#94a3b8;">데이터 없음</td></tr>';
    }

    // 매입 변경 상세 팝업
    window.showPurchaseChangeDetail = function(month) {
        var d = _purchaseChangeData;
        if (!d) return;
        var addedList = (d.added && d.added[month]) || [];
        var endedList = (d.ended && d.ended[month]) || [];
        var label = month.substring(2).replace('-', '.');

        var html = '<div style="max-height:500px;overflow-y:auto;">';

        // 추가 건
        html += '<div style="margin-bottom:16px;">';
        html += '<div style="font-size:0.9rem;font-weight:700;color:#059669;margin-bottom:8px;"><i class="fas fa-plus-circle me-1"></i>추가 (' + addedList.length + '건)</div>';
        if (addedList.length > 0) {
            html += '<table class="table table-sm table-hover mb-0" style="font-size:0.8rem;">';
            html += '<thead><tr style="background:#f0fdf4;"><th class="py-1">회원사</th><th class="py-1">통신사</th><th class="py-1">DC</th><th class="py-1">비용기준</th><th class="text-end py-1">매입금액</th><th class="py-1">과금시작</th></tr></thead><tbody>';
            addedList.forEach(function(item) {
                html += '<tr>' +
                    '<td class="py-1">' + item.company_name + '</td>' +
                    '<td class="py-1 text-center">' + item.provider + '</td>' +
                    '<td class="py-1 text-center">' + item.datacenter_code + '</td>' +
                    '<td class="py-1">' + item.cost_standart + '</td>' +
                    '<td class="text-end py-1" style="font-weight:600;color:#059669;">' + Number(item.cost_price).toLocaleString() + '원</td>' +
                    '<td class="py-1 text-center">' + item.billing_start_date + '</td>' +
                    '</tr>';
            });
            html += '</tbody></table>';
        } else {
            html += '<div style="color:#94a3b8;font-size:0.8rem;">해당 월 추가 건 없음</div>';
        }
        html += '</div>';

        // 종료 건
        html += '<div>';
        html += '<div style="font-size:0.9rem;font-weight:700;color:#dc2626;margin-bottom:8px;"><i class="fas fa-minus-circle me-1"></i>종료 (' + endedList.length + '건)</div>';
        if (endedList.length > 0) {
            html += '<table class="table table-sm table-hover mb-0" style="font-size:0.8rem;">';
            html += '<thead><tr style="background:#fef2f2;"><th class="py-1">회원사</th><th class="py-1">통신사</th><th class="py-1">DC</th><th class="py-1">비용기준</th><th class="text-end py-1">매입금액</th><th class="py-1">계약종료</th></tr></thead><tbody>';
            endedList.forEach(function(item) {
                html += '<tr>' +
                    '<td class="py-1">' + item.company_name + '</td>' +
                    '<td class="py-1 text-center">' + item.provider + '</td>' +
                    '<td class="py-1 text-center">' + item.datacenter_code + '</td>' +
                    '<td class="py-1">' + item.cost_standart + '</td>' +
                    '<td class="text-end py-1" style="font-weight:600;color:#dc2626;">' + Number(item.cost_price).toLocaleString() + '원</td>' +
                    '<td class="py-1 text-center">' + item.contract_end_date + '</td>' +
                    '</tr>';
            });
            html += '</tbody></table>';
        } else {
            html += '<div style="color:#94a3b8;font-size:0.8rem;">해당 월 종료 건 없음</div>';
        }
        html += '</div></div>';

        // 모달 표시
        var modal = document.getElementById('purchaseChangeModal');
        if (!modal) {
            var mdiv = document.createElement('div');
            mdiv.innerHTML = '<div class="modal fade" id="purchaseChangeModal" tabindex="-1"><div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content" style="border:none;border-radius:12px;overflow:hidden;">' +
                '<div class="modal-header py-2 px-3" style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">' +
                '<h6 class="modal-title" id="purchaseChangeModalTitle" style="font-size:0.92rem;font-weight:700;"></h6>' +
                '<button type="button" class="btn-close" data-bs-dismiss="modal" style="font-size:0.6rem;"></button></div>' +
                '<div class="modal-body p-3" id="purchaseChangeModalBody"></div>' +
                '</div></div></div>';
            document.body.appendChild(mdiv);
            modal = document.getElementById('purchaseChangeModal');
        }
        document.getElementById('purchaseChangeModalTitle').textContent = label + ' 매입 변경 상세';
        document.getElementById('purchaseChangeModalBody').innerHTML = html;
        var bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    };

    function renderCharts(memberAmounts, ktAmount, lguAmount, dcAmounts) {
        if (chartProvider) chartProvider.destroy();
        if (chartDC) chartDC.destroy();

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';

        // 1. 매입 TOP 5 (리스트 + 프로그레스바 - 초록 계열)
        var members = Object.keys(memberAmounts).map(function(k) { return memberAmounts[k]; });
        members.sort(function(a, b) { return b.amount - a.amount; });
        var top5 = members.slice(0, 5);
        var totalAmount = members.reduce(function(s, m) { return s + m.amount; }, 0);
        var maxAmount = top5.length > 0 ? top5[0].amount : 1;

        var barColors = ['#059669', '#10b981', '#34d399', '#6ee7b7', '#a7f3d0'];

        var html = '';
        top5.forEach(function(m, i) {
            var barW = maxAmount > 0 ? Math.round(m.amount / maxAmount * 100) : 0;
            var pct = totalAmount > 0 ? ((m.amount / totalAmount) * 100).toFixed(1) : 0;
            html += '<div style="padding:12px 0; border-bottom:1px solid ' + (isDark ? '#334155' : '#f1f5f9') + ';">' +
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">' +
                '<span style="min-width:18px;font-size:0.82rem;font-weight:700;color:#94a3b8;text-align:right;">' + (i + 1) + '</span>' +
                '<span style="flex:1;font-size:0.82rem;font-weight:600;color:' + (isDark ? '#e2e8f0' : '#1e293b') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + m.name + '</span>' +
                '<span style="font-size:0.82rem;font-weight:700;color:#059669;">' + m.amount.toLocaleString() + '원</span>' +
                '</div>' +
                '<div style="display:flex;align-items:center;gap:8px;padding-left:28px;">' +
                '<div style="flex:1;height:6px;background:rgba(0,0,0,0.03);border-radius:4px;overflow:hidden;">' +
                '<div style="height:100%;width:' + barW + '%;background:' + barColors[i] + ';border-radius:4px;transition:width 0.4s;"></div>' +
                '</div>' +
                '<span style="font-size:0.68rem;color:#94a3b8;white-space:nowrap;">' + m.count + '건 · ' + pct + '%</span>' +
                '</div>' +
                '</div>';
        });
        $('#top5Cards').html(html);

        // 도넛 중앙 텍스트 플러그인
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
                ctx.font = '500 0.65rem -apple-system, sans-serif';
                ctx.fillStyle = '#94a3b8';
                ctx.fillText(chart._centerLabel || '', centerX, centerY + 14);
                ctx.restore();
            }
        };

        // 2. KT vs LGU 매입 비율 (도넛 - 초록 계열 + 중앙 텍스트)
        var provTotal = ktAmount + lguAmount;
        var ktPct = provTotal > 0 ? ((ktAmount / provTotal) * 100).toFixed(1) : '0';

        chartProvider = new Chart(document.getElementById('chartProvider').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['KTC', 'LGU'],
                datasets: [{
                    data: [ktAmount, lguAmount],
                    backgroundColor: ['rgba(5, 150, 105, 0.7)', 'rgba(52, 211, 153, 0.6)'],
                    borderWidth: 2.5,
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
                                var pct = provTotal > 0 ? ((ctx.raw / provTotal) * 100).toFixed(1) : 0;
                                return ' ' + ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
        chartProvider._centerValue = ktPct + '%';
        chartProvider._centerLabel = 'KTC 비율';

        // 3. 데이터센터별 매입 분포 (도넛 - 초록 계열 + 중앙 텍스트)
        var dcKeys = Object.keys(dcAmounts).sort();
        var dcLabels = dcKeys;
        var dcData = dcKeys.map(function(k) { return dcAmounts[k].amount; });
        var dcTotal = dcData.reduce(function(a, b) { return a + b; }, 0);
        var dcColors = [
            'rgba(5, 150, 105, 0.75)',
            'rgba(16, 185, 129, 0.7)',
            'rgba(52, 211, 153, 0.65)',
            'rgba(110, 231, 183, 0.6)',
            'rgba(13, 148, 136, 0.7)',
            'rgba(15, 118, 110, 0.65)'
        ];

        chartDC = new Chart(document.getElementById('chartDC').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: dcLabels,
                datasets: [{
                    data: dcData,
                    backgroundColor: dcColors.slice(0, dcLabels.length),
                    borderWidth: 2.5,
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
                                var pct = dcTotal > 0 ? ((ctx.raw / dcTotal) * 100).toFixed(1) : 0;
                                return ' ' + ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
        chartDC._centerValue = dcLabels.length + '개';
        chartDC._centerLabel = '데이터센터';
    }

    function populateCostCodeSelect(selectId, selectedValue) {
        var $select = $(selectId);
        $select.find('option:gt(0)').remove();
        costCodes.forEach(function(c) {
            var label = c.code + ' / ' + (c.cost_standart || '-') + ' / ' + formatPrice(c.cost_price);
            var opt = $('<option></option>').val(c.code).text(label);
            if (c.code === selectedValue) opt.prop('selected', true);
            $select.append(opt);
        });
    }

    function showCostInfo(infoId, code) {
        var info = costCodes.find(function(c) { return c.code === code; });
        if (info) {
            $(infoId).html(info.cost_standart + ' / <strong>' + formatPrice(info.cost_price) + '</strong>');
        } else {
            $(infoId).html('');
        }
    }

    function loadCostCodes() {
        return fetch('/purchase_contract/get_cost_codes')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    costCodes = result.data;
                }
            })
            .catch(function(err) {
                console.error('Cost codes load error:', err);
            });
    }

    function loadMemberCodes() {
        return fetch('/subscriber_codes/get_codes')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    memberCodes = result.data.sort(function(a, b) {
                        return (a.member_code || '').localeCompare(b.member_code || '');
                    });
                }
            })
            .catch(function(err) {
                console.error('Member codes load error:', err);
            });
    }

    function populateMemberCodeSelect(selectId, selectedValue) {
        var $select = $(selectId);
        $select.find('option:gt(0)').remove();
        memberCodes.forEach(function(m) {
            var label = m.member_code + ' - ' + (m.company_name || '');
            var opt = $('<option></option>').val(m.member_code).text(label);
            if (m.member_code === selectedValue) opt.prop('selected', true);
            $select.append(opt);
        });
    }

    var initTable = function() {
        purchaseTable = $('#purchaseTable').DataTable({
            responsive: true,
            paging: false,
            searching: true,
            ordering: true,
            order: [[0, 'asc'], [2, 'asc']],
            language: {
                search: "검색:",
                lengthMenu: "페이지당 _MENU_ 개씩 표시",
                info: "전체 _TOTAL_개 중 _START_-_END_개 표시",
                infoEmpty: "데이터가 없습니다",
                infoFiltered: "(전체 _MAX_개 중 필터링됨)",
                paginate: {
                    first: "처음",
                    last: "마지막",
                    next: "다음",
                    previous: "이전"
                },
                emptyTable: "검색 결과가 없습니다",
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: " "
            },
            dom: '<"row align-items-center"<"col-sm-12 d-flex justify-content-end align-items-center gap-2"fB>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12"i>>',
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '매입내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '매입내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                }
            ],
            ajax: {
                url: '/purchase_contract/get_purchase_contract',
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
                { data: 'datacenter_code' },
                { data: 'provider' },
                { data: 'billing_start_date' },
                { data: 'contract_end_date' },
                { data: 'service_id' },
                { data: 'nni_id' },
                { data: 'cost_code' },
                { data: 'cost_standart' },
                { data: 'cost_price' }
            ],
            columnDefs: [
                {
                    targets: 0, // 회원번호
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 회원사코드
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회사명
                    width: '10%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '<span class="badge bg-danger bg-opacity-10 text-danger" style="font-size: 0.65rem; font-weight: 600;">코드입력필요</span>';
                        return data;
                    }
                },
                {
                    targets: 3, // 데이터센터
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-warning">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 통신사
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        var badgeClass = data === 'KTC' ? 'badge-phoenix-info' : 'badge-phoenix-success';
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
                    }
                },
                {
                    targets: 5, // 과금시작일
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return data.substring(0, 10);
                    }
                },
                {
                    targets: 6, // 계약종료일
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return data.substring(0, 10);
                    }
                },
                {
                    targets: 7, // 서비스ID
                    width: '10%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 8, // NNI ID
                    width: '10%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 9, // 원가코드
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 600; color: #4f46e5; background: #eef2ff;">' + data + '</span>';
                    }
                },
                {
                    targets: 10, // 비용기준
                    width: '14%',
                    className: 'text-start py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 11, // 매입금액
                    width: '12%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="fw-bold" style="color: #0f172a; white-space:nowrap;">' + Number(data).toLocaleString() + '원</span>';
                    }
                }
            ],
            drawCallback: function(settings) {
                var api = this.api();
                var rows = api.rows({ page: 'current' }).nodes();
                var data = api.rows({ page: 'current' }).data();
                var colCount = api.columns().nodes().length;

                if (!data.length) return;

                var lastGroup = '';
                var lastCompany = '';
                var groupAmount = 0;
                var groupCount = 0;
                var insertPoints = [];

                // 그룹별 소계 위치 계산
                data.each(function(row, i) {
                    var group = row.member_code || '?';
                    if (lastGroup && group !== lastGroup) {
                        insertPoints.push({ afterIdx: i - 1, code: lastGroup, name: lastCompany, amount: groupAmount, count: groupCount });
                        groupAmount = 0;
                        groupCount = 0;
                    }
                    groupAmount += (row.cost_price || 0);
                    groupCount++;
                    lastGroup = group;
                    lastCompany = row.company_name || group;
                });
                // 마지막 그룹
                if (lastGroup) {
                    insertPoints.push({ afterIdx: data.length - 1, code: lastGroup, name: lastCompany, amount: groupAmount, count: groupCount });
                }

                // 전체 합계 계산
                var grandTotal = 0;
                var grandCount = 0;
                insertPoints.forEach(function(p) { grandTotal += p.amount; grandCount += p.count; });

                // 역순으로 삽입 (인덱스 밀림 방지)
                for (var i = insertPoints.length - 1; i >= 0; i--) {
                    var p = insertPoints[i];
                    var subtotalRow = '<tr class="subtotal-row" style="background: #f0f4ff !important; border-top: 2px solid #c7d2fe; pointer-events: none;">' +
                        '<td colspan="3" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 700; color: #4338ca; padding-left: 14px !important;">' +
                        '<i class="fas fa-calculator me-1" style="font-size: 0.6rem; opacity: 0.7;"></i>' + p.name + ' 소계 (' + p.count + '건)</td>' +
                        '<td colspan="9"></td>' +
                        '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #4338ca; padding-right: 12px !important; white-space:nowrap;">' + Number(p.amount).toLocaleString() + '원</td>' +
                        '</tr>';
                    $(rows[p.afterIdx]).after(subtotalRow);
                }

                // 전체 합계 행 (테이블 맨 마지막)
                if (grandCount > 0) {
                    var grandRow = '<tr class="subtotal-row" style="background: #1e293b !important; pointer-events: none;">' +
                        '<td colspan="3" class="text-start py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                        '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + grandCount + '건)</td>' +
                        '<td colspan="9"></td>' +
                        '<td class="text-end py-2 align-middle" style="font-size: 0.95rem; font-weight: 800; color: #fbbf24; padding-right: 12px !important; white-space:nowrap;">' + Number(grandTotal).toLocaleString() + '원</td>' +
                        '</tr>';
                    $('#purchaseTable tbody').append(grandRow);
                }
            },
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.remove(); }, 400);
                }
            }
        });

        // 행 클릭 커서
        $('#purchaseTable tbody').css('cursor', 'pointer');

        // tfoot 검색 필드
        $('#purchaseTable tfoot th').each(function() {
            var title = $(this).text();
            $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
            $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.75rem; padding:2px 4px;" />');
        });

        // 개별 열 검색
        purchaseTable.columns().every(function() {
            var that = this;
            $('input', this.footer()).on('keyup change', function() {
                if (that.search() !== this.value) {
                    that.search(this.value).draw();
                }
            });
        });

        // 행 클릭 시 수정 모달 (소계 행 제외)
        $('#purchaseTable tbody').on('click', 'tr:not(.subtotal-row)', function() {
            var data = purchaseTable.row(this).data();
            if (!data) return;
            showEditModalFromData(data);
        });
    };

    function showEditModalFromData(item) {
        $('#edit_id').val(item.id);
        populateMemberCodeSelect('#edit_member_code', item.member_code || '');
        $('#edit_datacenter_code').val(item.datacenter_code || '');
        $('#edit_provider').val(item.provider || '');
        $('#edit_billing_start_date').val(item.billing_start_date ? item.billing_start_date.substring(0, 10) : '');
        $('#edit_contract_end_date').val(item.contract_end_date ? item.contract_end_date.substring(0, 10) : '');
        $('#edit_service_id').val(item.service_id || '');
        $('#edit_nni_id').val(item.nni_id || '');
        populateCostCodeSelect('#edit_cost_code', item.cost_code || '');
        showCostInfo('#edit_cost_info', item.cost_code || '');

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    }

    window.resetFilters = function() {
        $('#purchaseTable tfoot input').val('');
        if (purchaseTable) {
            purchaseTable.columns().search('').draw();
        }
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        resetFilters();
        if (purchaseTable) {
            purchaseTable.ajax.reload(function() {
                spinner.remove();
            }, false);
        } else {
            spinner.remove();
        }
    };

    window.showCreateModal = function() {
        $('#createForm')[0].reset();
        populateMemberCodeSelect('#add_member_code', '');
        populateCostCodeSelect('#add_cost_code', '');
        $('#add_cost_info').html('');
        var modal = new bootstrap.Modal(document.getElementById('createModal'));
        modal.show();
    };

    window.saveCreate = function() {
        var data = {
            member_code: $('#add_member_code').val().trim(),
            datacenter_code: $('#add_datacenter_code').val(),
            provider: $('#add_provider').val(),
            billing_start_date: $('#add_billing_start_date').val() || null,
            contract_end_date: $('#add_contract_end_date').val() || null,
            service_id: $('#add_service_id').val().trim() || null,
            nni_id: $('#add_nni_id').val().trim() || null,
            cost_code: $('#add_cost_code').val() || null
        };

        if (!data.member_code) {
            showAlert('회원사코드는 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/purchase_contract/create_purchase_contract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('createModal')).hide();
                refreshTable();
            } else {
                showAlert('추가 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('추가 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            member_code: $('#edit_member_code').val().trim(),
            datacenter_code: $('#edit_datacenter_code').val(),
            provider: $('#edit_provider').val(),
            billing_start_date: $('#edit_billing_start_date').val() || null,
            contract_end_date: $('#edit_contract_end_date').val() || null,
            service_id: $('#edit_service_id').val().trim() || null,
            nni_id: $('#edit_nni_id').val().trim() || null,
            cost_code: $('#edit_cost_code').val() || null
        };

        if (!data.member_code) {
            showAlert('회원사코드는 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/purchase_contract/update_purchase_contract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                refreshTable();
            } else {
                showAlert('수정 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('수정 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.deleteFromEdit = function() {
        var id = parseInt($('#edit_id').val());
        var memberCode = $('#edit_member_code').val();
        if (!confirm('"' + memberCode + '" 항목을 삭제하시겠습니까?')) {
            return;
        }

        fetch('/purchase_contract/delete_purchase_contract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id })
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('삭제가 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                refreshTable();
            } else {
                showAlert('삭제 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    };

    function showAlert(message, type) {
        var icons = {
            success: 'fa-check-circle',
            danger: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        var colors = {
            success: '#10b981',
            danger: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        var titles = {
            success: '완료',
            danger: '오류',
            warning: '알림',
            info: '안내'
        };
        var icon = icons[type] || icons.info;
        var color = colors[type] || colors.info;
        var title = titles[type] || titles.info;

        if (!$('#toastContainer').length) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }

        var toastId = 'toast_' + Date.now();
        var toastHtml = '<div id="' + toastId + '" class="toast align-items-center border-0 shadow-lg" role="alert" data-bs-delay="3000" style="border-radius: 10px; overflow: hidden; border-left: 4px solid ' + color + ' !important;">' +
            '<div class="toast-header border-0" style="padding: 10px 14px;">' +
            '<i class="fas ' + icon + ' me-2" style="color: ' + color + '; font-size: 0.9rem;"></i>' +
            '<strong class="me-auto" style="font-size: 0.8rem; color: #1e293b;">' + title + '</strong>' +
            '<button type="button" class="btn-close" data-bs-dismiss="toast" style="font-size: 0.55rem;"></button>' +
            '</div>' +
            '<div class="toast-body" style="padding: 0 14px 12px; font-size: 0.78rem; color: #475569;">' + message + '</div>' +
            '</div>';

        $('#toastContainer').append(toastHtml);
        var toastEl = document.getElementById(toastId);
        var toast = new bootstrap.Toast(toastEl);
        toast.show();

        toastEl.addEventListener('hidden.bs.toast', function() {
            $(toastEl).remove();
        });
    }

    $(document).ready(function() {
        Promise.all([loadCostCodes(), loadMemberCodes()]).then(function() {
            initTable();
        });

        // cost_code select 변경 시 매입금액 자동 표시
        $(document).on('change', '#add_cost_code', function() {
            showCostInfo('#add_cost_info', $(this).val());
        });
        $(document).on('change', '#edit_cost_code', function() {
            showCostInfo('#edit_cost_info', $(this).val());
        });
    });

}));
