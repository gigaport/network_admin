$(document).ready(function () {
    const data_back = document.getElementById("back_data");
    const currentPath = data_back ? data_back.dataset.submenu : "";

    // HTML 요소 캐싱
    const $detailBody = $("#ptp-detail-body");
    const $detailModal = $("#modal_ptp_detail");
    const $detailTitle = $("#modal_ptp_detail_label");

    // ==========================================================
    // 1. PTP 요약 DataTable 초기화 (메인 화면)
    // ==========================================================
    const table = $('#ptp_summary_table').DataTable({
        responsive: true,
        paging: true,
        searching: true,
        ordering: true,
        pageLength: 50,
        lengthChange: false,
        ajax: {
            url: '/information/init',
            type: 'GET',
            data: { sub_menu: currentPath }, // 'info_ptp'
            dataSrc: function (json) {
                if (!json) return [];
                return json;
            }
        },
        // [중요] HTML 헤더 개수(8개)와 반드시 일치해야 함
        columns: [
            { data: 'device_name' },       // 0. 영역 (장비명으로 판단)
            { data: 'device_name' },       // 1. 장비명
            { data: 'current_time' },      // 2. Time
            { data: 'offset' },            // 3. 오차
            { data: 'mean_path_delay' },   // 4. 지연
            { data: 'jitter' },            // 5. 지터
            { data: 'packet_continuity' }, // 6. 연속성
            { data: null }                 // 7. 버튼
        ],
        columnDefs: [
            {
                // 0. [NEW] 영역 (PYD=운영, TYD=테스트)
                targets: 0,
                width: '10%',
                className: 'text-center align-middle fw-bold',
                render: function (data) {
                    if (!data) return '-';
                    // 대소문자 구분 없이 체크
                    if (data.toUpperCase().startsWith('PYD')) {
                        return '<span class="badge badge-phoenix badge-phoenix-primary">운영</span>';
                    } else if (data.toUpperCase().startsWith('TYD')) {
                        return '<span class="badge badge-phoenix badge-phoenix-warning">테스트</span>';
                    }
                    return '<span class="badge badge-phoenix badge-phoenix-secondary">기타</span>';
                }
            },
            {
                // 1. 장비명
                targets: 1,
                width: '10%',
                className: 'text-center align-middle fw-bold',
                render: function (data) { return data || '-'; }
            },
            {
                // 2. Time
                targets: 2,
                width: '20%',
                className: 'text-center align-middle',
                render: function (data) { return data || '-'; }
            },
            {
                // 3. 오차 (1000ns 넘어가면 빨간색 경고)
                targets: 3,
                width: '10%',
                className: 'text-center align-middle',
                render: function (data) {
                    if (data === undefined || data === null) return '-';
                    const val = Number(data);
                    const colorClass = Math.abs(val) > 1000 ? 'text-danger fw-bold' : '';
                    return `<span class="${colorClass}">${numberWithCommas(val)}</span>`;
                }
            },
            {
                // 4. 지연
                targets: 4,
                width: '10%',
                className: 'text-center align-middle',
                render: function (data) {
                    return (data !== undefined && data !== null) ? numberWithCommas(data) : '-';
                }
            },
            {
                // 5. 지터
                targets: 5,
                width: '10%',
                className: 'text-center align-middle',
                render: function (data) {
                    return (data !== undefined && data !== null) ? numberWithCommas(data) : '-';
                }
            },
            {
                // 6. 패킷 연속성
                targets: 6,
                width: '15%',
                className: 'text-center align-middle',
                render: function (data) {
                    if (data === undefined || data === null || data === '-') return '-';
                    // 100%면 초록색(성공), 아니면 빨간색(실패)
                    const badgeClass = data >= 100 ? 'text-success fw-bold' : 'text-danger fw-bold';
                    return `<span class="${badgeClass}">${data}%</span>`;
                }
            },
            {
                // 7. 버튼
                targets: 7,
                width: '10%',
                orderable: false,
                searchable: false,
                className: 'text-center align-middle',
                render: function (data) {
                    return `
                        <button type="button" class="btn btn-sm btn-outline-primary ptp-detail-btn">
                            상세보기
                        </button>
                    `;
                }
            }
        ],
        language: {
            emptyTable: "수집된 데이터가 없습니다.",
            loadingRecords: "데이터를 불러오는 중...",
            search: "검색:"
        }
    });

    // ==========================================================
    // 2. 상세보기 버튼 클릭 이벤트 (모달 팝업)
    // ==========================================================
    $('#ptp_summary_table tbody').on('click', '.ptp-detail-btn', function () {
        const tr = $(this).closest('tr');
        const rowData = table.row(tr).data();

        if (!rowData) return;

        const hostname = rowData.device_name || rowData.hostname || '-';
        const details = Array.isArray(rowData.details) ? rowData.details : [];

        $detailTitle.text(`[${hostname}] PTP 상세 정보`);
        $detailBody.empty();

        if (details.length === 0) {
            $detailBody.append('<tr><td class="text-center" colspan="6">상세 데이터가 없습니다.</td></tr>');
        } else {
            // 상세 데이터 Loop
            details.forEach(function (d) {
                const port = d.port || '-';
                const time = d.time || '-';
                const offset = numberWithCommas(d.offset);
                const delay = numberWithCommas(d.delay);
                const skew = d.skew || '-';
                const seqId = d.sequence_id || '-';

                // Offset이 크면 상세화면에서도 빨간색 표시
                const offsetClass = (Math.abs(d.offset) > 1000) ? 'text-danger fw-bold' : '';

                const rowHtml = `
                    <tr>
                        <td class="text-center align-middle">${port}</td>
                        <td class="text-center align-middle">${time}</td>
                        <td class="text-center align-middle ${offsetClass}">${offset}</td>
                        <td class="text-center align-middle">${delay}</td>
                        <td class="text-center align-middle">${skew}</td>
                        <td class="text-center align-middle">${seqId}</td>
                    </tr>
                `;
                $detailBody.append(rowHtml);
            });
        }

        // 부트스트랩 모달 띄우기
        const modal = new bootstrap.Modal($detailModal[0]);
        modal.show();
    });

    // [유틸리티] 숫자 3자리마다 콤마 찍기
    function numberWithCommas(x) {
        if (x === null || x === undefined) return '-';
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }
    // [NEW] 30초 주기 자동 새로고침 (Auto Refresh)
    setInterval(function () {
      // null: 페이징 유지, false: 전체 다시그리가 아닌 데이터만 갱신
      table.ajax.reload(null, false);
      console.log("[Autorefresh] PTP Data updated.");
    }, 30000); // 30000ms = 30초
});
