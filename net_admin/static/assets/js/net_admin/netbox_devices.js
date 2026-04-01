(function () {
    'use strict';

    var devicesTable = null;
    var NETBOX_BASE = 'http://172.25.32.221';
    var DEFAULT_MANUFACTURERS = ['arista', 'CISCO', 'JUNIPER', 'F5'];
    var _formMode = 'create'; // 'create' or 'edit'
    var _cachedFilters = null; // roles, manufacturers, sites

    var STATUS_COLORS = {
        'active': { bg: '#dcfce7', color: '#166534', label: 'Active' },
        'planned': { bg: '#dbeafe', color: '#1e40af', label: 'Planned' },
        'staged': { bg: '#fef3c7', color: '#92400e', label: 'Staged' },
        'failed': { bg: '#fce4ec', color: '#c62828', label: 'Failed' },
        'offline': { bg: '#f3f4f6', color: '#6b7280', label: 'Offline' },
        'decommissioning': { bg: '#fce4ec', color: '#c62828', label: 'Decommissioning' }
    };

    var ROLE_COLORS = {
        'PRD': { bg: '#dcfce7', color: '#166534' },
        'TST': { bg: '#fef3c7', color: '#92400e' },
        'DR': { bg: '#fae8ff', color: '#7e22ce' },
        'DEV': { bg: '#dbeafe', color: '#1e40af' },
        'IDLE': { bg: '#f3f4f6', color: '#6b7280' }
    };

    // ========== 필터 초기화 ==========
    function initFilters() {
        $.getJSON('/netbox_devices/get_netbox_filters', function(resp) {
            if (!resp.success) return;
            _cachedFilters = resp.data;
            var d = resp.data;
            var roleSel = $('#filterRole');
            d.roles.forEach(function(r) {
                roleSel.append('<option value="' + r.slug + '">' + esc(r.name) + '</option>');
            });
            var mfrSel = $('#filterManufacturer');
            d.manufacturers.forEach(function(m) {
                mfrSel.append('<option value="' + m.slug + '">' + esc(m.name) + '</option>');
            });
            var siteSel = $('#filterSite');
            d.sites.forEach(function(s) {
                var label = s.name + (s.description ? ' - ' + s.description.substring(0, 30) : '');
                siteSel.append('<option value="' + s.slug + '">' + esc(label) + '</option>');
            });
        });
    }

    function buildAjaxUrl() {
        var params = [];
        var role = $('#filterRole').val();
        var mfr = $('#filterManufacturer').val();
        var site = $('#filterSite').val();
        var status = $('#filterStatus').val();
        if (role) params.push('role=' + encodeURIComponent(role));
        if (mfr) {
            params.push('manufacturer=' + encodeURIComponent(mfr));
        } else {
            DEFAULT_MANUFACTURERS.forEach(function(m) {
                params.push('manufacturer=' + encodeURIComponent(m));
            });
        }
        if (site) params.push('site=' + encodeURIComponent(site));
        if (status) params.push('status=' + encodeURIComponent(status));
        params.push('limit=2000');
        return '/netbox_devices/get_netbox_devices?' + params.join('&');
    }

    // ========== DataTable ==========
    function initTable() {
        devicesTable = $('#devicesTable').DataTable({
            responsive: true,
            paging: true,
            pageLength: 50,
            searching: true,
            ordering: true,
            order: [[0, 'asc']],
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
                    title: 'NetBox_Devices_' + new Date().toISOString().slice(0, 10),
                    exportOptions: { columns: [0,1,2,3,4,5,6,7,8,9], modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: 'NetBox_Devices_' + new Date().toISOString().slice(0, 10),
                    exportOptions: { columns: [0,1,2,3,4,5,6,7,8,9], modifier: { page: 'all' } }
                }
            ],
            ajax: {
                url: buildAjaxUrl(),
                type: 'GET',
                dataSrc: function(json) {
                    if (json.success && json.data) {
                        updateSummary(json.data);
                        return json.data.results || [];
                    }
                    showAlert('데이터 로드 실패', 'danger');
                    return [];
                },
                error: function() {
                    showAlert('NetBox 데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'name', defaultContent: '-' },
                { data: 'status', defaultContent: '-' },
                { data: 'role', defaultContent: '-' },
                { data: 'device_type', defaultContent: '-' },
                { data: 'device_type', defaultContent: '-' },
                { data: 'site', defaultContent: '-' },
                { data: 'location', defaultContent: '-' },
                { data: 'rack', defaultContent: '-' },
                { data: 'primary_ip', defaultContent: '-' },
                { data: 'interface_count', defaultContent: '0' },
                { data: null, defaultContent: '' }
            ],
            columnDefs: [
                {
                    targets: 0, className: 'py-2 align-middle',
                    render: function(data) { return data ? '<span class="fw-semibold">' + esc(data) + '</span>' : '-'; }
                },
                {
                    targets: 1, className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data || !data.value) return '-';
                        var s = STATUS_COLORS[data.value] || { bg: '#f3f4f6', color: '#6b7280', label: data.label };
                        return '<span class="badge" style="background:' + s.bg + ';color:' + s.color + ';font-size:0.72rem;font-weight:600;">' + esc(s.label || data.label) + '</span>';
                    }
                },
                {
                    targets: 2, className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data || !data.name) return '-';
                        var r = ROLE_COLORS[data.name] || { bg: '#f3f4f6', color: '#6b7280' };
                        return '<span class="badge" style="background:' + r.bg + ';color:' + r.color + ';font-size:0.72rem;font-weight:600;">' + esc(data.name) + '</span>';
                    }
                },
                {
                    targets: 3, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data && data.manufacturer && data.manufacturer.name) ? esc(data.manufacturer.name) : '-'; }
                },
                {
                    targets: 4, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data && data.model) ? esc(data.model) : '-'; }
                },
                {
                    targets: 5, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data && data.name) ? esc(data.name) : '-'; }
                },
                {
                    targets: 6, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data && data.name) ? esc(data.name) : '-'; }
                },
                {
                    targets: 7, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data && data.name) ? esc(data.name) : '-'; }
                },
                {
                    targets: 8, className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data || !data.address) return '-';
                        return '<code style="font-size:0.78rem;">' + esc(data.address) + '</code>';
                    }
                },
                {
                    targets: 9, className: 'text-center py-2 align-middle',
                    render: function(data) { return (data !== null && data !== undefined) ? data : '0'; }
                },
                {
                    targets: 10, className: 'text-center py-2 align-middle', orderable: false, searchable: false,
                    render: function(data, type, row) {
                        return '<button class="btn-edit" title="수정" data-id="' + row.id + '" style="width:26px; height:26px; border:none; border-radius:6px; background:#f1f5f9; color:#64748b; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; margin-right:4px; transition:all 0.15s ease;" onmouseenter="this.style.background=\'#dbeafe\';this.style.color=\'#3b82f6\'" onmouseleave="this.style.background=\'#f1f5f9\';this.style.color=\'#64748b\'"><i class="fas fa-pen" style="font-size:0.6rem;"></i></button>' +
                               '<button class="btn-delete" title="삭제" data-id="' + row.id + '" style="width:26px; height:26px; border:none; border-radius:6px; background:#f1f5f9; color:#64748b; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:all 0.15s ease;" onmouseenter="this.style.background=\'#fee2e2\';this.style.color=\'#ef4444\'" onmouseleave="this.style.background=\'#f1f5f9\';this.style.color=\'#64748b\'"><i class="fas fa-trash" style="font-size:0.6rem;"></i></button>';
                    }
                }
            ],
            initComplete: function() {
                removeOverlay();
            }
        });

        // Footer column search (exclude last action column)
        $('#devicesTable tfoot th').each(function(idx) {
            if (idx >= 10) return; // skip action column
            var title = $(this).text();
            $(this).css({ 'font-size': '0.7rem', 'white-space': 'nowrap' });
            $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.7rem; padding:2px 4px;" />');
        });

        devicesTable.columns().every(function(idx) {
            if (idx >= 10) return;
            var that = this;
            $('input', this.footer()).on('keyup change', function() {
                if (that.search() !== this.value) {
                    that.search(this.value).draw();
                }
            });
        });

        // Row click → detail modal (but not on action buttons)
        $('#devicesTable tbody').css('cursor', 'pointer');
        $('#devicesTable tbody').on('click', 'tr', function(e) {
            if ($(e.target).closest('.btn-edit, .btn-delete').length) return;
            var data = devicesTable.row(this).data();
            if (data) showDetailModal(data);
        });

        // Edit button
        $('#devicesTable tbody').on('click', '.btn-edit', function(e) {
            e.stopPropagation();
            var id = $(this).data('id');
            var data = devicesTable.rows().data().toArray().find(function(r) { return r.id === id; });
            if (data) showEditModal(data);
        });

        // Delete button
        $('#devicesTable tbody').on('click', '.btn-delete', function(e) {
            e.stopPropagation();
            var id = $(this).data('id');
            var data = devicesTable.rows().data().toArray().find(function(r) { return r.id === id; });
            if (data) deleteDevice(data);
        });
    }

    // ========== Summary ==========
    function updateSummary(data) {
        var total = data.count || 0;
        var results = data.results || [];
        var active = 0;
        var idle = 0;
        var operating = 0;
        var roleCounts = {};
        var siteSet = {};
        var mfrMap = {};
        var modelCounts = {};
        var idleModels = {};

        results.forEach(function(d) {
            if (d.status && d.status.value === 'active') active++;
            var isIdle = d.role && d.role.name === 'IDLE';
            if (isIdle) { idle++; } else { operating++; }
            if (d.role && d.role.name) roleCounts[d.role.name] = (roleCounts[d.role.name] || 0) + 1;
            if (d.site && d.site.name) siteSet[d.site.name] = true;
            // 제조사별 집계
            var mfr = (d.device_type && d.device_type.manufacturer && d.device_type.manufacturer.name) || 'Unknown';
            if (!mfrMap[mfr]) mfrMap[mfr] = { total: 0, operating: 0, idle: 0 };
            mfrMap[mfr].total++;
            if (isIdle) { mfrMap[mfr].idle++; } else { mfrMap[mfr].operating++; }
            // 모델별 수량 집계
            var modelName = (d.device_type && d.device_type.model) || 'Unknown';
            var modelKey = mfr + '|||' + modelName;
            if (!modelCounts[modelKey]) modelCounts[modelKey] = 0;
            modelCounts[modelKey]++;
            // 유휴 모델별 집계
            if (isIdle) {
                var key = mfr + '|||' + modelName;
                idleModels[key] = (idleModels[key] || 0) + 1;
            }
        });

        // KPI 카드 업데이트
        $('#stat_total').text(total.toLocaleString());
        $('#stat_operating').text(operating.toLocaleString());
        $('#stat_idle').text(idle.toLocaleString());
        $('#stat_active').text(active.toLocaleString());
        var idleRate = total > 0 ? (idle / total * 100).toFixed(1) + '%' : '0%';
        $('#stat_idle_rate').text(idleRate);
        $('#stat_sites').text(Object.keys(siteSet).length);

        // 제조사별 현황 렌더링
        renderMfrSummary(mfrMap, total);

        // 장비모델별 수량 렌더링
        renderModelSummary(modelCounts, total);

        // 역할별 분포 렌더링
        renderRoleSummary(roleCounts, total);

        // 유휴 Top 모델 렌더링
        renderIdleTopModels(idleModels, idle);
    }

    function renderMfrSummary(mfrMap, total) {
        var el = document.getElementById('mfrSummaryArea');
        if (!el) return;
        var sorted = Object.keys(mfrMap).map(function(k) { return { name: k, d: mfrMap[k] }; })
            .sort(function(a, b) { return b.d.total - a.d.total; });
        if (sorted.length === 0) { el.innerHTML = '<div class="text-center py-2" style="color:#ccc;">데이터 없음</div>'; return; }
        var maxTotal = sorted[0].d.total;
        var html = '';
        sorted.forEach(function(m) {
            var pct = total > 0 ? (m.d.total / total * 100).toFixed(1) : 0;
            var barW = maxTotal > 0 ? Math.round(m.d.total / maxTotal * 100) : 0;
            html += '<div class="d-flex align-items-center mb-2">' +
                '<span style="min-width:68px;font-weight:600;font-size:0.75rem;">' + esc(m.name) + '</span>' +
                '<div class="flex-grow-1 mx-2" style="height:18px;background:#f1f5f9;border-radius:9px;overflow:hidden;position:relative;">' +
                '<div style="position:absolute;top:0;left:0;height:100%;width:' + barW + '%;background:linear-gradient(90deg,#6366f1,#818cf8);border-radius:9px;transition:width 0.5s;"></div>' +
                '</div>' +
                '<span style="min-width:125px;text-align:right;font-size:0.72rem;white-space:nowrap;">' +
                '<b>' + m.d.total + '</b>' +
                '<span style="color:#10b981;margin-left:6px;">' + m.d.operating + '</span>' +
                '<span style="color:#f59e0b;margin-left:6px;">' + m.d.idle + '</span>' +
                '<span style="color:#94a3b8;margin-left:4px;font-size:0.65rem;">(' + pct + '%)</span>' +
                '</span></div>';
        });
        el.innerHTML = html;
    }

    function renderModelSummary(modelCounts, total) {
        var el = document.getElementById('modelSummaryArea');
        if (!el) return;
        var sorted = Object.keys(modelCounts).map(function(k) {
            var parts = k.split('|||');
            return { mfr: parts[0], model: parts[1], count: modelCounts[k] };
        }).sort(function(a, b) { return b.count - a.count; });
        if (sorted.length === 0) { el.innerHTML = '<div class="text-center py-2" style="color:#ccc;">데이터 없음</div>'; return; }
        var maxCount = sorted[0].count;
        var html = '';
        sorted.forEach(function(item) {
            var barW = maxCount > 0 ? Math.round(item.count / maxCount * 100) : 0;
            html += '<div class="d-flex align-items-center mb-1" style="line-height:1.3;">' +
                '<span style="min-width:100px;font-size:0.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="' + esc(item.model) + '">' + esc(item.model) + '</span>' +
                '<div class="flex-grow-1 mx-2" style="height:14px;background:#f1f5f9;border-radius:7px;overflow:hidden;position:relative;">' +
                '<div style="position:absolute;top:0;left:0;height:100%;width:' + barW + '%;background:linear-gradient(90deg,#10b981,#6ee7b7);border-radius:7px;transition:width 0.5s;"></div>' +
                '</div>' +
                '<span style="min-width:28px;text-align:right;font-size:0.72rem;font-weight:700;">' + item.count + '</span>' +
                '</div>';
        });
        el.innerHTML = html;
    }

    function renderRoleSummary(roleCounts, total) {
        var el = document.getElementById('roleSummaryArea');
        if (!el) return;
        var roleColors = { 'PRD': '#10b981', 'TST': '#f59e0b', 'DR': '#a855f7', 'DEV': '#3b82f6', 'IDLE': '#6b7280' };
        var sorted = Object.keys(roleCounts).map(function(k) { return { name: k, count: roleCounts[k] }; })
            .sort(function(a, b) { return b.count - a.count; });
        if (sorted.length === 0) { el.innerHTML = '<div class="text-center py-2" style="color:#ccc;">데이터 없음</div>'; return; }
        var html = '';
        sorted.forEach(function(r) {
            var c = roleColors[r.name] || '#6b7280';
            var pct = total > 0 ? (r.count / total * 100).toFixed(1) : 0;
            html += '<div class="d-flex align-items-center mb-2">' +
                '<span style="width:10px;height:10px;min-width:10px;border-radius:50%;background:' + c + ';margin-right:8px;"></span>' +
                '<span style="font-size:0.75rem;font-weight:600;">' + esc(r.name) + '</span>' +
                '<span class="ms-auto" style="font-size:0.75rem;font-weight:700;">' + r.count + '</span>' +
                '<span style="font-size:0.65rem;color:#94a3b8;min-width:42px;text-align:right;">(' + pct + '%)</span></div>';
        });
        el.innerHTML = html;
    }

    function renderIdleTopModels(idleModels, idleTotal) {
        var el = document.getElementById('idleTopModelArea');
        if (!el) return;
        var sorted = Object.keys(idleModels).map(function(k) {
            var parts = k.split('|||');
            return { mfr: parts[0], model: parts[1], count: idleModels[k] };
        }).sort(function(a, b) { return b.count - a.count; }).slice(0, 6);
        if (sorted.length === 0) { el.innerHTML = '<div class="text-center py-2" style="color:#ccc;">유휴자산 없음</div>'; return; }
        var maxCount = sorted[0].count;
        var html = '';
        sorted.forEach(function(item) {
            var barW = maxCount > 0 ? Math.round(item.count / maxCount * 100) : 0;
            html += '<div class="d-flex align-items-center mb-2">' +
                '<span style="min-width:110px;font-size:0.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="' + esc(item.mfr) + ' / ' + esc(item.model) + '">' +
                '<span style="color:#94a3b8;">' + esc(item.mfr) + '</span> ' + esc(item.model) + '</span>' +
                '<div class="flex-grow-1 mx-2" style="height:14px;background:#fef3c7;border-radius:7px;overflow:hidden;">' +
                '<div style="height:100%;width:' + barW + '%;background:linear-gradient(90deg,#f59e0b,#fbbf24);border-radius:7px;transition:width 0.5s;"></div>' +
                '</div>' +
                '<span style="font-size:0.75rem;font-weight:700;min-width:28px;text-align:right;">' + item.count + '</span></div>';
        });
        if (idleTotal > 0) {
            html += '<div class="text-end mt-1" style="font-size:0.65rem;color:#94a3b8;">총 유휴 ' + idleTotal + '대</div>';
        }
        el.innerHTML = html;
    }

    // ========== Detail Modal ==========
    function showDetailModal(d) {
        var title = d.name || '디바이스 상세';
        $('#modalTitle').text(title);
        var statusBadge = '-';
        if (d.status) {
            var s = STATUS_COLORS[d.status.value] || { bg: '#f3f4f6', color: '#6b7280' };
            statusBadge = '<span class="badge" style="background:' + s.bg + ';color:' + s.color + ';">' + esc(d.status.label) + '</span>';
        }
        var html = '<div class="row g-4">';
        html += '<div class="col-md-6">';
        html += '<h6 class="fw-bold mb-3" style="font-size:0.85rem;"><i class="fas fa-info-circle me-2 text-primary"></i>기본 정보</h6>';
        html += infoRow('디바이스명', d.name);
        html += infoRow('상태', statusBadge, true);
        html += infoRow('역할', d.role ? d.role.name : '-');
        html += infoRow('제조사', d.device_type ? (d.device_type.manufacturer ? d.device_type.manufacturer.name : '-') : '-');
        html += infoRow('모델', d.device_type ? d.device_type.model : '-');
        html += infoRow('시리얼', d.serial || '-');
        html += infoRow('설명', d.description || '-');
        html += '</div>';
        html += '<div class="col-md-6">';
        html += '<h6 class="fw-bold mb-3" style="font-size:0.85rem;"><i class="fas fa-map-marker-alt me-2 text-success"></i>위치 정보</h6>';
        html += infoRow('사이트', d.site ? (d.site.name + (d.site.description ? ' (' + d.site.description + ')' : '')) : '-');
        html += infoRow('위치', d.location ? d.location.name : '-');
        html += infoRow('랙', d.rack ? d.rack.display : '-');
        html += infoRow('포지션', d.position != null ? d.position : '-');
        html += infoRow('면', d.face ? d.face.label : '-');
        html += '</div>';
        html += '<div class="col-md-6">';
        html += '<h6 class="fw-bold mb-3" style="font-size:0.85rem;"><i class="fas fa-network-wired me-2 text-warning"></i>네트워크</h6>';
        html += infoRow('Primary IP', d.primary_ip ? d.primary_ip.address : '-');
        html += infoRow('OOB IP', d.oob_ip ? d.oob_ip.address : '-');
        html += infoRow('인터페이스 수', d.interface_count != null ? d.interface_count : '-');
        html += '</div>';
        html += '<div class="col-md-6">';
        html += '<h6 class="fw-bold mb-3" style="font-size:0.85rem;"><i class="fas fa-clock me-2 text-info"></i>메타 정보</h6>';
        html += infoRow('등록일', d.created ? d.created.substring(0, 10) : '-');
        html += infoRow('수정일', d.last_updated ? d.last_updated.substring(0, 10) : '-');
        if (d.tags && d.tags.length > 0) {
            var tagHtml = d.tags.map(function(t) {
                return '<span class="badge bg-secondary me-1" style="font-size:0.7rem;">' + esc(t.name || t.display) + '</span>';
            }).join('');
            html += infoRow('태그', tagHtml, true);
        }
        html += '</div></div>';
        $('#modalBody').html(html);
        $('#modalNetboxLink').attr('href', NETBOX_BASE + '/dcim/devices/' + d.id + '/');
        new bootstrap.Modal(document.getElementById('deviceDetailModal')).show();
    }

    function infoRow(label, value, isHtml) {
        return '<div class="d-flex mb-2" style="font-size:0.82rem;">' +
            '<span style="min-width:100px;color:#8c8c8c;font-weight:500;">' + label + '</span>' +
            '<span class="fw-semibold">' + (isHtml ? value : esc(String(value || '-'))) + '</span></div>';
    }

    // ========== CRUD: Create ==========
    window.showCreateModal = function() {
        _formMode = 'create';
        $('#formModalTitle').text('디바이스 추가');
        $('#deviceForm')[0].reset();
        $('#form_device_id').val('');
        $('#form_status').val('active');
        loadFormDropdowns();
        new bootstrap.Modal(document.getElementById('deviceFormModal')).show();
    };

    // ========== CRUD: Edit ==========
    function showEditModal(d) {
        _formMode = 'edit';
        $('#formModalTitle').text('디바이스 수정');
        $('#form_device_id').val(d.id);
        $('#form_name').val(d.name || '');
        $('#form_status').val(d.status ? d.status.value : 'active');
        $('#form_serial').val(d.serial || '');
        $('#form_description').val(d.description || '');
        $('#form_position').val(d.position || '');
        $('#form_face').val(d.face && d.face.value ? d.face.value : '');

        loadFormDropdowns(function() {
            // Set role
            if (d.role) $('#form_role').val(d.role.id);
            // Set manufacturer & load device types
            if (d.device_type && d.device_type.manufacturer) {
                $('#form_manufacturer').val(d.device_type.manufacturer.id);
                loadDeviceTypes(d.device_type.manufacturer.id, function() {
                    if (d.device_type) $('#form_device_type').val(d.device_type.id);
                });
            }
            // Set site & load locations
            if (d.site) {
                $('#form_site').val(d.site.id);
                loadLocations(d.site.id, function() {
                    if (d.location) {
                        $('#form_location').val(d.location.id);
                        loadRacks(d.site.id, d.location.id, function() {
                            if (d.rack) $('#form_rack').val(d.rack.id);
                        });
                    }
                });
            }
        });
        new bootstrap.Modal(document.getElementById('deviceFormModal')).show();
    }

    // ========== CRUD: Save (Create or Edit) ==========
    window.saveDevice = function() {
        var roleId = $('#form_role').val();
        var deviceTypeId = $('#form_device_type').val();
        var siteId = $('#form_site').val();

        if (!roleId || !deviceTypeId || !siteId) {
            showAlert('역할, 모델(디바이스 타입), 사이트는 필수입니다.', 'warning');
            return;
        }

        var payload = {
            name: $('#form_name').val().trim() || null,
            status: $('#form_status').val(),
            role: parseInt(roleId),
            device_type: parseInt(deviceTypeId),
            site: parseInt(siteId),
            serial: $('#form_serial').val().trim() || '',
            description: $('#form_description').val().trim() || ''
        };

        var locId = $('#form_location').val();
        if (locId) payload.location = parseInt(locId);
        var rackId = $('#form_rack').val();
        if (rackId) payload.rack = parseInt(rackId);
        var pos = $('#form_position').val();
        if (pos) payload.position = parseFloat(pos);
        var face = $('#form_face').val();
        if (face) payload.face = face;

        var url, verb;
        if (_formMode === 'edit') {
            var devId = $('#form_device_id').val();
            url = '/netbox_devices/update_netbox_device/' + devId;
        } else {
            url = '/netbox_devices/create_netbox_device';
        }

        $('#btnSaveDevice').prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-1"></span>저장 중...');

        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(res) { return res.json().then(function(d) { return { status: res.status, body: d }; }); })
        .then(function(resp) {
            $('#btnSaveDevice').prop('disabled', false).html('<i class="fas fa-save me-1"></i>저장');
            if (resp.body.success) {
                showAlert(_formMode === 'edit' ? '수정 완료' : '등록 완료', 'success');
                bootstrap.Modal.getInstance(document.getElementById('deviceFormModal')).hide();
                refreshTable();
            } else {
                var errMsg = formatError(resp.body.detail || resp.body.error || '저장 실패');
                showAlert(errMsg, 'danger');
            }
        })
        .catch(function() {
            $('#btnSaveDevice').prop('disabled', false).html('<i class="fas fa-save me-1"></i>저장');
            showAlert('저장 중 오류가 발생했습니다.', 'danger');
        });
    };

    // ========== CRUD: Delete ==========
    function deleteDevice(d) {
        var name = d.name || 'ID ' + d.id;
        if (!confirm(name + ' 디바이스를 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.')) return;

        fetch('/netbox_devices/delete_netbox_device/' + d.id, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        })
        .then(function(res) { return res.json(); })
        .then(function(resp) {
            if (resp.success) {
                showAlert(name + ' 삭제 완료', 'success');
                refreshTable();
            } else {
                showAlert('삭제 실패: ' + (resp.error || resp.detail || ''), 'danger');
            }
        })
        .catch(function() {
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    }

    // ========== Form Dropdown Loaders ==========
    function loadFormDropdowns(cb) {
        if (_cachedFilters) {
            populateFormSelects(_cachedFilters);
            if (cb) cb();
            return;
        }
        $.getJSON('/netbox_devices/get_netbox_filters', function(resp) {
            if (resp.success) {
                _cachedFilters = resp.data;
                populateFormSelects(resp.data);
            }
            if (cb) cb();
        });
    }

    function populateFormSelects(data) {
        var roleSel = $('#form_role');
        roleSel.find('option:not(:first)').remove();
        data.roles.forEach(function(r) {
            roleSel.append('<option value="' + r.id + '">' + esc(r.name) + '</option>');
        });

        var mfrSel = $('#form_manufacturer');
        mfrSel.find('option:not(:first)').remove();
        data.manufacturers.forEach(function(m) {
            mfrSel.append('<option value="' + m.id + '">' + esc(m.name) + '</option>');
        });

        var siteSel = $('#form_site');
        siteSel.find('option:not(:first)').remove();
        data.sites.forEach(function(s) {
            siteSel.append('<option value="' + s.id + '">' + esc(s.name) + '</option>');
        });

        // Reset dependent selects
        $('#form_device_type').html('<option value="">제조사를 먼저 선택</option>');
        $('#form_location').html('<option value="">사이트를 먼저 선택</option>');
        $('#form_rack').html('<option value="">위치를 먼저 선택</option>');
    }

    function loadDeviceTypes(mfrId, cb) {
        var sel = $('#form_device_type');
        sel.html('<option value="">로딩 중...</option>');
        $.getJSON('/netbox_devices/get_netbox_device_types?manufacturer_id=' + mfrId, function(resp) {
            sel.html('<option value="">선택</option>');
            if (resp.success) {
                resp.data.forEach(function(dt) {
                    sel.append('<option value="' + dt.id + '">' + esc(dt.model) + '</option>');
                });
            }
            if (cb) cb();
        });
    }

    function loadLocations(siteId, cb) {
        var sel = $('#form_location');
        sel.html('<option value="">로딩 중...</option>');
        $.getJSON('/netbox_devices/get_netbox_locations?site_id=' + siteId, function(resp) {
            sel.html('<option value="">선택 (없음)</option>');
            if (resp.success) {
                resp.data.forEach(function(loc) {
                    sel.append('<option value="' + loc.id + '">' + esc(loc.name) + '</option>');
                });
            }
            if (cb) cb();
        });
    }

    function loadRacks(siteId, locationId, cb) {
        var sel = $('#form_rack');
        sel.html('<option value="">로딩 중...</option>');
        var url = '/netbox_devices/get_netbox_racks?site_id=' + siteId;
        if (locationId) url += '&location_id=' + locationId;
        $.getJSON(url, function(resp) {
            sel.html('<option value="">선택 (없음)</option>');
            if (resp.success) {
                resp.data.forEach(function(r) {
                    sel.append('<option value="' + r.id + '">' + esc(r.name) + '</option>');
                });
            }
            if (cb) cb();
        });
    }

    // Cascading dropdown events
    $(document).on('change', '#form_manufacturer', function() {
        var mfrId = $(this).val();
        if (mfrId) {
            loadDeviceTypes(mfrId);
        } else {
            $('#form_device_type').html('<option value="">제조사를 먼저 선택</option>');
        }
    });

    $(document).on('change', '#form_site', function() {
        var siteId = $(this).val();
        $('#form_rack').html('<option value="">위치를 먼저 선택</option>');
        if (siteId) {
            loadLocations(siteId);
        } else {
            $('#form_location').html('<option value="">사이트를 먼저 선택</option>');
        }
    });

    $(document).on('change', '#form_location', function() {
        var siteId = $('#form_site').val();
        var locId = $(this).val();
        if (siteId) {
            loadRacks(siteId, locId);
        }
    });

    // ========== Utility ==========
    function formatError(detail) {
        if (typeof detail === 'string') return detail;
        if (typeof detail === 'object') {
            var msgs = [];
            Object.keys(detail).forEach(function(k) {
                var v = detail[k];
                if (Array.isArray(v)) v = v.join(', ');
                msgs.push(k + ': ' + v);
            });
            return msgs.join('\n');
        }
        return String(detail);
    }

    window.applyFilters = function() {
        if (devicesTable) {
            devicesTable.ajax.url(buildAjaxUrl()).load();
        }
    };

    window.resetFilters = function() {
        $('#filterRole, #filterManufacturer, #filterSite, #filterStatus').val('');
        $('#devicesTable tfoot input').val('');
        devicesTable.columns().search('');
        applyFilters();
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span></div></div>');
        $('body').append(spinner);
        if (devicesTable) {
            devicesTable.ajax.url(buildAjaxUrl()).load(function() { spinner.remove(); }, false);
        } else {
            spinner.remove();
        }
    };

    function removeOverlay() {
        var o = document.getElementById('pageLoadingOverlay');
        if (o) { o.style.opacity = '0'; setTimeout(function() { o.remove(); }, 400); }
    }

    function showAlert(message, type) {
        var icons = { success: 'fa-check-circle', danger: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        var colors = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
        if (!$('#toastContainer').length) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }
        var toastId = 'toast_' + Date.now();
        var toastHtml = '<div id="' + toastId + '" class="toast align-items-center border-0 shadow-lg" role="alert" data-bs-delay="3000">' +
            '<div class="toast-header"><i class="fas ' + (icons[type] || icons.info) + ' me-2" style="color: ' + (colors[type] || colors.info) + ';"></i>' +
            '<strong class="me-auto">' + type + '</strong><button type="button" class="btn-close" data-bs-dismiss="toast"></button></div>' +
            '<div class="toast-body">' + message + '</div></div>';
        $('#toastContainer').append(toastHtml);
        var toastEl = document.getElementById(toastId);
        new bootstrap.Toast(toastEl).show();
        toastEl.addEventListener('hidden.bs.toast', function() { $(toastEl).remove(); });
    }

    function esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    $(document).ready(function() {
        initFilters();
        initTable();
    });

})();
