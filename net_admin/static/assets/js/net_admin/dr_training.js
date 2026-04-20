(function() {
    'use strict';

    var autoRefreshTimer = null;
    function isDark() { return document.documentElement.getAttribute('data-bs-theme') === 'dark'; }
    function T(light, dark) { return isDark() ? dark : light; }

    function esc(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(s));
        return d.innerHTML;
    }

    window.fetchStatus = function() {
        $.ajax({
            url: '/get_dr_training_status',
            method: 'GET',
            dataType: 'json',
            timeout: 65000,
            success: function(data) {
                hideLoading();
                if (data.success) {
                    var ts = data.timestamp ? data.timestamp.substring(0, 16) : '-';
                    document.getElementById('lastUpdated').textContent = '체크한 시간 : ' + ts;
                    renderDeviceCards(data.devices);
                } else {
                    showError(data.error || '데이터 조회 실패');
                }
            },
            error: function(xhr, status, error) {
                hideLoading();
                showError('서버 연결 실패: ' + error);
            }
        });
    };

    function hideLoading() {
        var overlay = document.getElementById('pageLoadingOverlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(function() { overlay.style.display = 'none'; }, 400);
        }
    }

    function showError(msg) {
        document.getElementById('deviceCards').innerHTML =
            '<div class="card border-0 shadow-sm bg-body-emphasis"><div class="card-body text-center py-5">' +
            '<i class="fas fa-exclamation-triangle text-warning me-2"></i>' +
            '<span style="color:#64748b;">' + esc(msg) + '</span></div></div>';
    }

    function renderSummary(summary, timestamp) {
        document.getElementById('stat_total').textContent = summary.total_interfaces;
        document.getElementById('stat_up').textContent = summary.up_count;
        document.getElementById('stat_down').textContent = summary.down_count;

        // 설정확인 카드
        var cfgOkEl = document.getElementById('stat_cfg_ok');
        var cfgFailEl = document.getElementById('stat_cfg_fail');
        if (cfgOkEl) cfgOkEl.textContent = (summary.config_ok || 0) + ' / ' + (summary.total_config_checks || 0);
        if (cfgFailEl) cfgFailEl.textContent = summary.config_fail || 0;

        var cfgCard = document.getElementById('cfgFailCard');
        if (cfgCard) {
            if ((summary.config_fail || 0) === 0) {
                cfgCard.style.background = 'linear-gradient(135deg, #64748b, #94a3b8)';
                cfgCard.style.boxShadow = '0 4px 15px rgba(100,116,139,0.3)';
            } else {
                cfgCard.style.background = 'linear-gradient(135deg, #d97706, #f59e0b)';
                cfgCard.style.boxShadow = '0 4px 15px rgba(245,158,11,0.3)';
            }
        }

        var statusEl = document.getElementById('stat_status');
        var statusCard = document.getElementById('statusCard');

        if (summary.all_ok) {
            statusEl.textContent = '정상';
            statusCard.style.background = 'linear-gradient(135deg, #059669, #10B981)';
            statusCard.style.boxShadow = '0 4px 15px rgba(16,185,129,0.3)';
        } else {
            statusEl.textContent = '경고';
            statusCard.style.background = 'linear-gradient(135deg, #dc2626, #f87171)';
            statusCard.style.boxShadow = '0 4px 15px rgba(220,38,38,0.3)';
        }

        var downCard = document.getElementById('downCard');
        if (summary.down_count === 0) {
            downCard.style.background = 'linear-gradient(135deg, #64748b, #94a3b8)';
            downCard.style.boxShadow = '0 4px 15px rgba(100,116,139,0.3)';
        } else {
            downCard.style.background = 'linear-gradient(135deg, #dc2626, #f87171)';
            downCard.style.boxShadow = '0 4px 15px rgba(220,38,38,0.3)';
        }

        // timestamp는 fetchStatus에서 처리
    }

    function renderDeviceCards(devices) {
        var container = document.getElementById('deviceCards');
        var html = '';
        var grandTotal = 0, grandMainOk = 0, grandDrOk = 0;

        devices.forEach(function(device) {
            var reachableBadge = device.reachable
                ? '<span style="background:#dcfce7;color:#16a34a;padding:3px 12px;border-radius:6px;font-size:0.85rem;font-weight:600;">연결됨</span>'
                : '<span style="background:#fef2f2;color:#dc2626;padding:3px 12px;border-radius:6px;font-size:0.85rem;font-weight:600;">접속불가</span>';

            // 전환율 계산
            var totalItems = 0, mainOk = 0, drOk = 0;
            var isIntfNormalDown = device.procedure === '51.01' ||
                (device.procedure === '51.02' && (device.device_name === 'RBD_MPR_L3_01' || device.device_name === 'RBD_SVC_L3_01'));
            var isIntfNormalUp = (device.procedure === '51.02' && (device.device_name === 'PYD_DFP_BB_01' || device.device_name === 'PYD_DFP_BB_02')) ||
                device.procedure === '51.04' || device.procedure === '51.05';
            // 인터페이스 판정
            if (device.interfaces) {
                device.interfaces.forEach(function(intf) {
                    totalItems++;
                    var isDown = intf.oper_state !== 'up';
                    if (isIntfNormalDown) {
                        if (isDown) mainOk++; else drOk++;
                    } else if (isIntfNormalUp) {
                        if (!isDown) mainOk++; else drOk++;
                    }
                });
            }
            // 설정 판정 (51.02 MPR/MKD/RBD_MPR: 설정됨=평상시정상, 미설정=DR정상)
            // RBD_MPR_L3_01: 미설정=평상시정상, 설정됨=DR정상
            var isCfgDevice = device.procedure === '51.02' &&
                (device.device_name === 'PYD_MPR_L3_01' || device.device_name === 'PHQ_MPR_L3_01' ||
                 device.device_name === 'PYD_MKD_L3_01' || device.device_name === 'PHQ_MKD_L3_01' ||
                 device.device_name === 'RBD_MPR_L3_01');
            var isRbdMpr = device.device_name === 'RBD_MPR_L3_01';
            if (isCfgDevice && device.config_checks) {
                device.config_checks.forEach(function(chk) {
                    totalItems++;
                    if (isRbdMpr) {
                        // RBD_MPR: 미설정=평상시정상, 설정됨=DR정상
                        if (!chk.found) mainOk++; else drOk++;
                    } else {
                        // 나머지: 설정됨=평상시정상, 미설정=DR정상
                        if (chk.found) mainOk++; else drOk++;
                    }
                });
            }

            var mainPct = totalItems > 0 ? Math.round(mainOk / totalItems * 100) : 0;
            var drPct = totalItems > 0 ? Math.round(drOk / totalItems * 100) : 0;
            grandTotal += totalItems; grandMainOk += mainOk; grandDrOk += drOk;

            html += '<div class="card border-0 shadow-sm bg-body-emphasis mb-3">';
            html += '<div class="card-body py-3 px-4">';

            // 카드 헤더
            html += '<div class="d-flex align-items-center flex-wrap gap-2 mb-3">';
            html += '<span style="background:#eef2ff;color:#6366f1;padding:5px 14px;border-radius:8px;font-size:0.95rem;font-weight:700;">절차 ' + esc(device.procedure) + '</span>';
            html += '<span style="font-size:1.1rem;font-weight:700;color:' + T('#1e293b','#e2e8f0') + ';">' + esc(device.device_name) + '</span>';
            html += '<span style="font-size:0.9rem;color:#64748b;">(' + esc(device.ip) + ')</span>';
            if (device.label) {
                html += '<span style="font-size:0.82rem;color:' + T('#475569','#94a3b8') + ';margin-left:10px;font-weight:500;">- ' + esc(device.label) + '</span>';
            }
            html += '<span class="ms-auto d-flex align-items-center gap-2">';
            if (totalItems > 0) {
                var mainColor = mainPct === 100 ? '#16a34a' : (mainPct >= 50 ? '#d97706' : '#dc2626');
                var drColor = drPct === 100 ? '#16a34a' : (drPct >= 50 ? '#d97706' : '#dc2626');
                html += '<span style="background:#f0fdf4;border:1px solid #bbf7d0;padding:4px 12px;border-radius:8px;font-size:0.82rem;">';
                html += '<span style="color:#64748b;font-weight:500;">메인전환율 </span>';
                html += '<span style="color:' + mainColor + ';font-weight:700;">' + mainOk + '/' + totalItems + ' (' + mainPct + '%)</span></span>';
                html += '<span style="background:#fef2f2;border:1px solid #fecaca;padding:4px 12px;border-radius:8px;font-size:0.82rem;">';
                html += '<span style="color:#64748b;font-weight:500;">DR전환율 </span>';
                html += '<span style="color:' + drColor + ';font-weight:700;">' + drOk + '/' + totalItems + ' (' + drPct + '%)</span></span>';
            }
            html += reachableBadge + '</span>';
            html += '</div>';

            if (!device.reachable) {
                html += '<div style="text-align:center;padding:20px;color:#dc2626;font-size:0.95rem;">';
                html += '<i class="fas fa-exclamation-triangle me-2"></i>' + esc(device.error || '장비에 접속할 수 없습니다');
                html += '</div>';
            } else {
                // 인터페이스 테이블 (인터페이스가 있는 경우만)
                if (device.interfaces && device.interfaces.length > 0) {
                    var hasDrJudge = device.procedure === '51.01' ||
                        (device.procedure === '51.02' && (device.device_name === 'PYD_DFP_BB_01' || device.device_name === 'PYD_DFP_BB_02' ||
                         device.device_name === 'RBD_MPR_L3_01' || device.device_name === 'RBD_SVC_L3_01')) ||
                        device.procedure === '51.04' || device.procedure === '51.05';

                    html += '<div class="table-responsive">';
                    html += '<table class="table table-sm table-hover mb-0" style="font-size:0.95rem;">';
                    html += '<thead><tr style="background:' + T('#f8fafc','#1e293b') + ';">';
                    html += '<th class="text-center" style="width:5%;">No</th>';
                    if (hasDrJudge) {
                        html += '<th class="text-center" style="width:9%;background:#f0fdf4;">가동상태</th>';
                        html += '<th class="text-center" style="width:9%;background:#fef2f2;">DR상태</th>';
                    }
                    html += '<th class="text-center" style="width:' + (hasDrJudge ? '14' : '16') + '%;">Interface</th>';
                    html += '<th class="text-center" style="width:' + (hasDrJudge ? '7' : '9') + '%;">Admin</th>';
                    html += '<th class="text-center" style="width:' + (hasDrJudge ? '9' : '11') + '%;">Oper State</th>';
                    html += '<th class="text-center" style="width:' + (hasDrJudge ? '7' : '9') + '%;">Speed</th>';
                    html += '<th class="text-center" style="width:' + (hasDrJudge ? '6' : '7') + '%;">MTU</th>';
                    html += '<th style="width:' + (hasDrJudge ? '17' : '23') + '%;">Description</th>';
                    html += '<th style="width:' + (hasDrJudge ? '17' : '20') + '%;">Last Flapped</th>';
                    html += '</tr></thead><tbody>';

                    device.interfaces.forEach(function(intf, idx) {
                        var isDown = intf.oper_state !== 'up';
                        var rowStyle = '';
                        var operBadge = isDown
                            ? '<span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;border-radius:50%;background:#dc2626;display:inline-block;"></span><span style="color:#dc2626;font-weight:600;">down</span></span>'
                            : '<span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;border-radius:50%;background:#16a34a;display:inline-block;"></span><span style="color:#16a34a;font-weight:600;">up</span></span>';

                        var adminBadge = intf.admin_state === 'up'
                            ? '<span style="color:#16a34a;">up</span>'
                            : '<span style="color:#dc2626;">' + esc(intf.admin_state) + '</span>';

                        var normalJudge = '', drJudge = '';
                        if (hasDrJudge) {
                            var normalIsDown = device.procedure === '51.01' ||
                                (device.procedure === '51.02' && (device.device_name === 'RBD_MPR_L3_01' || device.device_name === 'RBD_SVC_L3_01'));
                            if (normalIsDown) {
                                normalJudge = isDown
                                    ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                    : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                                drJudge = !isDown
                                    ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                    : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                            } else {
                                normalJudge = !isDown
                                    ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                    : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                                drJudge = isDown
                                    ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                    : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                            }
                        }

                        html += '<tr style="' + rowStyle + '">';
                        html += '<td class="text-center" style="color:#94a3b8;font-weight:600;">' + (idx + 1) + '</td>';
                        if (hasDrJudge) {
                            html += '<td class="text-center" style="background:rgba(240,253,244,0.5);">' + normalJudge + '</td>';
                            html += '<td class="text-center" style="background:rgba(254,242,242,0.5);">' + drJudge + '</td>';
                        }
                        html += '<td class="text-center fw-semibold">' + esc(intf.name) + '</td>';
                        html += '<td class="text-center">' + adminBadge + '</td>';
                        html += '<td class="text-center">' + operBadge + '</td>';
                        html += '<td class="text-center">' + esc(intf.speed) + '</td>';
                        html += '<td class="text-center">' + esc(intf.mtu) + '</td>';
                        html += '<td>' + esc(intf.description || '-') + '</td>';
                        html += '<td style="color:#64748b;">' + esc(intf.last_link_flapped || '-') + '</td>';
                        html += '</tr>';
                    });

                    html += '</tbody></table></div>';
                }
            }

            // 설정 확인 테이블
            if (device.config_checks && device.config_checks.length > 0 && device.reachable) {
                if (device.interfaces && device.interfaces.length > 0) {
                    html += '<div style="margin-top:12px;"></div>';
                }
                // 설정확인에 평상 시/DR 전환 시 판정 추가 여부
                var hasCfgDrJudge = device.procedure === '51.02' &&
                    (device.device_name === 'PYD_MPR_L3_01' || device.device_name === 'PHQ_MPR_L3_01' ||
                     device.device_name === 'PYD_MKD_L3_01' || device.device_name === 'PHQ_MKD_L3_01' ||
                     device.device_name === 'RBD_MPR_L3_01');

                html += '<div class="table-responsive">';
                html += '<table class="table table-sm table-hover mb-0" style="font-size:0.95rem;">';
                html += '<thead><tr style="background:' + T('#f8fafc','#1e293b') + ';">';
                html += '<th class="text-center" style="width:5%;">No</th>';
                if (hasCfgDrJudge) {
                    html += '<th class="text-center" style="width:9%;background:#f0fdf4;">가동상태</th>';
                    html += '<th class="text-center" style="width:9%;background:#fef2f2;">DR상태</th>';
                }
                html += '<th class="text-center" style="width:10%;">구분</th>';
                html += '<th style="width:' + (hasCfgDrJudge ? '38' : '52') + '%;">설정 항목</th>';
                html += '<th class="text-center" style="width:12%;">상태</th>';
                if (false) {
                }
                html += '<th style="width:15%;">상세</th>';
                html += '</tr></thead><tbody>';

                device.config_checks.forEach(function(chk, idx) {
                    var rowStyle = '';
                    var typeBadge;
                    if (chk.type === 'route') {
                        typeBadge = '<span style="background:#dbeafe;color:#2563eb;padding:2px 8px;border-radius:4px;font-size:0.78rem;font-weight:600;">Route</span>';
                    } else if (chk.type === 'pim_sparse') {
                        typeBadge = '<span style="background:#fef3c7;color:#b45309;padding:2px 8px;border-radius:4px;font-size:0.78rem;font-weight:600;">PIM</span>';
                    } else {
                        typeBadge = '<span style="background:#f3e8ff;color:#9333ea;padding:2px 8px;border-radius:4px;font-size:0.78rem;font-weight:600;">Prefix-list</span>';
                    }
                    var statusBadge = chk.found
                        ? '<span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;border-radius:50%;background:#16a34a;display:inline-block;"></span><span style="color:#16a34a;font-weight:600;">설정됨</span></span>'
                        : '<span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;border-radius:50%;background:#d97706;display:inline-block;"></span><span style="color:#d97706;font-weight:600;">미설정</span></span>';

                    // 평상 시/DR 전환 시 판정
                    // RBD_MPR_L3_01: 미설정=평상시정상, 설정됨=DR정상 (PIM 해제 후 DR에서 설정)
                    // 나머지: 설정됨=평상시정상, 미설정=DR정상
                    var cfgNormalJudge = '', cfgDrJudge = '';
                    if (hasCfgDrJudge) {
                        var cfgReverse = device.device_name === 'RBD_MPR_L3_01';
                        if (cfgReverse) {
                            cfgNormalJudge = !chk.found
                                ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                            cfgDrJudge = chk.found
                                ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                        } else {
                            cfgNormalJudge = chk.found
                                ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                            cfgDrJudge = !chk.found
                                ? '<span style="color:#16a34a;font-weight:700;">OK</span>'
                                : '<span style="color:#dc2626;font-weight:700;">Not OK</span>';
                        }
                    }

                    html += '<tr style="' + rowStyle + '">';
                    html += '<td class="text-center" style="color:#94a3b8;font-weight:600;">' + (idx + 1) + '</td>';
                    if (hasCfgDrJudge) {
                        html += '<td class="text-center" style="background:rgba(240,253,244,0.5);">' + cfgNormalJudge + '</td>';
                        html += '<td class="text-center" style="background:rgba(254,242,242,0.5);">' + cfgDrJudge + '</td>';
                    }
                    html += '<td class="text-center">' + typeBadge + '</td>';
                    html += '<td><code style="font-size:0.88rem;background:' + T('#f1f5f9','#334155') + ';padding:2px 6px;border-radius:4px;">' + esc(chk.description) + '</code></td>';
                    html += '<td class="text-center">' + statusBadge + '</td>';
                    html += '<td style="color:#64748b;">' + esc(chk.detail || '-') + '</td>';
                    html += '</tr>';
                });

                html += '</tbody></table></div>';
            }

            html += '</div></div>';
        });

        container.innerHTML = html;

        // 상단 통합 전환율 업데이트
        var grandMainPct = grandTotal > 0 ? Math.round(grandMainOk / grandTotal * 100) : 0;
        var grandDrPct = grandTotal > 0 ? Math.round(grandDrOk / grandTotal * 100) : 0;

        document.getElementById('totalMainPct').textContent = grandMainPct + '%';
        document.getElementById('totalMainCount').textContent = grandMainOk + ' / ' + grandTotal;
        document.getElementById('totalDrPct').textContent = grandDrPct + '%';
        document.getElementById('totalDrCount').textContent = grandDrOk + ' / ' + grandTotal;

        // 바 차트 업데이트
        document.getElementById('barMain').style.width = grandMainPct + '%';
        document.getElementById('barMainLabel').textContent = grandMainPct + '% (' + grandMainOk + '/' + grandTotal + ')';
        document.getElementById('barDr').style.width = grandDrPct + '%';
        document.getElementById('barDrLabel').textContent = grandDrPct + '% (' + grandDrOk + '/' + grandTotal + ')';

        // 카드 색상 - 가동전환율: 초록 계열
        var mainCard = document.getElementById('totalMainCard');
        if (grandMainPct === 100) {
            mainCard.style.background = 'linear-gradient(135deg, #059669, #34d399)';
        } else if (grandMainPct >= 50) {
            mainCard.style.background = 'linear-gradient(135deg, #15803d, #4ade80)';
        } else {
            mainCard.style.background = 'linear-gradient(135deg, #166534, #86efac)';
        }
        // 카드 색상 - DR전환율: 빨강 계열
        var drCard = document.getElementById('totalDrCard');
        if (grandDrPct === 100) {
            drCard.style.background = 'linear-gradient(135deg, #b91c1c, #ef4444)';
        } else if (grandDrPct >= 50) {
            drCard.style.background = 'linear-gradient(135deg, #991b1b, #f87171)';
        } else {
            drCard.style.background = 'linear-gradient(135deg, #7f1d1d, #fca5a5)';
        }
    }

    window.handleAutoRefreshChange = function(value) {
        stopAutoRefresh();
        var sec = parseInt(value);
        if (sec > 0) {
            startAutoRefresh(sec);
        }
    };

    function startAutoRefresh(sec) {
        stopAutoRefresh();
        autoRefreshTimer = setInterval(function() {
            fetchStatus();
        }, sec * 1000);
    }

    function stopAutoRefresh() {
        if (autoRefreshTimer) {
            clearInterval(autoRefreshTimer);
            autoRefreshTimer = null;
        }
    }

    // 초기 로드
    $(document).ready(function() {
        fetchStatus();
        // 기본값 30초 자동 갱신
        startAutoRefresh(30);
    });

})();
