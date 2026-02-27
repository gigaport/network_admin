/**
 * 네트워크 통합 대시보드 - Clean White Style (Dark Theme Support)
 */

var chartInstances = {};

// 컬러 팔레트 (Clean & Minimal)
var C = {
    blue: '#4a7cff',
    green: '#36b37e',
    orange: '#ff9f43',
    purple: '#a855f7',
    red: '#ff6b6b',
    cyan: '#00b8d9',
    pink: '#f06595',
    teal: '#20c997',
    multi: ['#4a7cff', '#36b37e', '#ff9f43', '#a855f7', '#ff6b6b', '#00b8d9', '#f06595', '#20c997']
};

// 다크 테마 감지
function isDark() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}
// 테마에 따른 색상 반환
function T(light, dark) { return isDark() ? dark : light; }

document.addEventListener('DOMContentLoaded', function() {
    loadDashboard();
    loadMulticastStatus();
    loadPtpStatus();
    loadNetboxSummary();
    loadRevenueTrend();
});

function loadDashboard() {
    fetch('/get_dashboard')
        .then(function(res) { return res.json(); })
        .then(function(resp) {
            if (resp.success && resp.data) {
                renderDashboard(resp.data);
            }
            removeOverlay();
        })
        .catch(function(err) {
            console.error('Dashboard load error:', err);
            removeOverlay();
        });
    resetBadge('stat_multicast');
    resetBadge('stat_ptp');
    loadMulticastStatus();
    loadPtpStatus();
    loadNetboxSummary();
    loadRevenueTrend();
}

function resetBadge(id) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:0.6rem;height:0.6rem;"></span> 확인 중';
}

function removeOverlay() {
    var o = document.getElementById('pageLoadingOverlay');
    if (o) { o.style.opacity = '0'; setTimeout(function() { o.remove(); }, 400); }
}

// ========== 메인 렌더링 ==========
function renderDashboard(data) {
    renderSummaryCards(data.summary);
    renderTopMembersChart(data.top_members);
    renderStatGrids(data.circuits_by_provider, data.circuits_by_env, data.circuits_by_usage);
    renderRevenueUsageChart(data.revenue ? data.revenue.by_usage : null);
    renderDcChart(data.circuits_by_dc);
    if (data.revenue) {
        renderRevenueCard(data.revenue);
        renderTopRevenueChart(data.revenue.top_members);
    }
}

// ========== 요약 카드 ==========
function renderSummaryCards(s) {
    setText('stat_total_circuits', fmtNum(s.total_circuits));
    setText('stat_total_members', fmtNum(s.total_members));
    setText('stat_total_products', fmtNum(s.total_products));
    setText('stat_total_fee', fmtNum(s.total_fee_items));
}

// ========== 매출 카드 ==========
function renderRevenueCard(rev) {
    setText('stat_revenue_total', fmtWon(rev.grand_total));
    setText('stat_revenue_ord', fmtWon(rev.ord_total));
    setText('stat_revenue_mpr', fmtWon(rev.mpr_total));
}

// ========== 회선 분류별 통계 그리드 (컬러 도트) ==========
function renderStatGrids(provider, env, usage) {
    renderStatGrid('statGridProvider', '통신사별', provider, C.multi);
    renderStatGrid('statGridEnv', '환경별', env, [C.green, C.red, C.orange, C.blue]);
    renderStatGrid('statGridUsage', '용도별', usage, [C.orange, C.cyan, C.purple, C.green, C.red, C.blue]);
}

function renderStatGrid(containerId, title, data, colors) {
    var el = document.getElementById(containerId);
    if (!el || !data) return;

    var keys = Object.keys(data);
    var labelColor = T('#8c8c8c', '#64748b');
    var textColor = T('#555', '#94a3b8');
    var valColor = T('#1a1a2e', '#e2e8f0');
    var html = '<div style="font-size:0.72rem;font-weight:600;color:' + labelColor + ';margin-bottom:8px;">' + esc(title) + '</div>';
    html += '<div class="row g-2">';
    keys.forEach(function(k, i) {
        html += '<div class="col-6">' +
            '<div class="d-flex align-items-center" style="padding:4px 0;">' +
            '<span class="dash-stat-dot" style="background:' + colors[i % colors.length] + ';"></span>' +
            '<span style="font-size:0.72rem;color:' + textColor + ';">' + esc(k) + '</span>' +
            '<span style="font-size:0.82rem;font-weight:700;color:' + valColor + ';margin-left:auto;">' + data[k] + '</span>' +
            '</div></div>';
    });
    html += '</div>';
    el.innerHTML = html;
}

// ========== 멀티캐스트 상태 ==========
function loadMulticastStatus() {
    fetch('/multicast/init?sub_menu=pr_info_multicast', { signal: AbortSignal.timeout(25000) })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (!Array.isArray(data) || data.length === 0) {
                setBadge('stat_multicast', '데이터 없음', 'info');
                setTableEmpty('multicastTableBody', 6);
                return;
            }
            var total = data.length;
            var normal = data.filter(function(d) { return d.check_result === '정상확인' || d.check_result === '회원사연결서버없음'; }).length;
            var abnormal = total - normal;
            if (abnormal === 0) setBadge('stat_multicast', total + '/' + total + ' 정상', 'success');
            else setBadge('stat_multicast', abnormal + '건 확인필요', 'warn');
            renderMulticastTable(data);
        })
        .catch(function() {
            setBadge('stat_multicast', '연결 실패', 'error');
            setTableEmpty('multicastTableBody', 6);
        });
}

function loadPtpStatus() {
    fetch('/information/init?sub_menu=info_ptp', { signal: AbortSignal.timeout(25000) })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (!Array.isArray(data) || data.length === 0) {
                setBadge('stat_ptp', '데이터 없음', 'info');
                setTableEmpty('ptpTableBody', 7);
                return;
            }
            var total = data.length;
            var abnormal = data.filter(function(d) {
                return (d.offset !== undefined && Math.abs(d.offset) > 1000)
                    || (d.packet_continuity !== undefined && d.packet_continuity < 100);
            }).length;
            if (abnormal === 0) setBadge('stat_ptp', total + '/' + total + ' 정상', 'success');
            else setBadge('stat_ptp', abnormal + '건 이상', 'warn');
            renderPtpTable(data);
        })
        .catch(function() {
            setBadge('stat_ptp', '연결 실패', 'error');
            setTableEmpty('ptpTableBody', 7);
        });
}

function setBadge(id, text, type) {
    var el = document.getElementById(id);
    if (!el) return;
    el.className = 'dash-badge dash-badge-' + type;
    el.textContent = text;
}

// ========== 멀티캐스트 테이블 ==========
function renderMulticastTable(data) {
    var tbody = document.getElementById('multicastTableBody');
    if (!tbody) return;
    var sorted = data.slice().sort(function(a, b) {
        var aOk = (a.check_result === '정상확인' || a.check_result === '회원사연결서버없음') ? 1 : 0;
        var bOk = (b.check_result === '정상확인' || b.check_result === '회원사연결서버없음') ? 1 : 0;
        return aOk - bOk;
    });
    var html = '';
    sorted.forEach(function(d) {
        var badge = getMcBadge(d.check_result, d.check_result_badge);
        html += '<tr style="border-bottom:1px solid #f5f5f5;">' +
            '<td class="text-center py-2">' + esc(d.member_name || d.member_code || '-') + '</td>' +
            '<td class="text-center py-2" style="color:#999;font-size:0.68rem;">' + esc(d.device_name || '-') + '</td>' +
            '<td class="text-center py-2">' + (d.product_cnt != null ? d.product_cnt : '-') + '</td>' +
            '<td class="text-center py-2">' + (d.mroute_cnt != null ? d.mroute_cnt : '-') + '</td>' +
            '<td class="text-center py-2">' + (d.oif_cnt != null ? d.oif_cnt : '-') + '</td>' +
            '<td class="text-center py-2">' + badge + '</td></tr>';
    });
    tbody.innerHTML = html;
}

function getMcBadge(result, info) {
    var type = (info && info.type) || 'secondary';
    var cls = 'dash-badge-info';
    if (type === 'success') cls = 'dash-badge-success';
    else if (type === 'warning') cls = 'dash-badge-warn';
    else if (type === 'danger') cls = 'dash-badge-error';
    return '<span class="dash-badge ' + cls + '">' + esc(result || '-') + '</span>';
}

// ========== PTP 테이블 ==========
function renderPtpTable(data) {
    var tbody = document.getElementById('ptpTableBody');
    if (!tbody) return;
    var sorted = data.slice().sort(function(a, b) {
        var aW = (Math.abs(a.offset || 0) > 1000 || (a.packet_continuity != null && a.packet_continuity < 100)) ? 0 : 1;
        var bW = (Math.abs(b.offset || 0) > 1000 || (b.packet_continuity != null && b.packet_continuity < 100)) ? 0 : 1;
        return aW - bW;
    });
    var html = '';
    sorted.forEach(function(d) {
        var oW = d.offset !== undefined && Math.abs(d.offset) > 1000;
        var cW = d.packet_continuity !== undefined && d.packet_continuity < 100;
        var region = getPtpRegion(d.device_name);
        html += '<tr style="border-bottom:1px solid #f5f5f5;">' +
            '<td class="text-center py-2">' + esc(region) + '</td>' +
            '<td class="text-center py-2" style="font-size:0.68rem;">' + esc(d.device_name || '-') + '</td>' +
            '<td class="text-center py-2" style="font-size:0.68rem;color:#999;">' + esc(d.current_time || '-') + '</td>' +
            '<td class="text-center py-2" style="' + (oW ? 'color:#c62828;font-weight:700;' : '') + '">' + fmtPtp(d.offset) + '</td>' +
            '<td class="text-center py-2">' + fmtPtp(d.mean_path_delay) + '</td>' +
            '<td class="text-center py-2">' + fmtPtp(d.jitter) + '</td>' +
            '<td class="text-center py-2" style="' + (cW ? 'color:#c62828;font-weight:700;' : '') + '">' + fmtCont(d.packet_continuity) + '</td></tr>';
    });
    tbody.innerHTML = html;
}

function getPtpRegion(n) {
    if (!n) return '-';
    var u = n.toUpperCase();
    if (u.indexOf('PYD') >= 0 || u.indexOf('PRD') >= 0) return '운영';
    if (u.indexOf('TYD') >= 0 || u.indexOf('TSD') >= 0) return '테스트';
    if (u.indexOf('DR') >= 0) return 'DR';
    return '-';
}

// ========== Top 5 회선 보유 (번호 + 가로 바) ==========
function renderTopMembersChart(members) {
    var el = document.getElementById('chartTopMembers');
    if (!el || !members || members.length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartTopMembers');
    var top5 = members.slice(0, 5).reverse();
    var names = top5.map(function(m, i) { return (5 - i) + '. ' + (m.company_name || m.member_code); });
    var counts = top5.map(function(m) { return m.circuit_count; });
    var max = Math.max.apply(null, counts);

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'none' }, formatter: function(p) { return p[0].name.substring(3) + ': ' + p[0].value + '건'; } },
        grid: { left: 5, right: 50, top: 5, bottom: 5, containLabel: true },
        xAxis: { type: 'value', show: false, max: max * 1.3 },
        yAxis: {
            type: 'category', data: names,
            axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { fontSize: 11, color: T('#555', '#94a3b8'), fontWeight: 500, width: 110, overflow: 'truncate' }
        },
        series: [{
            type: 'bar', data: counts, barWidth: 12,
            itemStyle: { borderRadius: [0, 6, 6, 0], color: C.blue },
            label: { show: true, position: 'right', fontSize: 11, fontWeight: 700, color: T('#1a1a2e', '#e2e8f0'), formatter: '({c})' }
        }]
    });
}

// ========== ORD/MPR 매출 도넛 ==========
function renderRevenueUsageChart(data) {
    var el = document.getElementById('chartRevenueUsage');
    if (!el || !data || Object.keys(data).length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartRevenueUsage');
    var usageColors = { 'ORD': C.green, 'MPR': C.blue };
    var grandTotal = 0;
    var seriesData = Object.keys(data).map(function(k) {
        grandTotal += data[k];
        return { value: data[k], name: k, itemStyle: { color: usageColors[k] || '#ccc' } };
    });

    chart.setOption({
        tooltip: {
            trigger: 'item',
            formatter: function(p) { return p.name + ': ' + Number(p.value).toLocaleString() + '원 (' + p.percent + '%)'; }
        },
        legend: { bottom: 0, textStyle: { fontSize: 11, color: T('#999', '#94a3b8') } },
        graphic: [{
            type: 'group', left: 'center', top: '33%',
            children: [
                { type: 'text', left: 'center', style: { text: fmtWon(grandTotal), textAlign: 'center', fontSize: 20, fontWeight: 'bold', fill: T('#1a1a2e', '#e2e8f0') } },
                { type: 'text', left: 'center', top: 28, style: { text: '월 매출', textAlign: 'center', fontSize: 11, fill: T('#b0b0b0', '#64748b') } }
            ]
        }],
        series: [{
            type: 'pie', radius: ['48%', '72%'], center: ['50%', '42%'],
            itemStyle: { borderRadius: 6, borderColor: T('#fff', '#1e2a3a'), borderWidth: 3 },
            label: { show: false },
            emphasis: { label: { show: false }, itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.08)' } },
            data: seriesData
        }]
    });
}

// ========== 매출 Top 10 가로 스택 바 ==========
function renderTopRevenueChart(members) {
    var el = document.getElementById('chartTopRevenue');
    if (!el || !members || members.length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartTopRevenue');
    var top5 = members.slice(0, 5).reverse();
    var names = top5.map(function(m) { return m.company_name || m.member_code; });
    var ordData = top5.map(function(m) { return m.ord_revenue || 0; });
    var mprData = top5.map(function(m) { return m.mpr_revenue || 0; });

    chart.setOption({
        tooltip: {
            trigger: 'axis', axisPointer: { type: 'shadow' },
            formatter: function(params) {
                var lines = [params[0].name];
                var total = 0;
                params.forEach(function(p) { lines.push(p.marker + ' ' + p.seriesName + ': ' + Number(p.value).toLocaleString() + '원'); total += p.value; });
                lines.push('<b>합계: ' + Number(total).toLocaleString() + '원</b>');
                return lines.join('<br>');
            }
        },
        legend: { bottom: 0, textStyle: { fontSize: 10, color: T('#999', '#94a3b8') } },
        grid: { left: 5, right: 50, top: 5, bottom: 25, containLabel: true },
        xAxis: { type: 'value', show: false },
        yAxis: {
            type: 'category', data: names,
            axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { fontSize: 10, color: T('#555', '#94a3b8'), width: 75, overflow: 'truncate' }
        },
        series: [
            { name: 'ORD', type: 'bar', stack: 'rev', data: ordData, barWidth: 10, itemStyle: { color: C.green } },
            {
                name: 'MPR', type: 'bar', stack: 'rev', data: mprData, barWidth: 10,
                itemStyle: { color: C.blue, borderRadius: [0, 4, 4, 0] },
                label: { show: true, position: 'right', fontSize: 9, color: T('#999', '#94a3b8'),
                    formatter: function(p) { return fmtWon((ordData[p.dataIndex] || 0) + (mprData[p.dataIndex] || 0)); }
                }
            }
        ]
    });
}

// ========== DC별 바 차트 ==========
function renderDcChart(data) {
    var el = document.getElementById('chartDc');
    if (!el || !data || Object.keys(data).length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartDc');
    var dcNames = Object.keys(data).sort();
    var usageSet = {};
    dcNames.forEach(function(dc) { Object.keys(data[dc]).forEach(function(u) { usageSet[u] = true; }); });
    var usages = Object.keys(usageSet).sort();

    var series = usages.map(function(usage, idx) {
        return {
            name: usage, type: 'bar', stack: 'dc', barWidth: 24,
            itemStyle: { color: C.multi[idx % C.multi.length], borderRadius: idx === usages.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0] },
            data: dcNames.map(function(dc) { return data[dc][usage] || 0; })
        };
    });

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { bottom: 0, textStyle: { fontSize: 10, color: T('#999', '#94a3b8') } },
        grid: { left: 10, right: 10, top: 10, bottom: 32, containLabel: true },
        xAxis: { type: 'category', data: dcNames, axisLine: { lineStyle: { color: T('#f0f0f0', '#2d3d50') } }, axisTick: { show: false }, axisLabel: { fontSize: 11, color: T('#555', '#94a3b8') } },
        yAxis: { type: 'value', axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: T('#f5f5f5', '#2d3d50') } }, axisLabel: { fontSize: 10, color: T('#ccc', '#64748b') } },
        series: series
    });
}

// ========== NetBox 디바이스 요약 ==========
var NB_MANUFACTURERS = ['arista', 'CISCO', 'JUNIPER', 'F5'];

function nbMfrParams() {
    return NB_MANUFACTURERS.map(function(m) { return 'manufacturer=' + encodeURIComponent(m); }).join('&');
}

function loadNetboxSummary() {
    var allResults = [];
    function fetchPage(offset) {
        var url = '/netbox_devices/get_netbox_devices?limit=1000&offset=' + offset + '&' + nbMfrParams();
        return fetch(url, { signal: AbortSignal.timeout(20000) })
            .then(function(res) { return res.json(); })
            .then(function(resp) {
                if (!resp.success || !resp.data) return;
                allResults = allResults.concat(resp.data.results || []);
                if (resp.data.next && allResults.length < resp.data.count) {
                    return fetchPage(allResults.length);
                }
                renderNetboxSummary({ count: resp.data.count, results: allResults });
            });
    }
    fetchPage(0).catch(function(err) { console.error('NetBox summary load error:', err); });
}

function renderNetboxSummary(data) {
    var results = data.results || [];
    var total = data.count || results.length;
    var active = 0;
    var idle = 0;
    var operating = 0;
    var roleCounts = {};
    var mfrCounts = {};
    var siteSet = {};

    results.forEach(function(d) {
        if (d.status && d.status.value === 'active') active++;
        // 운영/유휴 구분: role.name이 IDLE이면 유휴장비 (slug 기준 시 데이터 불일치 방지)
        var isIdle = d.role && d.role.name === 'IDLE';
        if (isIdle) { idle++; } else { operating++; }
        if (d.role && d.role.name) {
            roleCounts[d.role.name] = (roleCounts[d.role.name] || 0) + 1;
        }
        if (d.device_type && d.device_type.manufacturer && d.device_type.manufacturer.name) {
            var mName = d.device_type.manufacturer.name;
            mfrCounts[mName] = (mfrCounts[mName] || 0) + 1;
        }
        if (d.site && d.site.name) {
            siteSet[d.site.name] = true;
        }
    });

    // 요약 숫자
    setText('stat_nb_total', fmtNum(total));
    setText('stat_nb_active', fmtNum(active));
    setText('stat_nb_sites', fmtNum(Object.keys(siteSet).length));
    setText('stat_nb_operating', fmtNum(operating));
    setText('stat_nb_idle', fmtNum(idle));

    // 역할별 그리드
    var roleColors = { 'PRD': '#10b981', 'TST': '#f59e0b', 'DR': '#a855f7', 'DEV': '#3b82f6' };
    var gridEl = document.getElementById('statGridNetbox');
    if (gridEl) {
        var html = '<div style="font-size:0.72rem;font-weight:600;color:' + T('#8c8c8c', '#64748b') + ';margin-bottom:6px;">역할별</div>';
        html += '<div class="row g-1">';
        Object.keys(roleCounts).sort().forEach(function(k) {
            var c = roleColors[k] || '#6b7280';
            html += '<div class="col-6"><div class="d-flex align-items-center" style="padding:3px 0;">' +
                '<span class="dash-stat-dot" style="background:' + c + ';"></span>' +
                '<span style="font-size:0.72rem;color:' + T('#555', '#94a3b8') + ';">' + esc(k) + '</span>' +
                '<span style="font-size:0.82rem;font-weight:700;color:' + T('#1a1a2e', '#e2e8f0') + ';margin-left:auto;">' + roleCounts[k] + '</span>' +
                '</div></div>';
        });
        html += '</div>';
        gridEl.innerHTML = html;
    }

    // 역할별 도넛 차트
    renderNetboxRoleChart(roleCounts, roleColors);

    // 제조사 Top 10 바 차트
    renderNetboxMfrChart(mfrCounts);

    // 제조사별 장비 현황 테이블 (전체/운영/유휴)
    renderMfrSummaryTable(results);

    // 유휴자산 제조사·모델별 보유수량 테이블
    renderIdleAssetTable(results);
}

function renderNetboxRoleChart(roleCounts, roleColors) {
    var el = document.getElementById('chartNetboxRole');
    if (!el || Object.keys(roleCounts).length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartNetboxRole');
    var total = 0;
    var seriesData = Object.keys(roleCounts).sort().map(function(k) {
        total += roleCounts[k];
        return { value: roleCounts[k], name: k, itemStyle: { color: roleColors[k] || '#6b7280' } };
    });

    chart.setOption({
        tooltip: {
            trigger: 'item',
            formatter: function(p) { return p.name + ': ' + p.value + '대 (' + p.percent + '%)'; }
        },
        legend: { bottom: 0, textStyle: { fontSize: 11, color: T('#999', '#94a3b8') } },
        graphic: [{
            type: 'group', left: 'center', top: '33%',
            children: [
                { type: 'text', left: 'center', style: { text: fmtNum(total), textAlign: 'center', fontSize: 22, fontWeight: 'bold', fill: T('#1a1a2e', '#e2e8f0') } },
                { type: 'text', left: 'center', top: 28, style: { text: '총 디바이스', textAlign: 'center', fontSize: 11, fill: T('#b0b0b0', '#64748b') } }
            ]
        }],
        series: [{
            type: 'pie', radius: ['48%', '72%'], center: ['50%', '42%'],
            itemStyle: { borderRadius: 6, borderColor: T('#fff', '#1e2a3a'), borderWidth: 3 },
            label: {
                show: true, position: 'outside', fontSize: 11, color: T('#555', '#94a3b8'),
                formatter: function(p) { return p.name + '\n' + p.value + '대'; }
            },
            emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.08)' } },
            data: seriesData
        }]
    });
}

function renderNetboxMfrChart(mfrCounts) {
    var el = document.getElementById('chartNetboxMfr');
    if (!el || Object.keys(mfrCounts).length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartNetboxMfr');

    // Top 10 정렬
    var sorted = Object.keys(mfrCounts).map(function(k) { return { name: k, count: mfrCounts[k] }; })
        .sort(function(a, b) { return b.count - a.count; }).slice(0, 10).reverse();
    var names = sorted.map(function(m) { return m.name; });
    var counts = sorted.map(function(m) { return m.count; });
    var max = Math.max.apply(null, counts);

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'none' }, formatter: function(p) { return p[0].name + ': ' + p[0].value + '대'; } },
        grid: { left: 5, right: 55, top: 5, bottom: 5, containLabel: true },
        xAxis: { type: 'value', show: false, max: max * 1.35 },
        yAxis: {
            type: 'category', data: names,
            axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { fontSize: 11, color: T('#555', '#94a3b8'), fontWeight: 500, width: 90, overflow: 'truncate' }
        },
        series: [{
            type: 'bar', data: counts, barWidth: 14,
            itemStyle: {
                borderRadius: [0, 6, 6, 0],
                color: function(params) {
                    var gradients = ['#6366f1', '#818cf8', '#a5b4fc', '#6366f1', '#818cf8', '#a5b4fc', '#6366f1', '#818cf8', '#a5b4fc', '#6366f1'];
                    return gradients[params.dataIndex % gradients.length];
                }
            },
            label: { show: true, position: 'right', fontSize: 11, fontWeight: 700, color: T('#1a1a2e', '#e2e8f0'), formatter: '{c}' }
        }]
    });
}

// ========== 제조사별 장비 현황 테이블 ==========
function renderMfrSummaryTable(results) {
    var tbody = document.getElementById('mfrSummaryTableBody');
    if (!tbody) return;
    if (!results || results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3" style="color:#ccc;font-size:0.75rem;">데이터 없음</td></tr>';
        return;
    }
    // 제조사별 전체/운영/유휴 집계
    var mfrMap = {};
    results.forEach(function(d) {
        var mfr = (d.device_type && d.device_type.manufacturer && d.device_type.manufacturer.name) || 'Unknown';
        if (!mfrMap[mfr]) mfrMap[mfr] = { total: 0, operating: 0, idle: 0 };
        mfrMap[mfr].total++;
        if (d.role && d.role.name === 'IDLE') {
            mfrMap[mfr].idle++;
        } else {
            mfrMap[mfr].operating++;
        }
    });
    // 전체 수량 내림차순 정렬
    var sorted = Object.keys(mfrMap).map(function(k) { return { name: k, data: mfrMap[k] }; })
        .sort(function(a, b) { return b.data.total - a.data.total; });
    // 합계 계산
    var sumTotal = 0, sumOp = 0, sumIdle = 0;
    sorted.forEach(function(m) { sumTotal += m.data.total; sumOp += m.data.operating; sumIdle += m.data.idle; });

    var html = '';
    sorted.forEach(function(m) {
        var idleRate = m.data.total > 0 ? (m.data.idle / m.data.total * 100).toFixed(1) : '0.0';
        var rateColor = parseFloat(idleRate) > 30 ? '#c62828' : (parseFloat(idleRate) > 15 ? '#e65100' : '#10b981');
        html += '<tr style="border-bottom:1px solid #f5f5f5;">' +
            '<td class="py-2" style="font-weight:600;">' + esc(m.name) + '</td>' +
            '<td class="text-center py-2" style="font-weight:700;">' + fmtNum(m.data.total) + '</td>' +
            '<td class="text-center py-2" style="color:#10b981;font-weight:600;">' + fmtNum(m.data.operating) + '</td>' +
            '<td class="text-center py-2" style="color:#f59e0b;font-weight:600;">' + fmtNum(m.data.idle) + '</td>' +
            '<td class="text-center py-2" style="color:' + rateColor + ';font-weight:600;">' + idleRate + '%</td></tr>';
    });
    // 합계 행
    var totalIdleRate = sumTotal > 0 ? (sumIdle / sumTotal * 100).toFixed(1) : '0.0';
    html += '<tr style="border-top:2px solid #e0e0e0;background:' + T('#f9fafb', '#253347') + ';">' +
        '<td class="py-2" style="font-weight:700;">합계</td>' +
        '<td class="text-center py-2" style="font-weight:800;">' + fmtNum(sumTotal) + '</td>' +
        '<td class="text-center py-2" style="color:#10b981;font-weight:700;">' + fmtNum(sumOp) + '</td>' +
        '<td class="text-center py-2" style="color:#f59e0b;font-weight:700;">' + fmtNum(sumIdle) + '</td>' +
        '<td class="text-center py-2" style="font-weight:700;">' + totalIdleRate + '%</td></tr>';
    tbody.innerHTML = html;
}

// ========== 유휴자산 제조사·모델별 보유수량 테이블 ==========
function renderIdleAssetTable(results) {
    var tbody = document.getElementById('idleAssetTableBody');
    if (!tbody) return;
    // 유휴장비만 필터
    var idleDevices = (results || []).filter(function(d) { return d.role && d.role.name === 'IDLE'; });
    if (idleDevices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center py-3" style="color:#ccc;font-size:0.75rem;">유휴자산 없음</td></tr>';
        return;
    }
    // 제조사·모델별 집계
    var groupMap = {};
    idleDevices.forEach(function(d) {
        var mfr = (d.device_type && d.device_type.manufacturer && d.device_type.manufacturer.name) || 'Unknown';
        var model = (d.device_type && d.device_type.model) || 'Unknown';
        var key = mfr + '|||' + model;
        groupMap[key] = (groupMap[key] || 0) + 1;
    });
    // 제조사명 → 수량 내림차순 정렬
    var sorted = Object.keys(groupMap).map(function(k) {
        var parts = k.split('|||');
        return { mfr: parts[0], model: parts[1], count: groupMap[k] };
    }).sort(function(a, b) {
        if (a.mfr !== b.mfr) return a.mfr.localeCompare(b.mfr);
        return b.count - a.count;
    });

    var html = '';
    var prevMfr = '';
    sorted.forEach(function(item) {
        var showMfr = item.mfr !== prevMfr;
        html += '<tr style="border-bottom:1px solid #f5f5f5;">' +
            '<td class="py-2" style="font-weight:' + (showMfr ? '600' : '400') + ';">' + (showMfr ? esc(item.mfr) : '') + '</td>' +
            '<td class="py-2">' + esc(item.model) + '</td>' +
            '<td class="text-center py-2" style="font-weight:700;color:#f59e0b;">' + item.count + '</td></tr>';
        prevMfr = item.mfr;
    });
    // 합계 행
    html += '<tr style="border-top:2px solid #e0e0e0;background:' + T('#f9fafb', '#253347') + ';">' +
        '<td class="py-2" style="font-weight:700;" colspan="2">합계</td>' +
        '<td class="text-center py-2" style="font-weight:800;color:#f59e0b;">' + idleDevices.length + '</td></tr>';
    tbody.innerHTML = html;
}

// ========== 최근 12개월 월별 매출 추이 ==========
function loadRevenueTrend() {
    var now = new Date();
    var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    fetch('/revenue_summary/get_revenue_monthly?year_month=' + ym, { signal: AbortSignal.timeout(15000) })
        .then(function(res) { return res.json(); })
        .then(function(resp) {
            if (resp.success && resp.trend) {
                renderRevenueTrendChart(resp.trend);
            }
        })
        .catch(function(err) {
            console.error('Revenue trend load error:', err);
            var el = document.getElementById('chartRevenueTrend');
            if (el) showNoData(el);
        });
}

function renderRevenueTrendChart(trend) {
    var el = document.getElementById('chartRevenueTrend');
    if (!el || !trend || trend.length === 0) { showNoData(el); return; }
    var chart = initChart(el, 'chartRevenueTrend');

    var months = trend.map(function(t) { return t.month; });
    var ordData = trend.map(function(t) { return Number(t.ord_total) || 0; });
    var mprData = trend.map(function(t) { return Number(t.mpr_total) || 0; });
    var totalData = trend.map(function(t) { return Number(t.grand_total) || 0; });
    var circuitData = trend.map(function(t) { return Number(t.circuit_count) || 0; });

    chart.setOption({
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                var lines = ['<b>' + params[0].axisValue + '</b>'];
                params.forEach(function(p) {
                    if (p.seriesName === '유효 회선수') {
                        lines.push(p.marker + ' ' + p.seriesName + ': ' + Number(p.value).toLocaleString() + '건');
                    } else {
                        lines.push(p.marker + ' ' + p.seriesName + ': ' + Number(p.value).toLocaleString() + '원');
                    }
                });
                return lines.join('<br>');
            }
        },
        legend: {
            bottom: 0,
            textStyle: { fontSize: 11, color: T('#999', '#94a3b8') },
            data: ['ORD 매출', 'MPR 매출', '합계', '유효 회선수']
        },
        grid: { left: 10, right: 50, top: 15, bottom: 36, containLabel: true },
        xAxis: {
            type: 'category',
            data: months,
            axisLine: { lineStyle: { color: T('#f0f0f0', '#2d3d50') } },
            axisTick: { show: false },
            axisLabel: {
                fontSize: 10, color: T('#999', '#94a3b8'),
                formatter: function(v) { var parts = v.split('-'); return parts[0].substring(2) + '.' + parts[1]; }
            }
        },
        yAxis: [
            {
                type: 'value', position: 'left',
                axisLine: { show: false }, axisTick: { show: false },
                splitLine: { lineStyle: { color: T('#f5f5f5', '#2d3d50') } },
                axisLabel: {
                    fontSize: 10, color: T('#ccc', '#64748b'),
                    formatter: function(v) {
                        if (v >= 100000000) return (v / 100000000).toFixed(1) + '억';
                        if (v >= 10000) return Math.round(v / 10000).toLocaleString() + '만';
                        return v;
                    }
                }
            },
            {
                type: 'value', position: 'right',
                axisLine: { show: false }, axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { fontSize: 10, color: T('#ccc', '#64748b'), formatter: '{value}건' }
            }
        ],
        series: [
            {
                name: 'ORD 매출', type: 'bar', stack: 'revenue', yAxisIndex: 0,
                data: ordData, barWidth: 18,
                itemStyle: { color: C.green, borderRadius: [0, 0, 0, 0] }
            },
            {
                name: 'MPR 매출', type: 'bar', stack: 'revenue', yAxisIndex: 0,
                data: mprData, barWidth: 18,
                itemStyle: { color: C.blue, borderRadius: [3, 3, 0, 0] }
            },
            {
                name: '합계', type: 'line', yAxisIndex: 0,
                data: totalData,
                lineStyle: { color: '#ff9f43', width: 2, type: 'dashed' },
                itemStyle: { color: '#ff9f43' },
                symbol: 'circle', symbolSize: 5,
                label: {
                    show: true, position: 'top', fontSize: 9, color: T('#999', '#94a3b8'),
                    formatter: function(p) { return fmtWon(p.value); }
                }
            },
            {
                name: '유효 회선수', type: 'line', yAxisIndex: 1,
                data: circuitData,
                lineStyle: { color: '#a855f7', width: 1.5 },
                itemStyle: { color: '#a855f7' },
                symbol: 'diamond', symbolSize: 5
            }
        ]
    });
}

// ========== 유틸리티 ==========
function initChart(el, key) {
    if (chartInstances[key]) chartInstances[key].dispose();
    var c = echarts.init(el);
    chartInstances[key] = c;
    return c;
}

function setText(id, t) { var el = document.getElementById(id); if (el) el.textContent = t; }
function fmtNum(n) { return (n === null || n === undefined) ? '-' : Number(n).toLocaleString(); }
function fmtWon(n) {
    if (n === null || n === undefined) return '-';
    if (n >= 100000000) return (n / 100000000).toFixed(1) + '억';
    if (n >= 10000) return Math.round(n / 10000).toLocaleString() + '만';
    return Number(n).toLocaleString() + '원';
}
function fmtPtp(v) { return (v === undefined || v === null) ? '-' : (typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : esc(String(v))); }
function fmtCont(v) { return (v === undefined || v === null) ? '-' : Number(v).toFixed(1) + '%'; }
function esc(s) { return !s ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function showNoData(el) { if (el) el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#ccc;font-size:0.8rem;">데이터 없음</div>'; }
function setTableEmpty(id, cols) { var el = document.getElementById(id); if (el) el.innerHTML = '<tr><td colspan="' + cols + '" class="text-center py-3" style="color:#ccc;font-size:0.75rem;">데이터 없음</td></tr>'; }

window.addEventListener('resize', function() {
    Object.keys(chartInstances).forEach(function(k) { if (chartInstances[k]) chartInstances[k].resize(); });
});

// 테마 변경 감지 → 차트 색상 재적용
var _themeObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
        if (m.attributeName === 'data-bs-theme') {
            loadDashboard();
        }
    });
});
_themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
